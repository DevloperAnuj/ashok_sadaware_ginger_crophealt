import random


class SensorSimulator:
    """Simulates IoT sensor readings using a bounded random walk."""

    def __init__(self):
        self._state = {
            "temperature": 27.0,
            "humidity": 65.0,
            "soil_moisture": 55.0,
            "soil_ph": 6.2,
            "light_intensity": 420.0,
        }
        self._bounds = {
            "temperature": (14.0, 46.0),
            "humidity": (25.0, 100.0),
            "soil_moisture": (10.0, 100.0),
            "soil_ph": (3.8, 9.0),
            "light_intensity": (0.0, 1000.0),
        }
        self._step = {
            "temperature": 0.4,
            "humidity": 1.2,
            "soil_moisture": 0.8,
            "soil_ph": 0.04,
            "light_intensity": 18.0,
        }

    def read(self) -> dict:
        """Return one sensor reading, advancing each value by a bounded random walk."""
        for key in self._state:
            delta = random.uniform(-self._step[key], self._step[key])
            lo, hi = self._bounds[key]
            self._state[key] = max(lo, min(hi, self._state[key] + delta))
        return dict(self._state)
