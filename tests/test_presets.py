"""Показательный режим должен усиливать согласованный с силой отклик."""
from dataclasses import replace
import math
import unittest

from stochlab.model import Model, critical_force
from stochlab.presets import RESONANCE_PARAMETERS


def state_response(parameters):
    """Амплитуда первой гармоники стороны ямы после двух периодов разгона.

    Это проверка выбранного примера в тестах, а не новый режим интерфейса.
    Используется обычный интегратор без изменения или фильтрации траектории.
    """
    model = Model(parameters)
    period = 2*math.pi/parameters.omega
    sine = cosine = 0.0
    count = 0
    for _ in range(round(14*period/parameters.dt)):
        model.step()
        if model.t >= 2*period:
            state = 1 if model.x >= 0 else -1
            sine += state*math.sin(parameters.omega*model.t)
            cosine += state*math.cos(parameters.omega*model.t)
            count += 1
    return 2*math.hypot(sine, cosine)/count


class ResonancePresetTests(unittest.TestCase):
    def test_thermal_noise_enhances_driven_switching_for_the_selected_example(self):
        p = RESONANCE_PARAMETERS
        self.assertTrue(p.drive_enabled)
        self.assertGreater(p.T, 0)
        self.assertGreater(p.f, 0)
        self.assertLess(p.f, critical_force(p))
        low = state_response(replace(p, T=.025))
        resonance = state_response(p)
        high = state_response(replace(p, T=1.1))
        self.assertGreater(resonance, .5)
        self.assertGreater(resonance, 2*low)
        self.assertGreater(resonance, 2*high)
