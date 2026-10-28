"""Интеграционные проверки настоящих Tk-виджетов на Windows/Linux.

Включение: STOCHLAB_GUI_TESTS=1; на Linux требуется DISPLAY (например Xvfb).
"""
import os
from types import SimpleNamespace
from tkinter import font as tkfont, ttk
import unittest

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

    def test_wheel_over_closed_menu_scrolls_without_changing_choice(self):
        app = self.app
        for box in (app.scheme_box, app.speed_box):
            box.focus_force()
            app.sidebar.reveal_focus(SimpleNamespace(widget=box))
            app.update()
            selected = box.current()
            before = app.sidebar.canvas.yview()
            box.event_generate("<MouseWheel>", delta=120, x=5, y=5,
                               rootx=box.winfo_rootx()+5, rooty=box.winfo_rooty()+5)
            app.update()
            self.assertEqual(box.current(), selected)
            self.assertNotEqual(app.sidebar.canvas.yview(), before)

    def test_graph_frames_reuse_one_canvas_item(self):
        app = self.app
        app._draw()
        items = [canvas.find_all() for canvas in (app.potential_canvas, app.trajectory_canvas)]
        self.assertTrue(all(len(ids) == 1 for ids in items))
        app.advance_steps(25)
        app._draw()
        self.assertEqual(items, [canvas.find_all() for canvas in (app.potential_canvas, app.trajectory_canvas)])
        for canvas in (app.potential_canvas, app.trajectory_canvas):
            self.assertEqual(canvas.type(canvas.find_all()[0]), "image")
    def test_three_button_rows_fit_inside_sidebar(self):
        app = self.app
        for language in ("ru", "en"):
            app.language = language
            app._translate()
            app.update()
            left = app.sidebar.content.winfo_rootx()
            right = left + app.sidebar.content.winfo_width()
            for widget, key in app._text_bindings:
                if key in ("low", "medium", "high", "start", "pause", "stop"):
                    self.assertTrue(widget.winfo_ismapped(), key)
                    self.assertGreaterEqual(widget.winfo_rootx(), left, key)
                    self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(), right, key)

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
        self.assertEqual(app.theory_text.get("1.0", "end").strip(), "TODO")
        app.show_page("authors")
        self.assertGreater(app.logo_image.width(), 100)
        app.toggle_language()
        self.assertEqual(app.tr("start"), "Старт")

    def test_removed_helpers_and_export_actions_are_absent(self):
        app = self.app
        removed = {"scroll_hint", "reset_hint", "units", "vertical", "horizontal",
                   "export_csv", "export_svg", "thermal", "barrier"}
        self.assertTrue(removed.isdisjoint(key for widget, key in app._text_bindings))
        for name in ("thermal_label", "barrier_label", "axis_hint", "save_csv", "save_svg", "export_csv", "export_svg"):
            self.assertFalse(hasattr(app, name), name)
        for language in ("ru", "en"):
            app.language = language
            app._translate()
            self.assertEqual(app.theory_text.get("1.0", "end").strip(), "TODO")

    def test_section_headings_are_emphasized(self):
        app = self.app
        style = ttk.Style(app)
        for key in ("parameters", "potential", "trajectory"):
            widget = next(widget for widget, text_key in app._text_bindings if text_key == key)
            font = tkfont.Font(font=style.lookup(widget.cget("style"), "font"))
            self.assertEqual(font.actual()["weight"], "bold")
            self.assertGreater(font.actual()["size"], 12)
            self.assertGreaterEqual(widget.winfo_width(), font.measure(widget.cget("text")), key)

    def test_language_switch_keeps_home_and_graph_geometry(self):
        app = self.app
        for size in ("1240x880", "900x650"):
            app.geometry(size)
            app.update()
            for page, canvases in (("home", (app.title_canvas,)),
                                   ("lab", (app.potential_canvas, app.trajectory_canvas))):
                app.show_page(page)
                app.language = "en"
                app._translate()
                app.update()
                geometry = [(c.winfo_rootx(), c.winfo_rooty(), c.winfo_width(), c.winfo_height())
                            for c in canvases]
                before = self.snapshot()
                app.sidebar.canvas.yview_moveto(.25)
                scroll = app.sidebar.canvas.yview()
                for _ in range(4):
                    app.toggle_language()
                    app.update()
                    self.assertEqual(geometry, [(c.winfo_rootx(), c.winfo_rooty(), c.winfo_width(), c.winfo_height())
                                                 for c in canvases], (size, page, app.language))
                    self.assertEqual(before, self.snapshot())
                    self.assertEqual(scroll, app.sidebar.canvas.yview())

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
