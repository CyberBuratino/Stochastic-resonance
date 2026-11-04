"""Интеграционные проверки настоящих Tk-виджетов на Windows/Linux.

Включение: STOCHLAB_GUI_TESTS=1; на Linux требуется DISPLAY (например Xvfb).
"""
import os
import math
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from tkinter import font as tkfont, ttk
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops, ImageTk

from stochlab.app import Application
from stochlab.model import Parameters
from stochlab import appearance
from stochlab.presets import DEMONSTRATION_SPEED, RESONANCE_PARAMETERS
from stochlab.texts import EN, RU


@unittest.skipUnless(os.environ.get("STOCHLAB_GUI_TESTS") == "1", "GUI tests explicitly disabled")
class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Application()
        cls.app.report_callback_exception = cls.callback_error
        cls.app.update()

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
        app.set_history_periods(appearance.DEFAULT_HISTORY_PERIODS)
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

    def test_all_pictures_render_without_aggdraw_and_update_during_simulation(self):
        app = self.app

        def check_frame(canvas):
            items = canvas.find_all()
            self.assertEqual(len(items), 1)
            self.assertEqual(canvas.type(items[0]), "image")
            image = ImageTk.getimage(canvas._scene_photo).convert("RGB")
            self.assertEqual(image.size, (canvas.winfo_width(), canvas.winfo_height()))
            background = Image.new("RGB", image.size, canvas.cget("background"))
            histogram = ImageChops.difference(image, background).convert("L").histogram()
            self.assertGreater(sum(histogram[1:]), 100)
            return image

        with patch("stochlab.rendering.aggdraw", None):
            app.show_page("home")
            app.update()
            check_frame(app.title_canvas)
            app.show_page("lab")
            app.advance_steps(1000)
            app.update()
            check_frame(app.potential_canvas)
            first = check_frame(app.trajectory_canvas)
            app.advance_steps(1000)
            app.request_draw()
            app.update()
            second = check_frame(app.trajectory_canvas)
            self.assertIsNotNone(ImageChops.difference(first, second).getbbox())
            before = self.snapshot()
            app.rotate()
            app.set_scheme("monochrome")
            app.toggle_language()
            app.update()
            check_frame(app.potential_canvas)
            check_frame(app.trajectory_canvas)
            self.assertEqual(before, self.snapshot())

    def test_source_startup_without_aggdraw_displays_all_three_pictures(self):
        # Тот же вход, что у start-windows.bat, в свежем процессе Python.
        script = """
import runpy
import sys
sys.modules['aggdraw'] = None
sys.argv = ['main.py', '--smoke-test-gui']
runpy.run_path('main.py', run_name='__main__')
"""
        result = subprocess.run([sys.executable, "-c", script],
                                cwd=Path(__file__).resolve().parent.parent,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("nonblank home illustration and both graph frames", result.stdout)

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
        for box in (app.scheme_box, app.speed_box, app.history_box):
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
    def test_parameter_buttons_fit_inside_sidebar(self):
        app = self.app
        for language in ("ru", "en"):
            app.language = language
            app._translate()
            app.update()
            left = app.sidebar.winfo_rootx()
            right = left + app.sidebar.winfo_width()
            for widget, key in app._text_bindings:
                if key in ("low", "medium", "high", "start", "pause", "stop", "resonance"):
                    self.assertTrue(widget.winfo_ismapped(), key)
                    self.assertGreaterEqual(widget.winfo_rootx(), left, key)
                    self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(), right, key)

    def test_transport_stays_visible_above_scrolling_parameters(self):
        app = self.app
        for size in ("1240x880", "900x650"):
            app.geometry(size)
            app.update()
            buttons = [widget for widget, key in app._text_bindings
                       if key in ("start", "pause", "stop", "resonance")]
            before = [(button.winfo_rootx(), button.winfo_rooty()) for button in buttons]
            app.sidebar.canvas.yview_moveto(1)
            app.update()
            scroll = app.sidebar.canvas.yview()
            app.start_button.focus_force()
            app.update()
            self.assertEqual(scroll, app.sidebar.canvas.yview())
            self.assertEqual(before, [(b.winfo_rootx(), b.winfo_rooty()) for b in buttons])
            for button in buttons:
                self.assertGreaterEqual(button.winfo_rooty(), app.sidebar.winfo_rooty())
                self.assertLessEqual(button.winfo_rooty()+button.winfo_height(), app.sidebar.canvas.winfo_rooty())

    def test_resonance_button_recovers_all_parameters_and_reproduces_trajectory(self):
        app = self.app
        app.parameters = Parameters(T=1.1, a=0, b=0, drive_enabled=False,
                                    f=0, omega=.02, gamma=3, dt=.04, seed=99)
        app._sync_parameter_widgets()
        app.reset_model()
        app.advance_steps(50)
        app._slider_changed("b", "0")
        app.parameter_vars["T"].set("invalid")
        app.notice_label.configure(text=app.tr("error"))
        app.resonance_button.invoke()
        self.assertTrue(app.running)
        app.pause()
        self.assertEqual(app.current_page, "lab")
        self.assertEqual(app.parameters, RESONANCE_PARAMETERS)
        self.assertEqual(app.speed, DEMONSTRATION_SPEED)
        self.assertIsNone(app._pending_apply)
        self.assertEqual(app.notice_label.cget("text"), "")
        self.assertEqual(app.model.t, 0)
        self.assertEqual(len(app.history), 1)
        for name, variable in app.parameter_vars.items():
            self.assertEqual(float(variable.get()), getattr(RESONANCE_PARAMETERS, name))
        self.assertTrue(app.drive_var.get())
        self.assertEqual(str(app.parameter_entries["f"].cget("state")), "normal")
        app.advance_steps(1000)
        before = self.snapshot()
        app.resonance_button.invoke()
        app.pause()
        app.advance_steps(1000)
        self.assertEqual(before, self.snapshot())

    def test_large_button_text_fits_on_both_languages_at_minimum_window(self):
        app = self.app
        app.geometry("900x650")
        style = ttk.Style(app)
        for page in ("lab", "home"):
            app.show_page(page)
            for language in ("ru", "en"):
                app.language = language
                app._translate()
                app.update()
                buttons = [(widget, key) for widget, key in app._text_bindings
                           if isinstance(widget, (ttk.Button, ttk.Checkbutton))]
                buttons.append((app.language_button, "language"))
                for button, key in buttons:
                    if not button.winfo_ismapped():
                        continue
                    name = button.cget("style") or button.winfo_class()
                    font = tkfont.Font(font=style.lookup(name, "font"))
                    self.assertGreater(font.actual()["size"], appearance.BODY_FONT_SIZE, key)
                    self.assertGreaterEqual(button.winfo_width(), font.measure(button.cget("text"))+20, key)
                    self.assertGreaterEqual(button.winfo_rootx(), app.winfo_rootx(), key)
                    self.assertLessEqual(button.winfo_rootx()+button.winfo_width(), app.winfo_rootx()+app.winfo_width(), key)

    def test_longer_window_is_immediately_available_on_pause_and_preserves_state(self):
        app = self.app
        app.parameters = RESONANCE_PARAMETERS
        app._sync_parameter_widgets()
        app.reset_model()
        period = 2*math.pi/app.parameters.omega
        app.advance_steps(math.ceil(8*period/app.parameters.dt))
        # Несмотря на выбранные 3 периода, в буфере уже есть последние 6.
        self.assertEqual(app.history_periods, 3)
        self.assertGreaterEqual(app.history[0].t, app.model.t-6*period)
        self.assertLess(app.history[0].t, app.model.t-5.9*period)
        self.assertLessEqual(len(app.history), math.ceil(6*period/(5*app.parameters.dt))+1)
        before = self.snapshot()
        for periods in (6, 3, 6):
            app.history_box.current(appearance.HISTORY_PERIOD_OPTIONS.index(periods))
            app.history_box.event_generate("<<ComboboxSelected>>")
            app.update()
            self.assertEqual(app.history_periods, periods)
            self.assertFalse(app.running)
            self.assertEqual(before, self.snapshot())
        app.rotate()
        app.set_scheme("states")
        app.toggle_language()
        app.update()
        self.assertEqual(app.history_box.get(), "6 driving periods")
        self.assertEqual(app.history_periods, 6)
        self.assertEqual(before, self.snapshot())

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
                   "export_csv", "export_svg", "thermal", "barrier", "seed"}
        self.assertTrue(removed.isdisjoint(key for widget, key in app._text_bindings))
        for name in ("thermal_label", "barrier_label", "axis_hint", "save_csv", "save_svg", "export_csv", "export_svg", "seed_var"):
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
