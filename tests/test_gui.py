"""Интеграционные проверки настоящих Tk-виджетов на Windows/Linux.

Включение: STOCHLAB_GUI_TESTS=1; на Linux требуется DISPLAY (например Xvfb).
"""
import csv
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET

from stochlab.app import Application
from stochlab.model import Parameters
from stochlab.texts import EN, RU


@unittest.skipUnless(os.environ.get("STOCHLAB_GUI_TESTS") == "1", "GUI tests explicitly disabled")
class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Application()
        cls.app.update()
        cls.app.report_callback_exception = cls.callback_error

    @staticmethod
    def callback_error(kind, value, traceback):
        raise value

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def setUp(self):
        app = self.app
        app.pause()
        app.geometry("1240x880")
        app.language = "ru"
        app.parameters = Parameters()
        app._sync_parameter_widgets()
        app.reset_model()
        app._translate()
        app.show_page("lab")
        app.sidebar.canvas.yview_moveto(0)
        app.update()

    def snapshot(self):
        app = self.app
        return app.model.sample(), app.model.transitions, tuple(app.history)

    def test_sidebar_scroll_does_not_move_plots_or_reset_simulation(self):
        app = self.app
        app.advance_steps(1000)
        app._draw()
        app.update()
        before = self.snapshot()
        geometry = [(c.winfo_rootx(), c.winfo_rooty(), c.winfo_width(), c.winfo_height())
                    for c in (app.potential_canvas, app.trajectory_canvas)]
        self.assertLess(app.sidebar.canvas.yview()[1], 1)
        app.sidebar.canvas.yview_moveto(1)
        app.update()
        self.assertGreater(app.sidebar.canvas.yview()[0], 0)
        self.assertEqual(geometry, [(c.winfo_rootx(), c.winfo_rooty(), c.winfo_width(), c.winfo_height())
                         for c in (app.potential_canvas, app.trajectory_canvas)])
        self.assertEqual(before, self.snapshot())

    def test_mouse_wheel_is_local_to_sidebar(self):
        app = self.app
        panel = app.sidebar.canvas
        graph = app.trajectory_canvas
        event = SimpleNamespace(x_root=panel.winfo_rootx()+20,
                                y_root=panel.winfo_rooty()+80, delta=-120, num=0)
        app.sidebar.scroll_mouse(event)
        self.assertGreater(panel.yview()[0], 0)
        before = panel.yview()
        event.x_root, event.y_root = graph.winfo_rootx()+20, graph.winfo_rooty()+20
        app.sidebar.scroll_mouse(event)
        self.assertEqual(before, panel.yview())

    def test_scheme_and_rotation_preserve_history(self):
        app = self.app
        app.advance_steps(2000)
        before = self.snapshot()
        for scheme in ("states", "monochrome", "quantities"):
            app.set_scheme(scheme)
            app.rotate()
            app.update()
            self.assertEqual(before, self.snapshot())
        self.assertTrue(app._scenes)

    def test_parameters_reset_but_invalid_values_are_rejected(self):
        app = self.app
        app.advance_steps(50)
        app.parameter_vars["T"].set("0,3")
        self.assertTrue(app.apply_parameters())
        self.assertEqual(app.parameters.T, .3)
        self.assertEqual(app.model.t, 0)
        app.parameter_vars["b"].set("0")
        self.assertFalse(app.apply_parameters())
        self.assertEqual(app.parameters.b, .5)
        self.assertTrue(app.notice_label.cget("text"))
        app.drive_var.set(False)
        self.assertTrue(app.apply_parameters())
        self.assertEqual(str(app.parameter_entries["f"].cget("state")), "disabled")
        self.assertEqual(app.model.sample().force, 0)

    def test_start_pause_stop(self):
        app = self.app
        app.start()
        self.assertTrue(app.running)
        app.advance_steps(250)
        app.pause()
        self.assertFalse(app.running)
        self.assertGreater(app.model.t, 0)
        app.stop()
        self.assertEqual(app.model.t, 0)
        self.assertEqual(len(app.history), 1)

    def test_translations_theory_and_logo(self):
        app = self.app
        self.assertEqual(set(RU), set(EN))
        app.advance_steps(150)
        before = self.snapshot()
        app.toggle_language()
        app.update()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(app.tr("start"), "Start")
        app.show_page("theory")
        self.assertIn("Equations of motion", app.theory_text.get("1.0", "end"))
        self.assertNotIn("Kramers", app.theory_text.get("1.0", "end"))
        app.show_page("authors")
        self.assertGreater(app.logo_image.width(), 100)
        app.toggle_language()
        self.assertEqual(app.tr("start"), "Старт")

    def test_exports_include_current_appearance_and_physical_parameters(self):
        app = self.app
        app.advance_steps(1000)
        app.set_scheme("monochrome")
        before = self.snapshot()
        with tempfile.TemporaryDirectory() as directory:
            svg = Path(directory) / "graphs.svg"
            csv_path = Path(directory) / "trajectory.csv"
            app.save_svg(svg)
            app.save_csv(csv_path)
            tree = ET.parse(svg)
            self.assertTrue(any("stroke-dasharray" in e.attrib for e in tree.iter()))
            self.assertNotIn("#a34d0a", svg.read_text())
            text = csv_path.read_text(encoding="utf-8-sig")
            self.assertIn("# T=0.22", text)
            rows = list(csv.reader(line for line in text.splitlines() if not line.startswith("#")))
            self.assertEqual(rows[0], ["t", "x", "v", "force"])
            self.assertGreater(len(rows), 10)
        self.assertEqual(before, self.snapshot())

    def test_small_window_and_keyboard_access_to_bottom(self):
        app = self.app
        app.geometry("900x650")
        app.update()
        app.scheme_box.focus_force()
        app.sidebar.reveal_focus(SimpleNamespace(widget=app.scheme_box))
        app.update()
        y = app.scheme_box.winfo_rooty()
        canvas = app.sidebar.canvas
        self.assertGreaterEqual(y, canvas.winfo_rooty())
        self.assertLess(y+app.scheme_box.winfo_height(), canvas.winfo_rooty()+canvas.winfo_height()+2)
        for graph in (app.potential_canvas, app.trajectory_canvas):
            self.assertGreater(graph.winfo_width(), 400)
            self.assertGreater(graph.winfo_height(), 100)


if __name__ == "__main__":
    unittest.main()
