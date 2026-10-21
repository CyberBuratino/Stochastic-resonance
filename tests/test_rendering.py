"""Проверки растеризации: края сглаживаются, геометрия не меняется."""
from copy import deepcopy
import unittest

from PIL import ImageChops

from stochlab.plotting import Scene
from stochlab.rendering import _dashed_paths, render_scene


def rgb_pixels(image):
    """Читает RGB-пиксели без зависимости от меняющегося API getdata."""
    data = image.tobytes()
    for index in range(0, len(data), 3):
        yield tuple(data[index:index+3])


class RenderingTests(unittest.TestCase):
    def test_diagonal_has_subpixel_coverage(self):
        scene = Scene(80, 60)
        scene.line((8, 8, 70, 45), "#000000", 1)
        native = render_scene(scene, scale=1)
        smooth = render_scene(scene, scale=3)
        native_gray = {pixel[0] for pixel in rgb_pixels(native)}
        smooth_gray = {pixel[0] for pixel in rgb_pixels(smooth)}
        self.assertEqual(native_gray, {0, 255})
        self.assertTrue(any(0 < value < 255 for value in smooth_gray))
        self.assertGreater(len(smooth_gray), 10)
        # Сглаживание занимает только ближайшие пиксели к исходной линии.
        ink = ImageChops.invert(smooth).getbbox()
        self.assertLessEqual(abs(ink[0]-8), 4)
        self.assertLessEqual(abs(ink[1]-8), 4)
        self.assertLessEqual(abs(ink[2]-70), 5)
        self.assertLessEqual(abs(ink[3]-45), 5)

    def test_scene_size_mode_and_geometry_are_preserved(self):
        scene = Scene(123, 87)
        scene.line((5.25, 8.5, 105.2, 60.75), "#245b86", 2.5)
        scene.circle(45.3, 36.2, 7, "#a34d0a")
        before = deepcopy(scene)
        image = render_scene(scene)
        self.assertEqual(image.size, (123, 87))
        self.assertEqual(image.mode, "RGB")
        self.assertEqual(scene, before)

    def test_monochrome_stays_grayscale_including_antialiasing(self):
        scene = Scene(120, 80)
        scene.line((5, 20, 55, 55, 110, 22), "#000000", 2)
        scene.line((5, 45, 110, 15), "#000000", 1.5, (7, 5))
        scene.circle(75, 60, 6, "#000000")
        image = render_scene(scene)
        self.assertTrue(all(red == green == blue for red, green, blue in rgb_pixels(image)))
        self.assertTrue(any(0 < red < 255 for red, _, _ in rgb_pixels(image)))

    def test_dash_phase_continues_across_polyline_vertices(self):
        # 3-пиксельная вершина попадает внутри первого 5-пиксельного штриха.
        paths = list(_dashed_paths([(0, 0), (3, 0), (10, 0), (20, 0)], (5, 5)))
        self.assertEqual(paths[0], [(0, 0), (3, 0), (5, 0)])
        self.assertEqual(paths[1], [(10, 0), (15, 0)])
        self.assertEqual(len(paths), 2)

    def test_dash_phase_survives_corner_without_starting_again(self):
        paths = list(_dashed_paths([(0, 0), (3, 0), (3, 7)], (5, 5)))
        self.assertEqual(paths, [[(0, 0), (3, 0), (3, 2)]])

    def test_cyrillic_and_mathematical_labels_render_inside_frame(self):
        scene = Scene(260, 70)
        scene.text(130, 35, "Частица: ΔU = 0,5; γT", "#000000", font_size=16)
        image = render_scene(scene)
        bounds = ImageChops.invert(image).getbbox()
        self.assertIsNotNone(bounds)
        self.assertGreater(bounds[0], 0)
        self.assertLess(bounds[2], 260)
        self.assertGreater(bounds[1], 0)
        self.assertLess(bounds[3], 70)

    def test_invalid_supersampling_is_rejected(self):
        for scale in (0, -1, 2.5, True, 99):
            with self.subTest(scale=scale):
                with self.assertRaises(ValueError):
                    render_scene(Scene(10, 10), scale=scale)


if __name__ == "__main__":
    unittest.main()
