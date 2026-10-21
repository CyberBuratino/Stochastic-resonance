"""Проверки экспортируемого рисунка без графического дисплея."""

import unittest
from xml.etree import ElementTree

from stochlab.model import Parameters, Sample, Model
from stochlab.plotting import (
    Scene, ViewLimits, potential_scene, trajectory_scene, title_scene,
)


class PlotTests(unittest.TestCase):
    def setUp(self):
        self.parameters = Parameters()
        self.model = Model(self.parameters)
        self.samples = [Sample(0, self.model.x, self.model.v, 0)]
        for index in range(1000):
            self.model.step()
            if index % 5 == 0:
                self.samples.append(Sample(self.model.t, self.model.x, self.model.v, 0.1))

    def test_export_is_valid_svg_and_escapes_text(self):
        scene = Scene(500, 300)
        scene.text(20, 20, 'x < y & "test"', '#000000')
        svg = scene.to_svg()
        root = ElementTree.fromstring(svg)
        self.assertIn('x &lt; y &amp;', svg)
        self.assertEqual(root.find('{http://www.w3.org/2000/svg}text').text, 'x < y & "test"')

    def test_monochrome_export_has_dashed_force_and_no_colored_strokes(self):
        scene = trajectory_scene(self.parameters, self.model.t, self.samples, 700, 320,
                                 'monochrome')
        root = ElementTree.fromstring(scene.to_svg())
        lines = root.findall('{http://www.w3.org/2000/svg}polyline')
        self.assertTrue(any(line.get('stroke-dasharray') == '7,5' for line in lines))
        for line in lines:
            color = line.get('stroke').lstrip('#')
            self.assertTrue(color[0:2] == color[2:4] == color[4:6])
        self.assertTrue(any(line.get('stroke') == '#000000'
                            and line.get('stroke-dasharray') is None for line in lines))

    def test_both_plot_orientations_preserve_source_samples(self):
        before = list(self.samples)
        for vertical in (True, False):
            scene = trajectory_scene(self.parameters, self.model.t, self.samples,
                                     700, 320, 'states', vertical)
            ElementTree.fromstring(scene.to_svg())
            self.assertEqual(self.samples, before)

    def test_palette_uses_both_sides_of_barrier(self):
        scene = title_scene(500, 300, 'states')
        colors = {item.color for item in scene.primitives}
        self.assertIn('#6741a5', colors)
        self.assertIn('#19734a', colors)

    def test_time_zero_and_flat_potential_are_finite(self):
        parameters = Parameters(a=0, b=0)
        samples = [Sample(0, 0, 0, 0)]
        for scene in (
            potential_scene(parameters, 0, 0, samples, 300, 200, 'quantities'),
            trajectory_scene(parameters, 0, samples, 300, 200, 'quantities'),
        ):
            svg = scene.to_svg()
            import math
            for item in scene.primitives:
                self.assertTrue(all(math.isfinite(value) for value in item.coordinates))
            ElementTree.fromstring(svg)

    def test_all_saved_trajectory_points_are_retained(self):
        parameters = Parameters(omega=.02, drive_enabled=False)
        samples = [Sample(i*.1, -1 if i < 2500 else 1, 0, 0) for i in range(5000)]
        scene = trajectory_scene(parameters, samples[-1].t, samples, 700, 320, 'quantities')
        coordinates = [item for item in scene.primitives if item.kind == 'line' and item.color == '#245b86']
        self.assertEqual(len(coordinates), 1)
        self.assertEqual(len(coordinates[0].coordinates), len(samples)*2)

    def test_force_is_smooth_and_independent_of_trajectory_sampling(self):
        import math
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



if __name__ == '__main__':
    unittest.main()
