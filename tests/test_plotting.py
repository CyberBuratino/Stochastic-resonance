"""Геометрия графиков: неизменность данных, оси и непрерывная развёртка."""
import math
from dataclasses import replace
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

    def test_stationary_potential_stays_fixed_while_instantaneous_curve_changes(self):
        p = self.parameters
        palette = get_scheme("quantities")
        scenes = [potential_scene(p, phase/p.omega, -1, self.samples, 700, 320, "quantities")
                  for phase in (0, math.pi/2, math.pi)]
        reference = [[line for line in scene.primitives
                      if line.kind == "line" and line.color == palette.axes and line.dash == (7, 5)]
                     for scene in scenes]
        self.assertTrue(reference[0])
        self.assertEqual(reference[0], reference[1])
        self.assertEqual(reference[0], reference[2])
        solid = [[line for line in scene.primitives
                  if line.kind == "line" and line.color == palette.coordinate and not line.dash]
                 for scene in scenes]
        self.assertNotEqual(solid[0], solid[1])
        self.assertLess(scenes[0].primitives.index(reference[0][0]),
                        scenes[0].primitives.index(solid[0][0]))

    def test_stationary_potential_coincides_with_undriven_curve_in_all_palettes(self):
        p = replace(self.parameters, drive_enabled=False)
        for scheme in ("quantities", "states", "monochrome"):
            palette = get_scheme(scheme)
            scene = potential_scene(p, self.time, -1, self.samples, 700, 320, scheme)
            reference = [line for line in scene.primitives
                         if line.kind == "line" and line.color == palette.axes and line.dash == (7, 5)]
            self.assertTrue(reference)
            # Цветовая схема состояний разбивает сплошную кривую в x=0.
            if scheme != "states":
                solid = [line for line in scene.primitives
                         if line.kind == "line" and line.color == palette.coordinate and not line.dash]
                self.assertEqual([line.coordinates for line in reference],
                                 [line.coordinates for line in solid])
            if scheme == "monochrome":
                self.assertEqual(palette.axes[1:3], palette.axes[3:5])
                self.assertEqual(palette.axes[3:5], palette.axes[5:7])

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

    def test_particle_projection_matches_current_endpoint_and_rotation_is_unambiguous(self):
        time = 100
        current = Sample(time, .75, 0, 0)
        history = [Sample(0, -1, 0, 0), current]
        limits = ViewLimits()
        limits.update(self.parameters, history, current.x)
        before = list(history)
        for vertical in (True, False):
            potential = potential_scene(self.parameters, time, current.x, history, 700, 200,
                                        "quantities", view_limits=limits, connect_trajectory=vertical)
            trajectory = trajectory_scene(self.parameters, time, history, 700, 320, "quantities",
                                          vertical, view_limits=limits)
            particle = next(item for item in potential.primitives if item.kind == "circle")
            marker = next(item for item in trajectory.primitives if item.kind == "circle")
            lines = [item for item in trajectory.primitives
                     if item.kind == "line" and item.color == "#245b86"]
            self.assertEqual(lines[-1].coordinates[-2:], marker.coordinates[:2])
            self.assertEqual(marker.color, particle.color)
            guide = [item for item in trajectory.primitives if item.kind == "line" and item.dash == (4, 4)]
            upper = next(item for item in potential.primitives if item.kind == "line" and item.dash == (4, 4))
            if vertical:
                self.assertEqual(particle.coordinates[0], marker.coordinates[0])
                self.assertEqual(len(guide), 1)
                self.assertEqual(guide[0].coordinates, (marker.coordinates[0], 0, *marker.coordinates[:2]))
                self.assertEqual(upper.coordinates[-1], potential.height)
                self.assertLessEqual(potential.height-particle.coordinates[1]+marker.coordinates[1], 60)
            else:
                self.assertEqual(guide, [])
                self.assertEqual(upper.coordinates[-1], particle.coordinates[1])
        self.assertEqual(history, before)

    def test_projection_has_clearance_around_axis_numbers_at_zero(self):
        current = Sample(100, 0, 0, 0)
        history = [Sample(0, -1, 0, 0), current]
        scenes = [potential_scene(self.parameters, 100, 0, history, 700, 200, "quantities"),
                  trajectory_scene(self.parameters, 100, history, 700, 320, "quantities")]
        for scene in scenes:
            zero = min((item for item in scene.primitives
                        if item.kind == "text" and item.text == "0" and item.anchor == "center"),
                       key=lambda item: item.coordinates[1])
            guides = [item for item in scene.primitives if item.kind == "line" and item.dash == (4, 4)]
            self.assertTrue(guides)
            for guide in guides:
                low, high = sorted(guide.coordinates[1::2])
                self.assertTrue(high < zero.coordinates[1]-zero.font_size/2
                                or low > zero.coordinates[1]+zero.font_size/2)

    def test_six_period_window_displays_older_samples_without_changing_them(self):
        parameters = Parameters(omega=.08, drive_enabled=False)
        period = 2*math.pi/parameters.omega
        time = 8*period
        samples = [Sample(index*period/20, math.sin(index), 0, 0) for index in range(161)]
        before = list(samples)
        for vertical in (True, False):
            for periods in (3, 6):
                low, high = _time_window(parameters, time, periods)
                self.assertAlmostEqual(high-low, periods*period)
                scene = trajectory_scene(parameters, time, samples, 700, 320, "quantities", vertical,
                                         periods=periods)
                lines = [item for item in scene.primitives
                         if item.kind == "line" and item.color == "#245b86"]
                self.assertEqual(len(lines), 1)
                expected = [sample for sample in samples if low <= sample.t <= high]
                self.assertEqual(len(lines[0].coordinates), 2*len(expected))
        self.assertEqual(samples, before)

if __name__ == '__main__':
    unittest.main()
