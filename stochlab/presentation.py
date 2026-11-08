"""Общие элементы титульной страницы и авторов: эмблемы и карточки.

Фотографии загружаются из локальных файлов авторов. Размеры и цвета
настраиваются здесь и в appearance.py, без изменения физической модели.
"""
from pathlib import Path
import sys
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


class AuthorPortrait(ttk.Label):
    """Показывает квадратный фрагмент фото; исходный JPG не изменяется."""

    def __init__(self, parent, filename):
        super().__init__(parent, anchor="center")
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        with Image.open(root / "assets" / filename) as source:
            self.original = ImageOps.exif_transpose(source).convert("RGB")
        self.photo_image = None
        self._size = None
        self.set_size(visual.AUTHOR_PHOTO_MAX)

    def set_size(self, size):
        if size == self._size:
            return
        self._size = size
        frame = ImageOps.fit(self.original, (size, size), Image.Resampling.LANCZOS)
        self.photo_image = ImageTk.PhotoImage(frame, master=self)
        self.configure(image=self.photo_image)


class AuthorCard(ttk.Frame):
    """Карточка автора с центрированными фотографией, именем и ролью."""

    def __init__(self, parent, name_key, filename, label):
        super().__init__(parent, style="AuthorCard.TFrame", borderwidth=1, relief="solid")
        self.content = ttk.Frame(self)
        self.content.place(relx=.5, rely=.5, anchor="center")
        self.photo = AuthorPortrait(self.content, filename)
        self.photo.pack(pady=(0, 14))
        self.name_label = label(self.content, name_key, style="AuthorName.TLabel", anchor="center")
        self.name_label.pack(fill="x")
        label(self.content, "author_role", anchor="center").pack(fill="x", pady=(6, 0))
        self.bind("<Configure>", self._resize_photo)

    def _resize_photo(self, event):
        size = max(visual.AUTHOR_PHOTO_MIN, min(visual.AUTHOR_PHOTO_MAX, event.height-110))
        self.photo.set_size(size)
