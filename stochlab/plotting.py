"""Описание геометрии графиков.

Функции этого файла только читают параметры и готовую траекторию. Они создают
список простых фигур (Scene), который выводится на tkinter.Canvas.
Здесь меняется только рисунок, а не физическая траектория.
"""

from dataclasses import dataclass, field
import math

from .appearance import (
    ColorScheme, DEFAULT_HISTORY_PERIODS, FONT_FAMILY, FORCE_LINE_WIDTH, GRID_LINE_WIDTH,
    HISTORY_PERIOD_OPTIONS,
    PARTICLE_RADIUS, PLOT_BOTTOM_MARGIN, PLOT_FONT_SIZE, PLOT_LEFT_MARGIN,
    PARTICLE_TRACK_INSET, POTENTIAL_TOP_MARGIN, TRAJECTORY_TOP_MARGIN,
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
        """Показывает сглаженный кадр, не пересоздавая элементы Canvas."""
        from .rendering import draw_scene
        draw_scene(self, canvas)


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


def _time_step(span):
    """Удобный постоянный интервал делений для фиксированной ширины окна."""
    desired = span/4
    power = 10 ** math.floor(math.log10(desired))
    fraction = desired/power
    multiplier = 1 if fraction < 1.5 else 2 if fraction < 3 else 5 if fraction < 7 else 10
    return multiplier*power


def _time_ticks(low, high, step):
    # До t=0 вычислений нет: пустая предыстория не получает вымышленных меток.
    first = max(0, math.ceil((low-1e-10)/step))
    last = math.floor((high+1e-10)/step)
    return [index*step for index in range(first, last+1)]


def _axes(scene, xmin, xmax, ymin, ymax, xlabel, ylabel, palette,
          top=PLOT_TOP_MARGIN, secondary=None, time_axis=None):
    left = min(PLOT_LEFT_MARGIN, scene.width * .22)
    right_margin = PLOT_RIGHT_MARGIN + (36 if secondary else 0)
    axes = Axes(left, max(left+40, scene.width-right_margin), top,
                max(top+25, scene.height-PLOT_BOTTOM_MARGIN), xmin, xmax, ymin, ymax)
    xs = ([xmin+(xmax-xmin)*i/4 for i in range(5)] if time_axis != "x"
          else _time_ticks(xmin, xmax, _time_step(xmax-xmin)))
    ys = ([ymin+(ymax-ymin)*i/4 for i in range(5)] if time_axis != "y"
          else _time_ticks(ymin, ymax, _time_step(ymax-ymin)))
    for x in xs:
        scene.line((axes.x(x), axes.top, axes.x(x), axes.bottom), palette.grid, GRID_LINE_WIDTH)
        scene.text(axes.x(x), axes.bottom+19, _format_tick(x), palette.text)
    for y in ys:
        scene.line((axes.left, axes.y(y), axes.right, axes.y(y)), palette.grid, GRID_LINE_WIDTH)
        scene.text(axes.left-9, axes.y(y), _format_tick(y), palette.text, anchor="e")
        if secondary:
            low, high = secondary
            fraction = (y-ymin)/(ymax-ymin)
            scene.text(axes.right+8, axes.y(y), _format_tick(low+(high-low)*fraction),
                       palette.force, anchor="w")
    scene.text(8, 12, ylabel, palette.text, anchor="nw")
    scene.text(axes.right, scene.height-3, xlabel, palette.text, anchor="se")
    if secondary:
        scene.text(scene.width-5, 12, "F", palette.force, anchor="ne")
    return axes


def _time_window(parameters, time, periods=DEFAULT_HISTORY_PERIODS):
    """Ленточная развёртка: все старые точки сдвигаются с одной скоростью.

    Ширина равна выбранному числу периодов уже с первого кадра. Пока история короткая,
    оставшаяся часть окна пуста; вычислений для отрицательного времени нет.
    """
    if periods not in HISTORY_PERIOD_OPTIONS:
        raise ValueError("Неподдерживаемое число периодов временного окна")
    span = periods*2*math.pi/parameters.omega
    return time-span, time


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


@dataclass
class ViewLimits:
    """Масштаб одной реализации: расширяется при необходимости, не дрожит.

    Границы не следуют за каждым тепловым колебанием. При сбросе модели
    создаётся новый экземпляр; физические координаты при этом не изменяются.
    """
    extent: float = 0.0
    energy_min: float = 0.0
    energy_max: float = 0.0
    initialized: bool = False

    def update(self, parameters, history, position):
        required = _horizontal_extent(parameters, history, position)
        if not self.initialized:
            self.extent = math.ceil(required * 2) / 2
        elif required > self.extent:
            self.extent = math.ceil(required * 1.1 * 2) / 2
        amplitude = parameters.f if parameters.drive_enabled else 0
        # Нижняя оценка по всем фазам наклона, а не только текущей фазе.
        xs = [-self.extent + 2*self.extent*i/512 for i in range(513)]
        lowest = min(-.1, *(potential(x, parameters)-abs(x)*amplitude for x in xs))
        highest = max(.5, barrier_height(parameters)*1.2,
                      potential(position, parameters)+abs(position)*amplitude+.3)
        lowest -= .15*(highest-lowest)
        span = highest-lowest
        step = 10 ** math.floor(math.log10(max(span, .01))) / 5
        lower = math.floor(lowest/step+1e-12)*step
        upper = math.ceil(highest/step-1e-12)*step
        if not self.initialized:
            self.energy_min, self.energy_max = lower, upper
            self.initialized = True
        else:
            self.energy_min = min(self.energy_min, lower)
            self.energy_max = max(self.energy_max, upper)


def _vertical_guide(scene, x, start, end, color):
    """Пунктирная проекция с просветами вокруг численных подписей осей.

    Запас для ширины цифр сохраняет их читаемость, когда частица проходит
    точно над делением. На геометрию траектории эти просветы не влияют.
    """
    low, high = sorted((start, end))
    cursor = low
    labels = sorted((item for item in scene.primitives
                     if item.kind == "text" and item.anchor == "center"),
                    key=lambda item: item.coordinates[1])
    for label in labels:
        cx, cy = label.coordinates
        if abs(x-cx) > len(label.text)*label.font_size*.4+3:
            continue
        top, bottom = cy-label.font_size*.75-2, cy+label.font_size*.75+2
        if bottom < cursor or top > high:
            continue
        if top > cursor:
            scene.line((x, cursor, x, min(top, high)), color, 1, (4, 4))
        cursor = max(cursor, bottom)
    if cursor < high:
        scene.line((x, cursor, x, high), color, 1, (4, 4))


def potential_scene(parameters, time, position, history, width, height, scheme, language="ru", view_limits=None,
                    connect_trajectory=True):
    """Мгновенный потенциал и частица у общей границы с траекторией."""
    palette = get_scheme(scheme)
    scene = Scene(max(width, 220), max(height, 160), palette.background)
    extent = view_limits.extent if view_limits else _horizontal_extent(parameters, history, position)
    drive = driving_force(time, parameters)

    def energy(x):
        return potential(x, parameters)-x*drive

    # Кривая известна аналитически: плотность точек соответствует экрану.
    count = max(300, math.ceil(scene.width * 2))
    xs = [-extent+2*extent*index/count for index in range(count+1)]
    stationary = [(x, potential(x, parameters)) for x in xs]
    points = [(x, energy(x)) for x in xs]
    # Общая шкала для U и Ueff не зависит от текущей фазы силы. Неподвижная
    # пунктирная кривая остаётся опорой при наклоне мгновенного потенциала.
    amplitude = parameters.f if parameters.drive_enabled else 0
    lowest = min(-.1, *(value-abs(x)*amplitude for x, value in stationary))
    highest = max(.5, barrier_height(parameters)*1.2,
                  potential(position, parameters)+abs(position)*amplitude+.3)
    lowest -= .15*(highest-lowest)
    if view_limits:
        lowest, highest = view_limits.energy_min, view_limits.energy_max
    axes = _axes(scene, -extent, extent, lowest, highest, "", "Ueff", palette, top=POTENTIAL_TOP_MARGIN)
    scene.text(scene.width-3, axes.bottom+19, "x", palette.text, anchor="e")
    # Нейтральный пунктир одинаков во всех схемах, включая чёрно-белую.
    # Рисуем его первым, чтобы текущая сплошная кривая оставалась отчётливой.
    _curve(scene, axes, stationary, palette.axes, 1.5, (7, 5))
    _state_curve(scene, axes, points, [point[0] for point in points], palette)
    track = scene.height-PARTICLE_TRACK_INSET
    scene.line((axes.left, track, axes.right, track), palette.axes, 1.3)
    _vertical_guide(scene, axes.x(position), axes.y(energy(position)),
                    scene.height if connect_trajectory else track, palette.axes)
    color = palette.particle
    if palette.by_state:
        color = palette.right_well if position >= 0 else palette.left_well
    scene.circle(axes.x(position), track, PARTICLE_RADIUS, color)
    return scene


def trajectory_scene(parameters, time, history, width, height, scheme, vertical=True, language="ru", view_limits=None,
                     periods=DEFAULT_HISTORY_PERIODS):
    """Координата и сила; время направлено вверх либо вправо."""
    palette = get_scheme(scheme)
    scene = Scene(max(width, 220), max(height, 170), palette.background)
    extent = view_limits.extent if view_limits else _horizontal_extent(parameters, history)
    start, end = _time_window(parameters, time, periods)
    # Каждая сохранённая точка участвует в рисунке. Добавление новых точек
    # больше не меняет выбор старых точек и не создаёт рябь от прореживания.
    samples = [sample for sample in history if start <= sample.t <= end]
    count = max(200, math.ceil((height if vertical else width) * 2))
    observed_start = max(0, start)
    force_times = ([observed_start+(end-observed_start)*i/count for i in range(count+1)]
                   if end > observed_start else [])
    force_extent = max(parameters.f, .01)
    if vertical:
        axes = _axes(scene, -extent, extent, start, end, "x", "t", palette,
                     top=TRAJECTORY_TOP_MARGIN, time_axis="y")
        coordinate_points = [(sample.x, sample.t) for sample in samples]
        force_points = [(driving_force(t, parameters)/force_extent*extent, t) for t in force_times]
        scene.text(scene.width-5, TRAJECTORY_TOP_MARGIN-5, "F", palette.force, anchor="ne")
        for index in range(5):
            fraction = index/4
            scene.text(axes.x(-extent+2*extent*fraction), 16,
                       _format_tick(-force_extent+2*force_extent*fraction), palette.force)
    else:
        axes = _axes(scene, start, end, -extent, extent, "t", "x", palette,
                     secondary=(-force_extent, force_extent), time_axis="x")
        coordinate_points = [(sample.t, sample.x) for sample in samples]
        force_points = [(t, driving_force(t, parameters)/force_extent*extent) for t in force_times]
    _state_curve(scene, axes, coordinate_points, [sample.x for sample in samples], palette)
    if parameters.drive_enabled:
        _curve(scene, axes, force_points, palette.force, FORCE_LINE_WIDTH, palette.force_dash)
    if samples and samples[-1].t == time:
        current = samples[-1]
        color = palette.particle
        if palette.by_state:
            color = palette.right_well if current.x >= 0 else palette.left_well
        if vertical:
            x, y = axes.x(current.x), axes.y(time)
            # Продолжение проекции частицы через границу двух соседних Canvas.
            _vertical_guide(scene, x, 0, y, palette.axes)
        else:
            # После поворота общей вертикали x нет: отмечаем только конец линии.
            x, y = axes.x(time), axes.y(current.x)
        scene.circle(x, y, PARTICLE_RADIUS/2, color)
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
