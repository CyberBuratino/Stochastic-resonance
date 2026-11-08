"""Все основные настройки оформления, которые можно менять без знания модели.

Начните с этого файла, если нужно изменить цвета, размеры надписей или линий.
Физические параметры и численный метод находятся в model.py и от этих настроек
не зависят. Цвета записаны как обычные шестнадцатеричные HTML-коды.
"""

from dataclasses import dataclass


# Настройки окна и элементов управления.
FONT_FAMILY = "DejaVu Sans"
BODY_FONT_SIZE = 14
BUTTON_FONT_SIZE = 16
CONTROL_FONT_SIZE = 16
PARAMETER_FONT_SIZE = 16
SMALL_FONT_SIZE = 12
HEADING_FONT_SIZE = 20
TITLE_FONT_SIZE = 30
EMBLEM_SIZE = 104
ACADEMIC_HEADER_HEIGHT = 116
AUTHOR_PHOTO_MIN = 140
AUTHOR_PHOTO_MAX = 280
SIDEBAR_WIDTH = 300
PANEL_PADDING = 16

UI_COLORS = {
    "background": "#ffffff",
    "panel": "#f7f8fa",
    "text": "#202830",
    "muted": "#525e69",
    "border": "#cbd2d9",
    "accent": "#245b86",
    "button": "#f2f4f6",
}

# Размеры графиков. У обеих картинок одинаковые левые/правые поля:
# поэтому координата x на вертикальной траектории совпадает с потенциалом.
PLOT_FONT_SIZE = 18
PLOT_LEFT_MARGIN = 96
PLOT_RIGHT_MARGIN = 42
PLOT_BOTTOM_MARGIN = 56
PLOT_TOP_MARGIN = 60
POTENTIAL_TOP_MARGIN = 42
TRAJECTORY_TOP_MARGIN = 44
PARTICLE_TRACK_INSET = 9
PLOT_LINE_WIDTH = 2.0
FORCE_LINE_WIDTH = 2.0
PARTICLE_RADIUS = 7
GRID_LINE_WIDTH = 1
HISTORY_PERIOD_OPTIONS = (3, 6)
DEFAULT_HISTORY_PERIODS = 3


@dataclass(frozen=True)
class ColorScheme:
    """Палитра графиков; физические данные схема не изменяет."""

    background: str
    text: str
    grid: str
    axes: str
    coordinate: str
    force: str
    particle: str
    left_well: str
    right_well: str
    force_dash: tuple[int, ...] = ()
    by_state: bool = False


SCHEMES = {
    # Различаем величины: координата/потенциал синие, сила оранжевая.
    "quantities": ColorScheme(
        background="#ffffff", text="#374151", grid="#e1e5e9",
        axes="#66717c", coordinate="#245b86", force="#a34d0a",
        particle="#a34d0a", left_well="#245b86", right_well="#245b86",
    ),
    # Цвет координаты показывает сторону: слева от барьера — фиолетовый,
    # справа — зелёный. Момент смены цвета точно соответствует x = 0.
    "states": ColorScheme(
        background="#ffffff", text="#374151", grid="#e1e5e9",
        axes="#66717c", coordinate="#6741a5", force="#a34d0a",
        particle="#6741a5", left_well="#6741a5", right_well="#19734a",
        by_state=True,
    ),
    # Для цитирования/чёрно-белой печати смысл не зависит от цвета:
    # координата — сплошная линия, внешняя сила — пунктирная.
    "monochrome": ColorScheme(
        background="#ffffff", text="#000000", grid="#dedede",
        axes="#555555", coordinate="#000000", force="#000000",
        particle="#000000", left_well="#000000", right_well="#000000",
        force_dash=(7, 5),
    ),
}

SCHEME_LABELS = {
    "quantities": {"ru": "По величинам", "en": "By quantity"},
    "states": {"ru": "По сторонам барьера", "en": "By side of barrier"},
    "monochrome": {"ru": "Чёрно-белая", "en": "Black and white"},
}


def get_scheme(scheme: str | ColorScheme) -> ColorScheme:
    """Возвращает палитру по имени; готовую палитру можно передать напрямую."""
    return SCHEMES[scheme] if isinstance(scheme, str) else scheme

# AGG рисует дробные координаты со сглаживанием уже при масштабе 1.
# Большие значения повышают нагрузку; физические данные не усредняются.
GRAPH_SUPERSAMPLING = 1
GRAPH_FONT_FILE = "assets/fonts/DejaVuSans.ttf"
