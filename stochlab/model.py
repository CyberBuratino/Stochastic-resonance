"""Физическая модель: инерционная частица в термостате и двухъямном потенциале.

Этот файл не зависит от интерфейса и библиотек для рисования. Все величины
безразмерные, масса и постоянная Больцмана равны единице. Интегратор BAOAB
и последовательность случайных чисел сохранены из исходной JavaScript-версии.
Для изменения внешнего вида приложения этот файл редактировать не требуется.
"""

from dataclasses import dataclass
import math


# Допустимые значения параметров. Интерфейс использует те же ограничения.
PARAMETER_LIMITS = {
    "T": (0.0, 1.5),
    "a": (0.0, 2.0),
    "b": (0.0, 2.0),
    "f": (0.0, 0.5),
    "omega": (0.02, 0.2),
    "gamma": (0.3, 3.0),
    "dt": (0.005, 0.04),
    "seed": (0, 4_294_967_295),
}


@dataclass(frozen=True)
class Parameters:
    """Параметры одной реализации; при их изменении создаётся новая модель.

    T — приведённая температура; D = gamma*T — интенсивность случайной силы.
    a, b — коэффициенты U(x) = -a*x²/2 + b*x⁴/4.
    f, omega — амплитуда и частота периодической силы.
    gamma — трение, dt — шаг интегрирования, seed — зерно генератора.
    """

    T: float = 0.22
    a: float = 1.0
    b: float = 0.5
    drive_enabled: bool = True
    f: float = 0.18
    omega: float = 0.04
    gamma: float = 1.0
    dt: float = 0.02
    seed: int = 42

    def __post_init__(self):
        """Отклонить некорректные значения до начала вычислений."""
        for name, (minimum, maximum) in PARAMETER_LIMITS.items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name}: требуется число")
            if not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError(f"{name}: допустимый диапазон {minimum}…{maximum}")
        if not isinstance(self.drive_enabled, bool):
            raise ValueError("drive_enabled: требуется True или False")
        if not isinstance(self.seed, int):
            raise ValueError("seed: требуется целое число")
        if self.b == 0 and self.a > 0:
            raise ValueError("При a > 0 требуется b > 0: иначе потенциал не удерживает частицу")


@dataclass(frozen=True)
class Sample:
    """Одна точка траектории для графиков и экспорта CSV."""

    t: float
    x: float
    v: float
    force: float


class SeededRandom:
    """Воспроизводимый Mulberry32 и нормальный шум Бокса—Мюллера.

    Маска оставляет младшие 32 бита целого числа. Так Python повторяет
    целочисленные операции исходного JavaScript независимо от платформы.
    Это генератор для численной демонстрации, не для криптографии.
    """

    MASK = 0xFFFF_FFFF

    def __init__(self, seed):
        self.state = seed & self.MASK

    def uniform(self):
        """Равномерное число в интервале [0, 1)."""
        self.state = (self.state + 0x6D2B79F5) & self.MASK
        value = self.state
        value = ((value ^ (value >> 15)) * (value | 1)) & self.MASK
        product = ((value ^ (value >> 7)) * (value | 61)) & self.MASK
        value ^= (value + product) & self.MASK
        return ((value ^ (value >> 14)) & self.MASK) / 4_294_967_296

    def normal(self):
        """Нормальная величина с нулевым средним и единичной дисперсией."""
        radius = math.sqrt(-2 * math.log(1 - self.uniform()))
        angle = 2 * math.pi * self.uniform()
        return radius * math.cos(angle)


def potential(x, parameters):
    """Собственная потенциальная энергия U(x), без внешнего наклона."""
    return -parameters.a * x * x / 2 + parameters.b * x**4 / 4


def driving_force(t, parameters):
    """Периодическая сила; выключатель сохраняет выбранную амплитуду f."""
    if not parameters.drive_enabled:
        return 0.0
    return parameters.f * math.sin(parameters.omega * t)


def total_force(x, t, parameters):
    """Обычная сила без трения и случайных толчков: -U'(x) + F(t)."""
    return parameters.a * x - parameters.b * x**3 + driving_force(t, parameters)


def noise_intensity(parameters):
    """Флуктуационно-диссипативная связь для случайной силы: D = gamma*T."""
    return parameters.gamma * parameters.T


def well_position(parameters):
    """Модуль координаты минимума; ноль, если двух ям нет."""
    if parameters.a > 0 and parameters.b > 0:
        return math.sqrt(parameters.a / parameters.b)
    return 0.0


def barrier_height(parameters):
    """Высота барьера собственного потенциала относительно дна ямы."""
    if parameters.b > 0:
        return parameters.a * parameters.a / (4 * parameters.b)
    return 0.0


def critical_force(parameters):
    """Статическая сила, при которой одна из мгновенных ям исчезает."""
    if parameters.a > 0 and parameters.b > 0:
        return 2 * parameters.a / 3 * math.sqrt(parameters.a / (3 * parameters.b))
    return 0.0


class Model:
    """Состояние частицы и один шаг стохастического уравнения движения.

    dx = v dt
    dv = [a*x - b*x³ - gamma*v + F(t)] dt + sqrt(2*gamma*T) dW

    Методы интерфейса лишь вызывают step() и читают состояние. Темп показа
    меняет число вызовов в секунду, а не физический шаг dt.
    """

    def __init__(self, parameters=None):
        self.parameters = parameters if parameters is not None else Parameters()
        self.random = SeededRandom(self.parameters.seed)
        self.t = 0.0
        self.x = -well_position(self.parameters) if self.parameters.a > 0 else 0.0
        self.v = 0.0
        self.steps = 0
        self.transitions = 0
        self.well = -1
        self.last_transition = None
        self.residence_times = []

        # Точное решение части уравнения с трением и тепловым шумом (OU-шаг).
        self.decay = math.exp(-self.parameters.gamma * self.parameters.dt)
        self.sigma = math.sqrt(
            self.parameters.T
            * (-math.expm1(-2 * self.parameters.gamma * self.parameters.dt))
        )

    def step(self):
        """Продвинуть систему на dt методом BAOAB и вернуть эту же модель."""
        parameters = self.parameters
        half_step = parameters.dt / 2

        # B: половина изменения скорости под действием обычной силы.
        self.v += half_step * total_force(self.x, self.t, parameters)
        # A: половина переноса координаты.
        self.x += half_step * self.v
        # O: совместное действие трения и тепловых толчков.
        self.v = self.decay * self.v + self.sigma * self.random.normal()
        # A: вторая половина переноса.
        self.x += half_step * self.v
        self.steps += 1
        self.t = self.steps * parameters.dt
        # B: сила вычисляется уже в новом положении и новом времени.
        self.v += half_step * total_force(self.x, self.t, parameters)

        if not math.isfinite(self.x) or not math.isfinite(self.v):
            raise ArithmeticError("Численный расчёт дал неограниченную траекторию")
        self._count_transition()
        return self

    def _count_transition(self):
        """Гистерезис не считает колебания возле x=0 отдельными переходами."""
        threshold = well_position(self.parameters) / 2
        next_well = self.well
        if threshold > 0:
            if self.x > threshold:
                next_well = 1
            elif self.x < -threshold:
                next_well = -1
        if next_well != self.well:
            self.transitions += 1
            if self.last_transition is not None:
                self.residence_times.append(self.t - self.last_transition)
            self.last_transition = self.t
            self.well = next_well

    def sample(self):
        """Получить неизменяемую точку траектории для интерфейса."""
        return Sample(self.t, self.x, self.v, driving_force(self.t, self.parameters))
