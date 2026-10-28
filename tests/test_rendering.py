"""Проверки растеризации: края сглаживаются, геометрия не меняется."""
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from PIL import ImageChops

from stochlab.plotting import Scene
from stochlab.rendering import _dashed_paths, render_scene


def rgb_pixels(image):
    """Читает RGB-пиксели без зависимости от меняющегося API getdata."""
    data = image.tobytes()
    for index in range(0, len(data), 3):
        yield tuple(data[index:index+3])


class RenderingTests(unittest.TestCase):
    def test_renderer_imports_when_aggdraw_is_missing_or_unloadable(self):
        # Отдельный процесс воспроизводит запуск обновлённых исходников:
        # модуль ещё не попадал в кэш импортов и отсутствует либо не грузит DLL.
        for error in ("ModuleNotFoundError", "OSError"):
            with self.subTest(error=error):
                script = f"""
import sys
class MissingAggdraw:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'aggdraw':
            raise {error}('Simulated unavailable aggdraw')
sys.meta_path.insert(0, MissingAggdraw())
from stochlab.rendering import aggdraw, render_scene
from stochlab.plotting import Scene
from PIL import ImageChops
assert aggdraw is None
scene = Scene(100, 80)
scene.line((10, 10, 90, 70), '#000000', 2)
assert ImageChops.invert(render_scene(scene)).getbbox() is not None
"""
                result = subprocess.run([sys.executable, "-c", script],
                                        cwd=Path(__file__).resolve().parent.parent,
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_pillow_fallback_preserves_geometry_text_dashes_and_color(self):
        scene = Scene(200, 120)
        scene.text(100, 22, "Частица x²", "#000000", font_size=16)
        scene.line((10, 60, 190, 60), "#000000", 2, (12, 12))
        scene.circle(100, 95, 7, "#245b86")
        before = deepcopy(scene)
        with patch("stochlab.rendering.aggdraw", None):
            image = render_scene(scene)
        self.assertEqual(image.size, (200, 120))
        self.assertEqual(scene, before)
        self.assertIsNotNone(ImageChops.invert(image.crop((0, 0, 200, 40))).getbbox())
        self.assertEqual(image.getpixel((100, 95)), (36, 91, 134))
        self.assertEqual(image.getpixel((16, 60)), (0, 0, 0))
        self.assertEqual(image.getpixel((28, 60)), (255, 255, 255))
        self.assertTrue(any(0 < red < 255 for red, _, _ in rgb_pixels(image)))

    def test_diagonal_has_native_subpixel_coverage(self):
        scene = Scene(80, 60)
        scene.line((8.25, 8.1, 70.4, 45.2), "#000000", 1.4)
        image = render_scene(scene, scale=1)
        shades = {pixel[0] for pixel in rgb_pixels(image)}
        self.assertTrue(any(0 < value < 255 for value in shades))
        self.assertGreater(len(shades), 10)
        # Покрытие края не должно размывать линию на несколько пикселей.
        ink = ImageChops.invert(image).getbbox()
        self.assertLessEqual(abs(ink[0]-8.25), 2)
        self.assertLessEqual(abs(ink[1]-8.1), 2)
        self.assertLessEqual(abs(ink[2]-70.4), 2)
        self.assertLessEqual(abs(ink[3]-45.2), 2)

    def test_fractional_line_motion_changes_each_frame(self):
        centers = []
        for index in range(9):
            x = 30 + index/8
            scene = Scene(80, 60)
            scene.line((x, 8, x, 52), "#000000", 1.4)
            image = render_scene(scene, scale=1)
            weights = [sum(255-image.getpixel((column, row))[0]
                           for row in range(15, 45)) for column in range(80)]
            centers.append(sum(column*weight for column, weight in enumerate(weights))/sum(weights))
        # Для штриха уже двух пикселей первый момент по центрам пикселей
        # слегка нелинеен. Требуем реакции на каждый малый шаг без ступенек:
        # прежний 2×-рендер давал здесь шесть нулей и скачок 0,668 пикселя.
        for first, second in zip(centers, centers[1:]):
            self.assertGreater(second-first, .075)
            self.assertLess(second-first, .2)
        self.assertAlmostEqual(centers[-1]-centers[0], 1, places=5)

    def test_thin_line_has_no_distant_resampling_halo(self):
        scene = Scene(80, 60)
        scene.line((30.25, 8, 30.25, 52), "#000000", 1.4)
        image = render_scene(scene, scale=1)
        for x in range(80):
            if x < 28 or x > 32:
                for y in range(12, 48):
                    self.assertEqual(image.getpixel((x, y)), (255, 255, 255))

    def test_labels_survive_geometry_drawn_after_them(self):
        label = Scene(180, 80)
        label.text(90, 25, "Температура T", "#000000", font_size=16)
        expected = render_scene(label, scale=1)
        label.line((10, 65, 170, 65), "#245b86", 2)
        actual = render_scene(label, scale=1)
        self.assertIsNone(ImageChops.difference(expected.crop((0, 0, 180, 50)),
                                               actual.crop((0, 0, 180, 50))).getbbox())

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
