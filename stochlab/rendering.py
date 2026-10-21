"""Сглаженная экранная отрисовка без изменения исходных линий и данных.

Сначала рисуем готовую сцену в увеличенном разрешении, затем уменьшаем её
фильтром Lanczos. Это сглаживает края пикселей, но не усредняет траекторию.
Canvas получает целый готовый кадр одной операцией, поэтому между кадрами
не появляется пустое поле. Векторный экспорт по-прежнему выполняет Scene.
"""
from functools import lru_cache
import math
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont, ImageTk

from . import appearance


def _resource_path(relative_path):
    """Находит шрифт рядом с исходниками или внутри сборки PyInstaller."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return root / relative_path


@lru_cache(maxsize=64)
def _font(pixel_size, font_file):
    """Кэш шрифтов устраняет повторное чтение файла при каждом кадре."""
    path = _resource_path(font_file)
    font = ImageFont.truetype(str(path), max(1, pixel_size))
    # Оси повторяют одни и те же подписи. Кэшируем их готовые маски,
    # чтобы FreeType не растеризовал одинаковый текст при каждом кадре.
    # Ограничение кэша не даёт истории числовых подписей накапливать память.
    font.getmask2 = lru_cache(maxsize=128)(font.getmask2)
    return font


def _points(coordinates):
    return [(coordinates[index], coordinates[index+1])
            for index in range(0, len(coordinates), 2)]


def _dashed_paths(points, dash):
    """Разбивает ломаную на штрихи с непрерывной фазой через её вершины.

    Длины задаются в экранных пикселях до увеличения разрешения. Отсчёт
    штриха не начинается заново на каждом коротком сегменте траектории.
    """
    pattern = tuple(float(length) for length in dash)
    if any(not math.isfinite(length) or length <= 0 for length in pattern):
        raise ValueError("Длины штрихов должны быть положительными")
    if len(pattern) % 2:
        pattern *= 2
    pattern_index = 0
    remaining = pattern[0]
    current = []
    for first, second in zip(points, points[1:]):
        dx, dy = second[0]-first[0], second[1]-first[1]
        length = math.hypot(dx, dy)
        if length == 0:
            continue
        consumed = 0.0
        while consumed < length-1e-10:
            part = min(remaining, length-consumed)
            start = (first[0]+dx*consumed/length, first[1]+dy*consumed/length)
            consumed += part
            end = (first[0]+dx*consumed/length, first[1]+dy*consumed/length)
            if pattern_index % 2 == 0:
                if not current:
                    current.append(start)
                current.append(end)
            remaining -= part
            if remaining <= 1e-10:
                if current:
                    yield current
                    current = []
                pattern_index = (pattern_index+1) % len(pattern)
                remaining = pattern[pattern_index]
    if current:
        yield current


def _stroke(draw, points, color, width, scale):
    """Рисует ломаную с округлёнными соединениями и концами."""
    if len(points) < 2:
        return
    pixels = [(x*scale, y*scale) for x, y in points]
    line_width = max(1, round(width*scale))
    draw.line(pixels, fill=color, width=line_width, joint="curve")
    radius = line_width/2
    for x, y in (pixels[0], pixels[-1]):
        draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=color)


def render_scene(scene, scale=None):
    """Возвращает готовый RGB-кадр размера сцены; не изменяет саму сцену.

    scale=3 рисует по девять вспомогательных пикселей на один конечный.
    Увеличение масштаба повышает качество краёв, а не частоту физических
    измерений. Физические координаты и положение каждой точки неизменны.
    """
    if scale is None:
        scale = getattr(appearance, "GRAPH_SUPERSAMPLING", 3)
    if isinstance(scale, bool) or not isinstance(scale, int) or not 1 <= scale <= 8:
        raise ValueError("GRAPH_SUPERSAMPLING должен быть целым числом от 1 до 8")
    width, height = max(1, round(scene.width)), max(1, round(scene.height))
    image = Image.new("RGB", (width*scale, height*scale), scene.background)
    draw = ImageDraw.Draw(image)
    font_file = getattr(appearance, "GRAPH_FONT_FILE", "assets/fonts/DejaVuSans.ttf")
    anchors = {
        "center": "mm", "w": "lm", "e": "rm", "n": "mt", "s": "mb",
        "nw": "lt", "ne": "rt", "sw": "lb", "se": "rb",
    }
    for item in scene.primitives:
        if item.kind == "line":
            points = _points(item.coordinates)
            paths = _dashed_paths(points, item.dash) if item.dash else (points,)
            for path in paths:
                _stroke(draw, path, item.color, item.width, scale)
        elif item.kind == "circle":
            x, y, radius = item.coordinates
            bounds = ((x-radius)*scale, (y-radius)*scale,
                      (x+radius)*scale, (y+radius)*scale)
            draw.ellipse(bounds, fill=item.fill or item.color)
        elif item.kind == "text":
            x, y = item.coordinates
            font = _font(max(1, round(item.font_size*scale)), font_file)
            draw.text((x*scale, y*scale), item.text, fill=item.color,
                      font=font, anchor=anchors.get(item.anchor, "mm"))
    if scale != 1:
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    return image


def draw_scene(scene, canvas):
    """Заменяет кадр в единственном элементе Canvas без промежуточной очистки.

    Ссылка на PhotoImage хранится в Canvas: иначе Tk потеряет изображение
    после выхода из функции. Новый кадр полностью готов до замены старого.
    """
    frame = render_scene(scene)
    photo = ImageTk.PhotoImage(frame, master=canvas)
    image_item = getattr(canvas, "_scene_image_item", None)
    if image_item is not None and canvas.type(image_item) == "image":
        canvas.itemconfigure(image_item, image=photo)
    else:
        canvas.delete("all")
        image_item = canvas.create_image(0, 0, anchor="nw", image=photo)
        canvas._scene_image_item = image_item
    canvas._scene_photo = photo
    canvas.configure(background=scene.background, highlightthickness=0)
