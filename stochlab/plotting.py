"""Рисование и SVG-экспорт без внешних библиотек.

Функции этого файла только читают параметры и готовую траекторию. Они создают
список простых фигур (Scene), который можно показать на tkinter.Canvas или
сохранить в SVG. Поэтому экспорт точно сохраняет цвета и пунктир текущего вида.
"""

from dataclasses import dataclass, field
from html import escape
import math

from .appearance import (
    ColorScheme, FONT_FAMILY, FORCE_LINE_WIDTH, GRID_LINE_WIDTH,
    PARTICLE_RADIUS, PLOT_BOTTOM_MARGIN, PLOT_FONT_SIZE, PLOT_LEFT_MARGIN,
    PLOT_LINE_WIDTH, PLOT_RIGHT_MARGIN, PLOT_TOP_MARGIN, get_scheme,
)
from .model import barrier_height, driving_force, potential, well_position


@dataclass
class Primitive:
    """Одна линия, подпись или окружность в экранных координатах."""

    kind: str
    coordinates: tuple[float, ...]
    color: str
    width: float = 1
    dash: tuple[int, ...] = ()
    text: str = ""
    font_size: int = PLOT_FONT_SIZE
    anchor: str = "center"
    fill: str = ""


@dataclass
class Scene:
    width: float
    height: float
    background: str = "#ffffff"
    primitives: list[Primitive] = field(default_factory=list)

    def line(self, coordinates, color, width=1, dash=()):
        if len(coordinates) >= 4:
            self.primitives.append(Primitive("line", tuple(coordinates), color, width, dash))

    def text(self, x, y, text, color, font_size=PLOT_FONT_SIZE, anchor="center"):
        self.primitives.append(Primitive(
            "text", (x, y), color, text=str(text), font_size=font_size, anchor=anchor,
        ))

    def circle(self, x, y, radius, color):
        self.primitives.append(Primitive("circle", (x, y, radius), color, fill=color))

    def draw(self, canvas):
        """Перерисовывает существующий Canvas. Его положение не меняется."""
        canvas.delete("all")
        canvas.configure(background=self.background, highlightthickness=0)
        for item in self.primitives:
            if item.kind == "line":
                options = {"fill": item.color, "width": item.width}
                if item.dash:
                    options["dash"] = item.dash
                canvas.create_line(*item.coordinates, **options)
            elif item.kind == "circle":
                x, y, radius = item.coordinates
                canvas.create_oval(x-radius, y-radius, x+radius, y+radius,
                                   fill=item.fill, outline=item.color)
            elif item.kind == "text":
                canvas.create_text(
                    *item.coordinates, text=item.text, fill=item.color,
                    font=(FONT_FAMILY, -item.font_size), anchor=item.anchor,
                )

    def to_svg(self):
        """Возвращает самостоятельный векторный SVG в UTF-8."""
        def number(value):
            return f"{value:.3f}".rstrip("0").rstrip(".") or "0"

        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{number(self.width)}" '
            f'height="{number(self.height)}" viewBox="0 0 {number(self.width)} {number(self.height)}">',
            f'<rect width="100%" height="100%" fill="{escape(self.background, quote=True)}"/>',
        ]
        for item in self.primitives:
            color = escape(item.color, quote=True)
            if item.kind == "line":
                coordinates = item.coordinates
                points = " ".join(
                    f"{number(coordinates[i])},{number(coordinates[i+1])}"
                    for i in range(0, len(coordinates), 2)
                )
                dash = ""
                if item.dash:
                    dash = f' stroke-dasharray="{",".join(map(str, item.dash))}"'
                lines.append(f'<polyline points="{points}" fill="none" stroke="{color}" '
                             f'stroke-width="{number(item.width)}"{dash}/>')
            elif item.kind == "circle":
                x, y, radius = item.coordinates
                lines.append(f'<circle cx="{number(x)}" cy="{number(y)}" r="{number(radius)}" '
                             f'fill="{color}"/>')
            elif item.kind == "text":
                x, y = item.coordinates
                horizontal = "start" if item.anchor in ("w", "nw", "sw") else "end" if item.anchor in ("e", "ne", "se") else "middle"
                vertical = "hanging" if item.anchor in ("n", "nw", "ne") else "auto" if item.anchor in ("s", "sw", "se") else "central"
                lines.append(
                    f'<text x="{number(x)}" y="{number(y)}" fill="{color}" '
                    f'font-family="{escape(FONT_FAMILY, quote=True)}" font-size="{item.font_size}" '
                    f'text-anchor="{horizontal}" dominant-baseline="{vertical}">{escape(item.text)}</text>'
                )
        lines.append("</svg>")
        return "\n".join(lines)


@dataclass(frozen=True)
class Axes:
    """Переход от физических координат графика к экранным."""

    left: float
    right: float
    top: float
    bottom: float
    xmin: float
    xmax: float
    ymin: float
    ymax: float

    def x(self, value):
        return self.left + (value-self.xmin)/(self.xmax-self.xmin)*(self.right-self.left)

    def y(self, value):
        return self.bottom - (value-self.ymin)/(self.ymax-self.ymin)*(self.bottom-self.top)


def _format_tick(value):
    if abs(value) < 1e-12:
        return "0"
    if abs(value) >= 1000 or 0 < abs(value) < .001:
        return f"{value:.1e}"
    if abs(value) < .1:
        return f"{value:.3g}"
    if abs(value) >= 100:
        return f"{value:.0f}"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _axes(scene, xmin, xmax, ymin, ymax, xlabel, ylabel, palette, top=PLOT_TOP_MARGIN, secondary=None):
    left = min(PLOT_LEFT_MARGIN, scene.width * .22)
    right_margin = PLOT_RIGHT_MARGIN + (36 if secondary else 0)
    axes = Axes(left, max(left+40, scene.width-right_margin), top,
                max(top+25, scene.height-PLOT_BOTTOM_MARGIN), xmin, xmax, ymin, ymax)
    for index in range(5):
        fraction = index/4
        x = xmin+(xmax-xmin)*fraction
        y = ymin+(ymax-ymin)*fraction
        scene.line((axes.x(x), axes.top, axes.x(x), axes.bottom), palette.grid, GRID_LINE_WIDTH)
        scene.line((axes.left, axes.y(y), axes.right, axes.y(y)), palette.grid, GRID_LINE_WIDTH)
        scene.text(axes.x(x), axes.bottom+19, _format_tick(x), palette.text)
        scene.text(axes.left-9, axes.y(y), _format_tick(y), palette.text, anchor="e")
        if secondary:
            low, high = secondary
            scene.text(axes.right+8, axes.y(y), _format_tick(low+(high-low)*fraction),
                       palette.force, anchor="w")
    scene.text(8, 12, ylabel, palette.text, anchor="nw")
    scene.text(axes.right, scene.height-3, xlabel, palette.text, anchor="se")
    if secondary:
        scene.text(scene.width-5, 12, "F [1]", palette.force, anchor="ne")
    return axes


def _clip_segment(x1, y1, x2, y2, axes):
    """Обрезает отрезок по рамке графика (метод Лянга—Барски)."""
    dx, dy = x2-x1, y2-y1
    entering, leaving = 0.0, 1.0
    for p, q in ((-dx, x1-axes.left), (dx, axes.right-x1),
                 (-dy, y1-axes.top), (dy, axes.bottom-y1)):
        if p == 0:
            if q < 0:
                return None
        else:
            fraction = q/p
            if p < 0:
                entering = max(entering, fraction)
            else:
                leaving = min(leaving, fraction)
            if entering > leaving:
                return None
    return (x1+entering*dx, y1+entering*dy,
            x1+leaving*dx, y1+leaving*dy)


def _curve(scene, axes, points, color, width=PLOT_LINE_WIDTH, dash=()):
    """Добавляет ломаную, не рисуя за пределами числовых осей."""
    current = []
    for first, second in zip(points, points[1:]):
        clipped = _clip_segment(axes.x(first[0]), axes.y(first[1]),
                                axes.x(second[0]), axes.y(second[1]), axes)
        if clipped is None:
            if current:
                scene.line(current, color, width, dash)
                current = []
            continue
        x1, y1, x2, y2 = clipped
        if current and (abs(current[-2]-x1) > .001 or abs(current[-1]-y1) > .001):
            scene.line(current, color, width, dash)
            current = []
        if not current:
            current.extend((x1, y1))
        current.extend((x2, y2))
    if current:
        scene.line(current, color, width, dash)


def _state_curve(scene, axes, points, states, palette):
    """Разделяет линию точно на границе x=0, сохраняя непрерывность."""
    if not points:
        return
    if not palette.by_state:
        _curve(scene, axes, points, palette.coordinate)
        return
    current = [points[0]]
    side = states[0] >= 0
    for index in range(1, len(points)):
        next_side = states[index] >= 0
        if next_side != side:
            previous_state, next_state = states[index-1], states[index]
            fraction = -previous_state/(next_state-previous_state)
            first, second = points[index-1], points[index]
            boundary = (first[0]+fraction*(second[0]-first[0]),
                        first[1]+fraction*(second[1]-first[1]))
            current.append(boundary)
            _curve(scene, axes, current, palette.right_well if side else palette.left_well)
            current = [boundary]
            side = next_side
        current.append(points[index])
    _curve(scene, axes, current, palette.right_well if side else palette.left_well)


def _horizontal_extent(parameters, history, position=0):
    """Одинаковый масштаб x для потенциала и вертикальной траектории."""
    positions = [abs(sample.x) for sample in history]
    return max(1.5, well_position(parameters)*1.85, abs(position)*1.12,
               max(positions, default=0)*1.12)


def _legend(scene, palette, language, y=12):
    if palette.by_state:
        left = "x < 0" if language == "en" else "x < 0"
        right = "x ≥ 0"
        scene.text(scene.width/2-35, y, left, palette.left_well, anchor="n")
        scene.text(scene.width/2+45, y, right, palette.right_well, anchor="n")


def potential_scene(parameters, time, position, history, width, height, scheme, language="ru"):
    """Мгновенный потенциал и частица на горизонтальной дорожке над ним."""
    palette = get_scheme(scheme)
    scene = Scene(max(width, 220), max(height, 160), palette.background)
    extent = _horizontal_extent(parameters, history, position)
    drive = driving_force(time, parameters)

    def energy(x):
        return potential(x, parameters)-x*drive

    points = [(-extent+2*extent*index/300, 0) for index in range(301)]
    points = [(x, energy(x)) for x, _ in points]
    lowest = min(-.1, *(point[1] for point in points))
    highest = max(.5, barrier_height(parameters)*1.2, energy(position)+.3)
    lowest -= .15*(highest-lowest)
    axes = _axes(scene, -extent, extent, lowest, highest, "x [1]", "Ueff [1]", palette, top=66)
    _state_curve(scene, axes, points, [point[0] for point in points], palette)
    track = 33
    scene.line((axes.left, track, axes.right, track), palette.axes, 1.3)
    scene.line((axes.x(position), track, axes.x(position), axes.y(energy(position))),
               palette.axes, 1, (4, 4))
    color = palette.particle
    if palette.by_state:
        color = palette.right_well if position >= 0 else palette.left_well
    scene.circle(axes.x(position), track, PARTICLE_RADIUS, color)
    _legend(scene, palette, language)
    return scene


def _display_samples(samples, limit=1200):
    """Прореживает только рисунок; исходная история/экспорт CSV не меняются.

    В каждом временном блоке оставляем минимальную и максимальную координату,
    чтобы узкие выбросы не пропали. Точки по обе стороны x=0 сохраняем отдельно:
    цветовые переключения не исчезают при уменьшении количества точек.
    """
    if len(samples) <= limit:
        return samples
    selected = {0, len(samples)-1}
    for index in range(1, len(samples)):
        if (samples[index-1].x >= 0) != (samples[index].x >= 0):
            selected.update((index-1, index))
    # В необычной траектории с очень частыми пересечениями нуля сохраняем их
    # все: точность цветов в этом случае важнее рекомендуемого лимита рисунка.
    buckets = max(0, (limit-len(selected))//2)
    for bucket in range(buckets):
        start = bucket*len(samples)//buckets
        end = (bucket+1)*len(samples)//buckets
        indices = range(start, end)
        selected.add(min(indices, key=lambda index: samples[index].x))
        selected.add(max(indices, key=lambda index: samples[index].x))
    return [samples[index] for index in sorted(selected)]


def trajectory_scene(parameters, time, history, width, height, scheme, vertical=True, language="ru"):
    """Координата и сила; время направлено вверх либо вправо."""
    palette = get_scheme(scheme)
    scene = Scene(max(width, 220), max(height, 170), palette.background)
    extent = _horizontal_extent(parameters, history)
    period = 2*math.pi/parameters.omega
    start = max(0, time-3*period)
    end = max(time, parameters.dt)
    samples = _display_samples([sample for sample in history if start <= sample.t <= end])
    force_extent = max(parameters.f, .01)
    if vertical:
        axes = _axes(scene, -extent, extent, start, end, "x [1]", "t [1]", palette, top=66)
        coordinate_points = [(sample.x, sample.t) for sample in samples]
        force_points = [(sample.force/force_extent*extent, sample.t) for sample in samples]
        scene.text(scene.width-5, 12, "F [1]", palette.force, anchor="ne")
        for index in range(5):
            fraction = index/4
            scene.text(axes.x(-extent+2*extent*fraction), 43,
                       _format_tick(-force_extent+2*force_extent*fraction), palette.force)
    else:
        axes = _axes(scene, start, end, -extent, extent, "t [1]", "x [1]", palette,
                     secondary=(-force_extent, force_extent))
        coordinate_points = [(sample.t, sample.x) for sample in samples]
        force_points = [(sample.t, sample.force/force_extent*extent) for sample in samples]
    _state_curve(scene, axes, coordinate_points, [sample.x for sample in samples], palette)
    if parameters.drive_enabled:
        _curve(scene, axes, force_points, palette.force, FORCE_LINE_WIDTH, palette.force_dash)
    if not vertical:
        _legend(scene, palette, language)
    return scene


def title_scene(width, height, scheme):
    """Неподписанный двухъямный рисунок для стартового экрана."""
    palette = get_scheme(scheme)
    scene = Scene(max(width, 220), max(height, 150), palette.background)
    axes = Axes(18, scene.width-18, 18, scene.height-18, -1.8, 1.8, -.6, 1.1)
    points = [(-1.8+3.6*index/200, 0) for index in range(201)]
    points = [(x, -x*x+x**4/2) for x, _ in points]
    _state_curve(scene, axes, points, [x for x, _ in points], palette)
    x = -1.05
    color = palette.left_well if palette.by_state else palette.particle
    scene.circle(axes.x(x), axes.y(-x*x+x**4/2)-PARTICLE_RADIUS, PARTICLE_RADIUS, color)
    return scene
