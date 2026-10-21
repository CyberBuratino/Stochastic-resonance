"""Окно приложения и обработчики кнопок.

Этот файл связывает интерфейс с моделью. Оформление вынесено в appearance.py,
надписи — в texts.py, рисунки — в plotting.py. Численный метод здесь не описан.
"""
from collections import deque
from dataclasses import asdict
import csv
import math
from pathlib import Path
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import xml.etree.ElementTree as ET

from . import appearance as visual
from .model import (Model, Parameters, PARAMETER_LIMITS, barrier_height,
                    critical_force, noise_intensity)
from .plotting import potential_scene, title_scene, trajectory_scene
from .texts import EN, RU, THEORY_EN, THEORY_RU


# Описание полей: имя в модели, ключ перевода, шаг ползунка.
PARAMETER_FIELDS = [
    ("T", "temperature", 0.01), ("a", "a", 0.01), ("b", "b", 0.01),
    ("f", "f", 0.01), ("omega", "omega", 0.005), ("gamma", "gamma", 0.01),
]
FRAME_MILLISECONDS = 50
SAMPLES_EVERY_STEPS = 5


class ScrollablePanel(ttk.Frame):
    """Прокрутка меняет только содержимое панели, не положение графиков."""

    def __init__(self, parent):
        super().__init__(parent, style="Panel.TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, width=visual.SIDEBAR_WIDTH, highlightthickness=0,
                                background=visual.UI_COLORS["panel"])
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.content = ttk.Frame(self.canvas, padding=visual.PANEL_PADDING, style="Panel.TFrame")
        self.window = self.canvas.create_window(0, 0, window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._update_region)
        self.canvas.bind("<Configure>", self._update_width)

    def _update_region(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _update_width(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)

    def contains(self, widget):
        while widget is not None:
            if widget is self:
                return True
            widget = getattr(widget, "master", None)
        return False

    def reveal_focus(self, event):
        """При переходе Tab выбранное поле остаётся видимым в панели."""
        widget = event.widget
        if not self.contains(widget) or widget is self.canvas:
            return
        self.update_idletasks()
        top = self.canvas.canvasy(0)
        y = widget.winfo_rooty() - self.content.winfo_rooty()
        bottom = y + widget.winfo_height()
        height = self.canvas.winfo_height()
        total = max(1, self.content.winfo_height())
        if y < top:
            self.canvas.yview_moveto(max(0, y - 8) / total)
        elif bottom > top + height:
            self.canvas.yview_moveto((bottom - height + 8) / total)

    def scroll_mouse(self, event):
        # У Tkinter событие колёсика зависит от ОС. Проверяем положение курсора:
        # над графиками или другими страницами боковая панель не прокручивается.
        try:
            under_pointer = self.winfo_containing(event.x_root, event.y_root)
        except KeyError:
            # Внутренний список раскрытого ttk.Combobox создан самим Tcl.
            # У него нет Python-виджета; его прокруткой занимается Tk.
            return None
        if not self.contains(under_pointer):
            return None
        if getattr(event, "num", None) in (4, 5):
            units = -3 if event.num == 4 else 3
        else:
            delta = getattr(event, "delta", 0)
            units = -max(1, abs(int(delta / 120))) * (1 if delta > 0 else -1)
        self.canvas.yview_scroll(units, "units")
        return "break"


class Application(tk.Tk):
    def __init__(self, logo_path=None):
        super().__init__()
        self.geometry("1240x880")
        self.minsize(900, 650)
        self.configure(background=visual.UI_COLORS["background"])
        self.language = "ru"
        self.scheme = "quantities"
        self.vertical = True
        self.running = False
        self.current_page = "home"
        self.parameters = Parameters()
        self.model = Model(self.parameters)
        self.history = deque([self.model.sample()])
        self.speed = "slow"
        self._last_clock = time.monotonic()
        self._fractional_steps = 0.0
        self._pending_apply = None
        self._updating_controls = False
        self._render_pending = False
        self._text_bindings = []
        self._scenes = []
        self._configure_styles()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self._build_header()
        self.container = ttk.Frame(self, padding=(20, 12, 20, 16))
        self.container.grid(row=2, column=0, sticky="nsew")
        self.container.rowconfigure(0, weight=1)
        self.container.columnconfigure(0, weight=1)
        self.pages = {}
        self._build_home()
        self._build_lab()
        self._build_theory()
        self._build_authors(logo_path)
        self.bind_all("<MouseWheel>", self.sidebar.scroll_mouse)
        self.bind_all("<Button-4>", self.sidebar.scroll_mouse)
        self.bind_all("<Button-5>", self.sidebar.scroll_mouse)
        self.bind_all("<FocusIn>", self.sidebar.reveal_focus)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._translate()
        self.show_page("home")
        self.after(FRAME_MILLISECONDS, self._tick)

    def tr(self, key):
        return (RU if self.language == "ru" else EN)[key]

    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        colors = visual.UI_COLORS
        body_font = (visual.FONT_FAMILY, visual.BODY_FONT_SIZE)
        style.configure(".", font=body_font, background=colors["background"], foreground=colors["text"])
        style.configure("TFrame", background=colors["background"])
        style.configure("TLabel", background=colors["background"])
        style.configure("Panel.TFrame", background=colors["panel"])
        style.configure("Panel.TLabel", background=colors["panel"])
        style.configure("Hint.TLabel", background=colors["panel"], foreground=colors["muted"],
                        font=(visual.FONT_FAMILY, visual.SMALL_FONT_SIZE))
        style.configure("Title.TLabel", font=(visual.FONT_FAMILY, visual.TITLE_FONT_SIZE, "bold"))
        style.configure("Heading.TLabel", font=(visual.FONT_FAMILY, visual.HEADING_FONT_SIZE, "bold"))
        style.configure("TButton", padding=(9, 7), background=colors["button"])
        style.configure("Panel.TCheckbutton", background=colors["panel"])
        style.map("TButton", background=[("active", "#e6edf4")])
        style.configure("TEntry", fieldbackground="white")
        style.configure("TCombobox", fieldbackground="white")
        style.map("TCombobox", fieldbackground=[("readonly", "white")])

    def _bind_text(self, widget, key):
        self._text_bindings.append((widget, key))
        return widget

    def _label(self, parent, key, **options):
        return self._bind_text(ttk.Label(parent, **options), key)

    def _button(self, parent, key, command, **options):
        return self._bind_text(ttk.Button(parent, command=command, **options), key)

    def _new_page(self, name):
        page = ttk.Frame(self.container)
        page.grid(row=0, column=0, sticky="nsew")
        self.pages[name] = page
        return page

    def _build_header(self):
        self.header = ttk.Frame(self, padding=(20, 8))
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.columnconfigure(0, weight=1)
        self.brand = self._label(self.header, "title")
        self.brand.grid(row=0, column=0, sticky="w")
        self.language_button = ttk.Button(self.header, width=5, command=self.toggle_language)
        self.language_button.grid(row=0, column=1, sticky="e")
        self.navigation = ttk.Frame(self, padding=(20, 4))
        self.navigation.grid(row=1, column=0, sticky="ew")
        for index, name in enumerate(("home", "lab", "theory", "authors")):
            self._button(self.navigation, name, lambda page=name: self.show_page(page)).grid(row=0, column=index, padx=(0, 8))
        self.navigation.columnconfigure(4, weight=1)
        self._button(self.navigation, "exit", self.destroy).grid(row=0, column=5, sticky="e")

    def _build_home(self):
        page = self._new_page("home")
        page.columnconfigure(0, weight=1)
        page.columnconfigure(1, weight=1)
        page.rowconfigure(0, weight=1)
        left = ttk.Frame(page, padding=20)
        left.grid(row=0, column=0, sticky="ew")
        self.home_title = self._label(left, "title", style="Title.TLabel", wraplength=490)
        self.home_title.pack(anchor="w", pady=(0, 24))
        for name in ("lab", "theory", "authors"):
            self._button(left, name, lambda target=name: self.show_page(target)).pack(anchor="w", pady=5)
        self.title_canvas = tk.Canvas(page, background="white", highlightthickness=0)
        self.title_canvas.grid(row=0, column=1, sticky="nsew")
        self.title_canvas.bind("<Configure>", self.request_draw)

    def _build_lab(self):
        page = self._new_page("lab")
        page.columnconfigure(1, weight=1)
        page.rowconfigure(0, weight=1)
        self.sidebar = ScrollablePanel(page)
        self.sidebar.grid(row=0, column=0, sticky="ns", padx=(0, 18))
        controls = self.sidebar.content
        controls.columnconfigure(0, weight=1)
        self._label(controls, "parameters", style="Panel.TLabel").pack(anchor="w", pady=(0, 12))
        self._label(controls, "scroll_hint", style="Hint.TLabel", wraplength=260).pack(fill="x", pady=(0, 14))
        self.parameter_vars = {}
        self.parameter_entries = {}
        self.parameter_scales = {}
        for name, key, resolution in PARAMETER_FIELDS:
            group = ttk.Frame(controls, style="Panel.TFrame")
            group.pack(fill="x", pady=(0, 10))
            self._label(group, key, style="Panel.TLabel").pack(anchor="w")
            variable = tk.StringVar(value=str(getattr(self.parameters, name)))
            entry = ttk.Entry(group, textvariable=variable, width=12)
            entry.pack(fill="x", pady=4)
            entry.bind("<Return>", self.apply_parameters)
            entry.bind("<FocusOut>", self.apply_parameters)
            minimum, maximum = PARAMETER_LIMITS[name]
            scale = tk.Scale(group, from_=minimum, to=maximum, resolution=resolution,
                             orient="horizontal", showvalue=False, highlightthickness=0,
                             background=visual.UI_COLORS["panel"],
                             command=lambda value, field=name: self._slider_changed(field, value))
            scale.pack(fill="x")
            self.parameter_vars[name] = variable
            self.parameter_entries[name] = entry
            self.parameter_scales[name] = scale
        self.drive_var = tk.BooleanVar(value=self.parameters.drive_enabled)
        self.drive_button = self._bind_text(ttk.Checkbutton(controls, variable=self.drive_var,
                                        command=self.apply_parameters, style="Panel.TCheckbutton"), "drive")
        self.drive_button.pack(anchor="w", pady=(6, 12))
        self.thermal_label = ttk.Label(controls, style="Hint.TLabel", wraplength=260)
        self.thermal_label.pack(fill="x", pady=(0, 10))
        self.barrier_label = ttk.Label(controls, style="Hint.TLabel", wraplength=260)
        self.barrier_label.pack(fill="x", pady=(0, 14))
        self._label(controls, "seed", style="Panel.TLabel").pack(anchor="w")
        self.seed_var = tk.StringVar(value=str(self.parameters.seed))
        seed_entry = ttk.Entry(controls, textvariable=self.seed_var)
        seed_entry.pack(fill="x", pady=(4, 12))
        seed_entry.bind("<Return>", self.apply_parameters)
        seed_entry.bind("<FocusOut>", self.apply_parameters)
        presets = ttk.Frame(controls, style="Panel.TFrame")
        presets.pack(fill="x", pady=(0, 14))
        for key, value in (("low", .025), ("medium", .22), ("high", 1.1)):
            self._button(presets, key, lambda temperature=value: self.set_temperature(temperature)).pack(side="left", expand=True, fill="x")
        self._label(controls, "appearance", style="Panel.TLabel").pack(anchor="w")
        self.scheme_box = ttk.Combobox(controls, state="readonly")
        self.scheme_box.pack(fill="x", pady=(4, 14))
        self.scheme_box.bind("<<ComboboxSelected>>", self._scheme_selected)
        self._label(controls, "speed", style="Panel.TLabel").pack(anchor="w")
        self.speed_box = ttk.Combobox(controls, state="readonly")
        self.speed_box.pack(fill="x", pady=(4, 12))
        self.speed_box.bind("<<ComboboxSelected>>", self._speed_selected)
        # Перехватываем колёсико до стандартного обработчика Combobox:
        # прокрутка панели не должна незаметно менять цвет или скорость.
        for box in (self.scheme_box, self.speed_box):
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                box.bind(sequence, self.sidebar.scroll_mouse)
        transport = ttk.Frame(controls, style="Panel.TFrame")
        transport.pack(fill="x", pady=(0, 12))
        for key, command in (("start", self.start), ("pause", self.pause), ("stop", self.stop)):
            button = self._button(transport, key, command)
            button.pack(side="left", expand=True, fill="x")
            if key == "pause":
                self.pause_button = button
        self._button(controls, "export_csv", self.export_csv).pack(fill="x", pady=(0, 6))
        self._button(controls, "export_svg", self.export_svg).pack(fill="x", pady=(0, 12))
        self._label(controls, "reset_hint", style="Hint.TLabel", wraplength=260).pack(fill="x", pady=(0, 12))
        self.notice_label = ttk.Label(controls, style="Hint.TLabel", wraplength=260)
        self.notice_label.pack(fill="x")
        # Эта колонка не входит в прокручиваемую область.
        field = ttk.Frame(page)
        field.grid(row=0, column=1, sticky="nsew")
        field.columnconfigure(0, weight=1)
        field.rowconfigure(2, weight=1)
        field.rowconfigure(5, weight=2)
        heading = ttk.Frame(field)
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        heading.columnconfigure(0, weight=1)
        self._label(heading, "potential").grid(row=0, column=0, sticky="w")
        self.status_label = ttk.Label(heading)
        self.status_label.grid(row=0, column=1, sticky="e")
        self.statistics_label = ttk.Label(field)
        self.statistics_label.grid(row=1, column=0, sticky="w")
        self.potential_canvas = tk.Canvas(field, background="white", highlightthickness=0, height=200)
        self.potential_canvas.grid(row=2, column=0, sticky="nsew")
        trajectory_header = ttk.Frame(field)
        trajectory_header.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        trajectory_header.columnconfigure(0, weight=1)
        self._label(trajectory_header, "trajectory").grid(row=0, column=0, sticky="w")
        self._button(trajectory_header, "rotate", self.rotate).grid(row=0, column=1, sticky="e")
        self.axis_hint = ttk.Label(field, font=(visual.FONT_FAMILY, visual.SMALL_FONT_SIZE))
        self.axis_hint.grid(row=4, column=0, sticky="w", pady=4)
        self.trajectory_canvas = tk.Canvas(field, background="white", highlightthickness=0, height=300)
        self.trajectory_canvas.grid(row=5, column=0, sticky="nsew")
        self._label(field, "units", font=(visual.FONT_FAMILY, visual.SMALL_FONT_SIZE)).grid(row=6, column=0, sticky="w")
        for canvas in (self.potential_canvas, self.trajectory_canvas):
            canvas.bind("<Configure>", self.request_draw)
        self._sync_parameter_widgets()

    def _build_theory(self):
        page = self._new_page("theory")
        page.rowconfigure(0, weight=1)
        page.columnconfigure(0, weight=1)
        self.theory_text = tk.Text(page, wrap="word", borderwidth=0, highlightthickness=0,
                                  background="white", foreground=visual.UI_COLORS["text"],
                                  padx=24, pady=16, font=(visual.FONT_FAMILY, visual.BODY_FONT_SIZE),
                                  spacing3=15)
        scrollbar = ttk.Scrollbar(page, orient="vertical", command=self.theory_text.yview)
        self.theory_text.configure(yscrollcommand=scrollbar.set)
        self.theory_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.theory_text.tag_configure("heading", font=(visual.FONT_FAMILY, 18, "bold"), spacing1=18, spacing3=12)
        self.theory_text.tag_configure("formula", font=(visual.FONT_FAMILY, 18), background="#f3f5f7", spacing1=10, spacing3=20)
        self.theory_text.tag_configure("body", spacing3=16)

    def _build_authors(self, logo_path):
        page = self._new_page("authors")
        content = ttk.Frame(page, padding=24)
        content.pack(anchor="nw")
        self._label(content, "authors", style="Heading.TLabel").pack(anchor="w", pady=(0, 18))
        path = Path(logo_path) if logo_path else Path(__file__).resolve().parent.parent / "assets" / "vmk-logo.png"
        self.logo_image = tk.PhotoImage(file=str(path)).subsample(2, 2)
        ttk.Label(content, image=self.logo_image).pack(anchor="w", pady=(0, 18))
        self._label(content, "author_names", font=(visual.FONT_FAMILY, 18, "bold")).pack(anchor="w", pady=(0, 18))
        self._label(content, "faculty").pack(anchor="w", pady=(0, 18))
        self._label(content, "teacher").pack(anchor="w")

    def _translate(self):
        self.title(self.tr("title"))
        self.language_button.configure(text="EN" if self.language == "ru" else "RU")
        for widget, key in self._text_bindings:
            widget.configure(text=self.tr(key))
        self.scheme_box.configure(values=[visual.SCHEME_LABELS[key][self.language] for key in visual.SCHEMES])
        self.scheme_box.current(list(visual.SCHEMES).index(self.scheme))
        self.speed_box.configure(values=[self.tr("slow"), self.tr("fast")])
        self.speed_box.current(0 if self.speed == "slow" else 1)
        self.theory_text.configure(state="normal")
        self.theory_text.delete("1.0", "end")
        for kind, text in (THEORY_RU if self.language == "ru" else THEORY_EN):
            self.theory_text.insert("end", text + "\n\n", kind)
        self.theory_text.configure(state="disabled")
        self._update_labels()
        self.request_draw()

    def toggle_language(self):
        self.language = "en" if self.language == "ru" else "ru"
        self._translate()

    def show_page(self, name):
        if name != "lab":
            self.running = False
        self.current_page = name
        for page_name, page in self.pages.items():
            if page_name == name:
                page.grid()
            else:
                page.grid_remove()
        if name == "home":
            self.navigation.grid_remove()
            self.brand.grid_remove()
        else:
            self.navigation.grid()
            self.brand.grid()
        self._update_labels()
        self.request_draw()

    def _sync_parameter_widgets(self):
        self._updating_controls = True
        try:
            for name, variable in self.parameter_vars.items():
                value = getattr(self.parameters, name)
                variable.set(f"{value:g}")
                self.parameter_scales[name].set(value)
            if hasattr(self, "seed_var"):
                self.seed_var.set(str(self.parameters.seed))
            if hasattr(self, "drive_var"):
                self.drive_var.set(self.parameters.drive_enabled)
        finally:
            self._updating_controls = False

    def _slider_changed(self, name, value):
        if self._updating_controls:
            return
        self.parameter_vars[name].set(value)
        if self._pending_apply is not None:
            self.after_cancel(self._pending_apply)
        # Один сброс после короткой паузы, а не сотни сбросов при движении мыши.
        self._pending_apply = self.after(150, self.apply_parameters)

    def apply_parameters(self, _event=None):
        if self._pending_apply is not None:
            self.after_cancel(self._pending_apply)
            self._pending_apply = None
        try:
            values = {name: float(variable.get().replace(",", "."))
                      for name, variable in self.parameter_vars.items()}
            candidate = Parameters(**values, seed=int(self.seed_var.get()),
                                   drive_enabled=self.drive_var.get())
        except (ValueError, OverflowError):
            self.notice_label.configure(text=self.tr("invalid"))
            self._sync_parameter_widgets()
            return False
        if candidate != self.parameters:
            self.parameters = candidate
            self.reset_model()
        self._sync_parameter_widgets()
        self._update_labels()
        return True

    def set_temperature(self, value):
        self.parameter_vars["T"].set(str(value))
        self.apply_parameters()

    def set_scheme(self, key):
        if key not in visual.SCHEMES:
            raise ValueError(key)
        self.scheme = key
        self.scheme_box.current(list(visual.SCHEMES).index(key))
        self.request_draw()

    def _scheme_selected(self, _event=None):
        self.set_scheme(list(visual.SCHEMES)[self.scheme_box.current()])

    def _speed_selected(self, _event=None):
        self.speed = "slow" if self.speed_box.current() == 0 else "fast"

    def start(self):
        if self.apply_parameters():
            self.running = True
            self._last_clock = time.monotonic()
            self._update_labels()

    def pause(self):
        self.running = False
        self._update_labels()

    def stop(self):
        self.running = False
        self.reset_model()

    def reset_model(self):
        self.model = Model(self.parameters)
        self.history = deque([self.model.sample()])
        self._fractional_steps = 0.0
        self.notice_label.configure(text="")
        self._update_labels()
        self.request_draw()

    def rotate(self):
        self.vertical = not self.vertical
        self._update_labels()
        self.request_draw()

    def advance_steps(self, count):
        """Отдельный метод нужен для проверки интерфейса без ожидания таймера."""
        for _ in range(count):
            self.model.step()
            if self.model.steps % SAMPLES_EVERY_STEPS == 0:
                self.history.append(self.model.sample())
        cutoff = self.model.t - 6 * math.pi / self.parameters.omega
        while len(self.history) > 1 and self.history[0].t < cutoff:
            self.history.popleft()

    def _tick(self):
        now = time.monotonic()
        elapsed = min(now - self._last_clock, 0.15)
        self._last_clock = now
        if self.running and self.current_page == "lab":
            steps_per_second = 100 if self.speed == "slow" else 1500
            self._fractional_steps += elapsed * steps_per_second
            steps = int(self._fractional_steps)
            self._fractional_steps -= steps
            try:
                self.advance_steps(steps)
            except (ArithmeticError, ValueError):
                self.running = False
                self.notice_label.configure(text=self.tr("error"))
            self._update_labels()
            self.request_draw()
        self.after(FRAME_MILLISECONDS, self._tick)

    def _update_labels(self):
        if not hasattr(self, "thermal_label"):
            return
        status = "running" if self.running else "paused" if self.model.t else "ready"
        self.status_label.configure(text=self.tr(status))
        self.pause_button.configure(state="normal" if self.running else "disabled")
        self.thermal_label.configure(text=self.tr("thermal").format(D=noise_intensity(self.parameters)))
        if self.parameters.a > 0:
            shape = self.tr("barrier").format(barrier=barrier_height(self.parameters),
                                              critical=critical_force(self.parameters))
        else:
            shape = self.tr("single" if self.parameters.b else "flat")
        self.barrier_label.configure(text=shape)
        enabled = "normal" if self.parameters.drive_enabled else "disabled"
        for name in ("f", "omega"):
            self.parameter_entries[name].configure(state=enabled)
            self.parameter_scales[name].configure(state=enabled)
        transitions = str(self.model.transitions) if self.parameters.a else "—"
        self.statistics_label.configure(text=f"t = {self.model.t:.1f}     x = {self.model.x:.2f}     {self.tr('transitions')}: {transitions}")
        self.axis_hint.configure(text=self.tr("vertical" if self.vertical else "horizontal"))

    def request_draw(self, _event=None):
        if not self._render_pending:
            self._render_pending = True
            self.after_idle(self._draw)

    def _draw(self):
        self._render_pending = False
        if self.current_page == "home":
            title_scene(max(250, self.title_canvas.winfo_width()),
                        max(200, self.title_canvas.winfo_height()), self.scheme).draw(self.title_canvas)
        elif self.current_page == "lab":
            # Добавляем актуальную точку только в рисунок; частота CSV не меняется.
            visible = list(self.history)
            if not visible or visible[-1].t != self.model.t:
                visible.append(self.model.sample())
            self._scenes = [
                potential_scene(self.parameters, self.model.t, self.model.x, visible,
                                max(300, self.potential_canvas.winfo_width()),
                                max(140, self.potential_canvas.winfo_height()), self.scheme, self.language),
                trajectory_scene(self.parameters, self.model.t, visible,
                                 max(300, self.trajectory_canvas.winfo_width()),
                                 max(180, self.trajectory_canvas.winfo_height()), self.scheme,
                                 self.vertical, self.language),
            ]
            for scene, canvas in zip(self._scenes, (self.potential_canvas, self.trajectory_canvas)):
                scene.draw(canvas)

    def save_csv(self, path):
        """Сохраняет видимую историю с параметрами; не изменяет модель."""
        with Path(path).open("w", encoding="utf-8-sig", newline="") as file:
            file.write("# inertial Langevin; dimensionless; D=gamma*T\n")
            for key, value in asdict(self.parameters).items():
                file.write(f"# {key}={value}\n")
            file.write(f"# D={noise_intensity(self.parameters)}\n")
            writer = csv.writer(file)
            writer.writerow(["t", "x", "v", "force"])
            for point in self.history:
                writer.writerow([point.t, point.x, point.v, point.force])

    def save_svg(self, path):
        """Два текущих графика в одном векторном рисунке, включая пунктир."""
        self._draw()
        namespace = "http://www.w3.org/2000/svg"
        ET.register_namespace("", namespace)
        gap = 30
        width = max(scene.width for scene in self._scenes)
        height = sum(scene.height for scene in self._scenes) + gap
        combined = ET.Element(f"{{{namespace}}}svg", {
            "width": str(width), "height": str(height),
            "viewBox": f"0 0 {width} {height}", "version": "1.1",
        })
        ET.SubElement(combined, f"{{{namespace}}}title").text = self.tr("title")
        offset = 0
        for scene in self._scenes:
            image = ET.fromstring(scene.to_svg())
            image.set("x", "0")
            image.set("y", str(offset))
            combined.append(image)
            offset += scene.height + gap
        ET.ElementTree(combined).write(path, encoding="utf-8", xml_declaration=True)

    def _choose_export(self, extension, save_function):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=extension,
                    filetypes=[(extension.upper().lstrip("."), f"*{extension}")],
                    initialfile="stochastic-resonance" + extension)
        if not path:
            return
        try:
            save_function(path)
            self.notice_label.configure(text=self.tr("saved"))
        except (OSError, ValueError) as error:
            messagebox.showerror(self.tr("save_error"), str(error), parent=self)

    def export_csv(self):
        self._choose_export(".csv", self.save_csv)

    def export_svg(self):
        self._choose_export(".svg", self.save_svg)
