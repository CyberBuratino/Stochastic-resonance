"""Общие элементы титульной страницы и авторов: эмблемы и карточки.

Фотографии пока заменены нейтральными плейсхолдерами. Размеры и цвета
настраиваются здесь и в appearance.py, без изменения физической модели.
"""
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageOps, ImageTk

from . import appearance as visual


def load_emblems(master, vmk_path=None):
    """Загружает локальные эмблемы и сохраняет пропорции при показе."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    paths = {
        "physics": root / "assets/physics-logo.png",
        "vmk": Path(vmk_path) if vmk_path else root / "assets/vmk-logo.png",
    }
    result = {}
    for name, path in paths.items():
        with Image.open(path) as source:
            frame = ImageOps.contain(source.convert("RGBA"), (visual.EMBLEM_SIZE, visual.EMBLEM_SIZE),
                                    Image.Resampling.LANCZOS)
        result[name] = ImageTk.PhotoImage(frame, master=master)
    return result


class AcademicHeader(ttk.Frame):
    """Две эмблемы по краям и симметричный центр с названием МГУ и факультета."""

    def __init__(self, parent, emblems, label):
        super().__init__(parent, padding=(8, 6))
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, minsize=visual.ACADEMIC_HEADER_HEIGHT)
        self.physics_label = ttk.Label(self, image=emblems["physics"])
        self.physics_label.grid(row=0, column=0, padx=(8, 16), sticky="n")
        self.vmk_label = ttk.Label(self, image=emblems["vmk"])
        self.vmk_label.grid(row=0, column=2, padx=(16, 8), sticky="n")
        # Равные боковые колонки сохраняют центр независимо от пропорций эмблем.
        for column in (0, 2):
            self.columnconfigure(column, minsize=visual.EMBLEM_SIZE+32, uniform="emblems")
        self.text_area = ttk.Frame(self, height=visual.ACADEMIC_HEADER_HEIGHT, width=1)
        self.text_area.grid(row=0, column=1, sticky="nsew")
        self.text_area.grid_propagate(False)
        self.text_area.columnconfigure(0, weight=1)
        for row in (0, 1):
            self.text_area.rowconfigure(row, weight=1, uniform="institution")
        self.university_label = label(self.text_area, "university", style="University.TLabel",
                                      anchor="center", justify="center")
        self.university_label.grid(row=0, column=0, sticky="nsew")
        self.faculty_label = label(self.text_area, "faculty", style="Faculty.TLabel",
                                   anchor="center", justify="center")
        self.faculty_label.grid(row=1, column=0, sticky="nsew")
        self.text_area.bind("<Configure>", self._resize_text)

    def _resize_text(self, event):
        for widget in (self.university_label, self.faculty_label):
            widget.configure(wraplength=max(200, event.width-8))


class PhotoPlaceholder(ttk.Frame):
    """Пустое место под будущую фотографию без вымышленного портрета."""

    def __init__(self, parent, label):
        super().__init__(parent, style="Photo.TFrame", width=visual.AUTHOR_PHOTO_MAX,
                         height=visual.AUTHOR_PHOTO_MAX)
        self.pack_propagate(False)
        label(self, "author_photo", style="Photo.TLabel", anchor="center").pack(side="bottom", fill="x", pady=(0, 8))
        self.canvas = tk.Canvas(self, background=visual.UI_COLORS["panel"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._draw)

    def _draw(self, event):
        width, height = event.width, event.height
        self.canvas.delete("all")
        color = "#cbd2d9"
        self.canvas.create_oval(width*.39, height*.16, width*.61, height*.45, fill=color, outline="")
        self.canvas.create_arc(width*.23, height*.48, width*.77, height*1.12,
                               start=0, extent=180, fill=color, outline="")


class AuthorCard(ttk.Frame):
    """Карточка автора с центрированными плейсхолдером, именем и ролью."""

    def __init__(self, parent, name_key, label):
        super().__init__(parent, style="AuthorCard.TFrame", borderwidth=1, relief="solid")
        self.content = ttk.Frame(self)
        self.content.place(relx=.5, rely=.5, anchor="center")
        self.photo = PhotoPlaceholder(self.content, label)
        self.photo.pack(pady=(0, 14))
        self.name_label = label(self.content, name_key, style="AuthorName.TLabel", anchor="center")
        self.name_label.pack(fill="x")
        label(self.content, "author_role", anchor="center").pack(fill="x", pady=(6, 0))
        self.bind("<Configure>", self._resize_photo)

    def _resize_photo(self, event):
        size = max(visual.AUTHOR_PHOTO_MIN, min(visual.AUTHOR_PHOTO_MAX, event.height-110))
        self.photo.configure(width=size, height=size)
