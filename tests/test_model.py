"""Проверки физики и совместимости с прежней JavaScript-версией.

Запуск из корня репозитория: python -m unittest discover -s tests
Эталонные значения в тестах паритета получены исходным js/physics.js
в Node.js перед переносом. JavaScript для запуска тестов уже не нужен.
"""

from dataclasses import replace
import math
import unittest

from stochlab.model import (
    Model,
    Parameters,
    SeededRandom,
    barrier_height,
    critical_force,
    driving_force,
    noise_intensity,
    potential,
    total_force,
    well_position,
)


class ModelTests(unittest.TestCase):
    def test_potential_geometry_and_gradient(self):
        for a in (0.1, 1.0, 2.0):
            for b in (0.01, 0.5, 2.0):
                p = Parameters(a=a, b=b, f=0)
                minimum = well_position(p)
                self.assertAlmostEqual(potential(minimum, p), -a * a / (4 * b))
                self.assertAlmostEqual(total_force(minimum, 0, p), 0)
                self.assertAlmostEqual(barrier_height(p), a * a / (4 * b))
                for x in (-2.0, -0.5, 0.0, 0.8, 2.0):
                    h = 1e-6
                    derivative = (potential(x + h, p) - potential(x - h, p)) / (2 * h)
                    self.assertAlmostEqual(total_force(x, 0, p), -derivative, places=7)
        self.assertAlmostEqual(critical_force(Parameters()), 0.5443310539518174)

    def test_invalid_parameters_fail_before_integration(self):
        invalid = [
            {"T": -1}, {"T": math.nan}, {"T": math.inf}, {"gamma": 0},
            {"omega": 0}, {"dt": 1}, {"seed": 0.5}, {"seed": True},
            {"seed": 2**32}, {"drive_enabled": 1}, {"a": 1, "b": 0},
            {"a": "1"},
        ]
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(ValueError):
                Parameters(**values)

    def test_seeded_random_matches_javascript(self):
        generator = SeededRandom(42)
        expected = [0.6011037519201636, 0.44829055899754167,
                    0.8524657934904099, 0.6697340414393693, 0.17481389874592423]
        self.assertEqual([generator.uniform() for _ in range(5)], expected)
        generator = SeededRandom(42)
        expected_normal = [-1.2848381576290195, -0.9453528099747296,
                           -0.6112802846514629, -0.5658325852126875, -1.9727758972262703]
        for expected_value in expected_normal:
            self.assertAlmostEqual(generator.normal(), expected_value, places=13)

    def test_trajectory_matches_javascript_after_1000_steps(self):
        # Эталоны содержат как обычную реализацию, так и три межъямных перехода.
        cases = [
            (Parameters(), -1.5373871864893696, -0.1261971060691662, 0),
            (Parameters(T=1.2, a=1.6, b=0.9, gamma=0.7, f=0.3, seed=123456),
             1.3342494100498352, -0.7668403681963106, 3),
            (Parameters(T=0.6, drive_enabled=False, seed=987),
             -0.4331084331588533, 1.395537359884859, 0),
        ]
        for parameters, expected_x, expected_v, expected_transitions in cases:
            with self.subTest(parameters=parameters):
                model = Model(parameters)
                for _ in range(1000):
                    model.step()
                self.assertEqual(model.t, 20)
                self.assertAlmostEqual(model.x, expected_x, places=10)
                self.assertAlmostEqual(model.v, expected_v, places=10)
                self.assertEqual(model.transitions, expected_transitions)

    def test_same_seed_reproduces_trajectory(self):
        first, second = Model(), Model()
        different = Model(Parameters(seed=43))
        for _ in range(10_000):
            first.step()
            second.step()
            different.step()
        self.assertEqual(first.sample(), second.sample())
        self.assertNotEqual(first.x, different.x)

    def test_gaussian_mean_and_variance(self):
        generator = SeededRandom(19)
        count = 100_000
        samples = [generator.normal() for _ in range(count)]
        mean = sum(samples) / count
        second_moment = sum(value * value for value in samples) / count
        self.assertLess(abs(mean), 0.015)
        self.assertLess(abs(second_moment - 1), 0.025)

    def test_noiseless_undriven_particle_stays_at_minimum(self):
        model = Model(Parameters(T=0, f=0))
        for _ in range(20_000):
            model.step()
        self.assertAlmostEqual(model.x, -math.sqrt(2), places=12)
        self.assertEqual(model.transitions, 0)

    def test_fluctuation_dissipation_normalization(self):
        for gamma in (0.3, 1.0, 3.0):
            p = Parameters(T=0.4, gamma=gamma)
            model = Model(p)
            self.assertEqual(noise_intensity(p), gamma * 0.4)
            expected_variance = p.T * (1 - math.exp(-2 * gamma * p.dt))
            self.assertAlmostEqual(model.sigma**2, expected_variance, places=14)

    def test_equilibrium_temperature_and_step_refinement(self):
        values = []
        for dt, gamma in ((0.02, 1), (0.01, 1), (0.02, 2)):
            model = Model(Parameters(T=0.4, f=0, dt=dt, gamma=gamma))
            sum_v_squared = 0.0
            count = 0
            for _ in range(round(4000 / dt)):
                model.step()
                if model.t > 500:
                    sum_v_squared += model.v * model.v
                    count += 1
            value = sum_v_squared / count
            values.append(value)
            self.assertLess(abs(value - 0.4), 0.035)
        self.assertLess(abs(values[0] - values[1]), 0.035)

    def test_disabled_force_equals_zero_amplitude(self):
        off = Model(Parameters(drive_enabled=False, f=0.4))
        zero = Model(Parameters(f=0))
        for _ in range(10_000):
            off.step()
            zero.step()
        self.assertEqual(off.x, zero.x)
        self.assertEqual(off.v, zero.v)
        self.assertEqual(off.parameters.f, 0.4)
        self.assertEqual(driving_force(5, off.parameters), 0)

    def test_flat_and_single_well_cases_have_no_interwell_count(self):
        for b in (0, 0.5):
            model = Model(Parameters(a=0, b=b, T=0, drive_enabled=False))
            for _ in range(10_000):
                model.step()
            self.assertEqual(model.x, 0)
            self.assertEqual(model.transitions, 0)
            self.assertEqual(barrier_height(model.parameters), 0)

    def test_hysteresis_ignores_repeated_barrier_recrossings(self):
        model = Model()
        for x in (-0.1, 0.1, -0.2, 0.2):
            model.x = x
            model._count_transition()
        self.assertEqual(model.transitions, 0)
        model.x = well_position(model.parameters)
        model._count_transition()
        self.assertEqual(model.transitions, 1)
        model.x = -0.1
        model._count_transition()
        self.assertEqual(model.transitions, 1)

    def test_edge_parameters_remain_finite(self):
        for a in (0, 2):
            for b in (0.01, 2):
                for gamma in (0.3, 3):
                    model = Model(Parameters(a=a, b=b, gamma=gamma, T=1.5, f=0.5))
                    for _ in range(30_000):
                        model.step()
                    self.assertTrue(math.isfinite(model.x))
                    self.assertTrue(math.isfinite(model.v))


if __name__ == "__main__":
    unittest.main()
