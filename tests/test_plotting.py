"""Геометрия графиков: неизменность данных, оси и непрерывная развёртка."""
import math
import unittest

from stochlab.appearance import get_scheme
from stochlab.model import Parameters, Sample, Model
from stochlab.plotting import (
    Scene, ViewLimits, _axes, _time_window, potential_scene, trajectory_scene, title_scene,
)


class PlotTests(unittest.TestCase):
    def setUp(self):
        self.parameters = Parameters()
        model = Model(self.parameters)
        self.samples = [model.sample()]
        for index in range(1000):
            model.step()
            if index % 5 == 0:
                self.samples.append(model.sample())
        self.time = model.t

    def test_monochrome_has_dashed_force_and_grayscale_strokes(self):
        scene = trajectory_scene(self.parameters, self.time, self.samples, 700, 320, 'monochrome')
        lines = [item for item in scene.primitives if item.kind == 'line']
        self.assertTrue(any(line.dash == (7, 5) for line in lines))
        self.assertTrue(any(not line.dash and line.color == '#000000' for line in lines))
        for line in lines:
            color = line.color.lstrip('#')
            self.assertTrue(color[0:2] == color[2:4] == color[4:6])

    def test_both_plot_orientations_preserve_source_samples(self):
        before = list(self.samples)
        for vertical in (True, False):
            scene = trajectory_scene(self.parameters, self.time, self.samples, 700, 320, 'states', vertical)
            self.assertTrue(scene.primitives)
            self.assertEqual(self.samples, before)

    def test_palette_uses_both_sides_of_barrier(self):
        scene = title_scene(500, 300, 'states')
        colors = {item.color for item in scene.primitives}
        self.assertIn('#6741a5', colors)
        self.assertIn('#19734a', colors)

    def test_zero_time_flat_potential_and_plain_axis_labels(self):
        parameters = Parameters(a=0, b=0)
        samples = [Sample(0, 0, 0, 0)]
        for scene in (
            potential_scene(parameters, 0, 0, samples, 300, 200, 'quantities'),
            trajectory_scene(parameters, 0, samples, 300, 200, 'quantities'),
            trajectory_scene(parameters, 0, samples, 300, 200, 'quantities', False),
        ):
            for item in scene.primitives:
                self.assertTrue(all(math.isfinite(value) for value in item.coordinates))
                self.assertNotIn('[1]', item.text)
            labels = [item.text for item in scene.primitives if item.kind == 'text']
            self.assertTrue('x' in labels)

    def test_all_saved_trajectory_points_are_retained(self):
        parameters = Parameters(omega=.02, drive_enabled=False)
        samples = [Sample(i*.1, -1 if i < 2500 else 1, 0, 0) for i in range(5000)]
        scene = trajectory_scene(parameters, samples[-1].t, samples, 700, 320, 'quantities')
        coordinates = [item for item in scene.primitives if item.kind == 'line' and item.color == '#245b86']
        self.assertEqual(len(coordinates), 1)
        self.assertEqual(len(coordinates[0].coordinates), len(samples)*2)

    def test_force_is_independent_of_trajectory_sampling(self):
        period = 2*math.pi/self.parameters.omega
        samples = [Sample(0, -1, 0, 999), Sample(period, -1, 0, 999)]
        scene = trajectory_scene(self.parameters, period, samples, 700, 320, 'quantities', False)
        force = [item for item in scene.primitives if item.kind == 'line' and item.color == '#a34d0a']
        self.assertEqual(len(force), 1)
        self.assertGreater(len(force[0].coordinates), 400)
        ys = force[0].coordinates[1::2]
        self.assertGreater(max(ys)-min(ys), 100)

    def test_view_limits_only_expand_during_a_realization(self):
        limits = ViewLimits()
        limits.update(self.parameters, self.samples, -1.4)
        original = limits.extent, limits.energy_min, limits.energy_max
        for x in [-1.3, -1, 0, 1, 1.4]:
            limits.update(self.parameters, self.samples, x)
            self.assertEqual(original, (limits.extent, limits.energy_min, limits.energy_max))
        limits.update(self.parameters, [Sample(0, 5, 0, 0)], 5)
        expanded = limits.extent, limits.energy_min, limits.energy_max
        self.assertGreater(expanded[0], original[0])
        self.assertGreater(expanded[2], original[2])
        limits.update(self.parameters, self.samples, -1)
        self.assertEqual(expanded, (limits.extent, limits.energy_min, limits.energy_max))

    def test_time_window_translates_old_points_without_stretching(self):
        palette = get_scheme('quantities')
        for vertical in (True, False):
            transforms = []
            for time in (10, 11.5, 1000):
                low, high = _time_window(self.parameters, time)
                self.assertAlmostEqual(high-low, 6*math.pi/self.parameters.omega)
                if vertical:
                    axes = _axes(Scene(700, 320), -3, 3, low, high, 'x', 't', palette, time_axis='y')
                    positions = [axes.y(t) for t in (3, 5)]
                else:
                    axes = _axes(Scene(700, 320), low, high, -3, 3, 't', 'x', palette, time_axis='x')
                    positions = [axes.x(t) for t in (3, 5)]
                transforms.append(positions)
            distances = [p[1]-p[0] for p in transforms]
            self.assertAlmostEqual(distances[0], distances[1])
            self.assertAlmostEqual(distances[0], distances[2])
            self.assertAlmostEqual(transforms[1][0]-transforms[0][0],
                                   transforms[1][1]-transforms[0][1])

    def test_startup_has_no_fictitious_negative_time_samples(self):
        scene = trajectory_scene(self.parameters, self.time, self.samples, 700, 320, 'quantities')
        # В начале развёртки нижняя часть ещё не заполнена историей.
        lines = [p for p in scene.primitives if p.kind == 'line' and p.color == '#245b86']
        self.assertEqual(len(lines), 1)
        ys = lines[0].coordinates[1::2]
        self.assertLess(max(ys)-min(ys), 25)
        self.assertEqual(min(sample.t for sample in self.samples), 0)
        before = list(self.samples)
        trajectory_scene(self.parameters, 0, [self.samples[0]], 700, 320, 'quantities')
        self.assertEqual(before, self.samples)


if __name__ == '__main__':
    unittest.main()
