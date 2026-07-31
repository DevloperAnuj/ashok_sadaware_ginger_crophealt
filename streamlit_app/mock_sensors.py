import random


class SensorSimulator:
    """Simulates IoT sensor readings using a bounded random walk."""

    def __init__(self):
        self._state = {
            # Original sensors (kept for backward compatibility)
            "temperature": 27.0,
            "humidity": 65.0,
            "soil_moisture": 55.0,
            "soil_ph": 6.2,
            "light_intensity": 420.0,
            # Module 1: Soil & environment
            "soil_temperature": 26.0,
            "electrical_conductivity": 1.0,
            "nitrogen": 120.0,
            "phosphorus": 30.0,
            "potassium": 150.0,
            "rainfall": 0.0,
            "days_since_irrigation": 0.0,
            # Module 2: Pest monitoring
            "days_since_last_spray": 7.0,
            "pest_risk_score": 0.0,
        }
        self._bounds = {
            "temperature": (14.0, 46.0),
            "humidity": (25.0, 100.0),
            "soil_moisture": (10.0, 100.0),
            "soil_ph": (3.8, 9.0),
            "light_intensity": (0.0, 1000.0),
            # Module 1
            "soil_temperature": (12.0, 40.0),
            "electrical_conductivity": (0.0, 4.0),
            "nitrogen": (40.0, 200.0),
            "phosphorus": (5.0, 60.0),
            "potassium": (50.0, 300.0),
            "rainfall": (0.0, 150.0),
            "days_since_irrigation": (0.0, 30.0),
            # Module 2
            "days_since_last_spray": (0.0, 60.0),
            "pest_risk_score": (0.0, 1.0),
        }
        self._step = {
            "temperature": 0.4,
            "humidity": 1.2,
            "soil_moisture": 0.8,
            "soil_ph": 0.04,
            "light_intensity": 18.0,
            # Module 1
            "soil_temperature": 0.3,
            "electrical_conductivity": 0.05,
            "nitrogen": 0.3,      # slow drift to simulate nutrient depletion
            "phosphorus": 0.1,    # slow drift
            "potassium": 0.4,     # slow drift
            "rainfall": 0.0,      # handled specially below
            "days_since_irrigation": 0.0,  # handled specially below
            # Module 2
            "days_since_last_spray": 0.0,  # handled specially below
            "pest_risk_score": 0.0,        # computed, not random walk
        }
        # NPK depletion counter: every N reads, decrement NPK slightly
        self._read_count = 0

    def read(self) -> dict:
        """Return one sensor reading, advancing each value by a bounded random walk."""
        self._read_count += 1
        for key in self._state:
            # Special handling for rainfall
            if key == "rainfall":
                # 8% chance of rain event, otherwise 0
                if random.random() < 0.08:
                    self._state[key] = random.uniform(2.0, 25.0)
                else:
                    # Decay existing rainfall toward 0
                    self._state[key] = max(0.0, self._state[key] - random.uniform(0.5, 3.0))
                continue

            # Special handling for days_since_irrigation
            if key == "days_since_irrigation":
                # Increment by ~1 day per 60 reads (roughly 1 day per 2 min of auto-refresh)
                self._state[key] += 1.0 / 60.0
                # Cap at 30 days
                if self._state[key] > 30:
                    self._state[key] = 30.0
                continue

            # Special handling for days_since_last_spray
            if key == "days_since_last_spray":
                # Increment by ~1 day per 60 reads (same pattern as days_since_irrigation)
                self._state[key] += 1.0 / 60.0
                # Cap at 60 days
                if self._state[key] > 60:
                    self._state[key] = 60.0
                continue

            # Special handling for pest_risk_score (computed from temp/humidity)
            if key == "pest_risk_score":
                temp = self._state["temperature"]
                hum = self._state["humidity"]
                dsls = self._state["days_since_last_spray"]
                # Score: 0.0 (low risk) to 1.0 (high risk)
                score = 0.0
                if 22 <= temp <= 35:
                    score += 0.3
                if hum > 70:
                    score += 0.3
                if dsls > 14:
                    score += 0.3
                if dsls > 21:
                    score += 0.1
                self._state[key] = min(1.0, score)
                continue

            # Normal random walk for all other sensors
            delta = random.uniform(-self._step[key], self._step[key])
            lo, hi = self._bounds[key]
            self._state[key] = max(lo, min(hi, self._state[key] + delta))

        # Gradual NPK nutrient depletion (simulates crop uptake)
        if self._read_count % 30 == 0:
            self._state["nitrogen"] = max(
                self._bounds["nitrogen"][0],
                self._state["nitrogen"] - random.uniform(0.5, 2.0)
            )
            self._state["phosphorus"] = max(
                self._bounds["phosphorus"][0],
                self._state["phosphorus"] - random.uniform(0.2, 1.0)
            )
            self._state["potassium"] = max(
                self._bounds["potassium"][0],
                self._state["potassium"] - random.uniform(0.5, 1.5)
            )

        return dict(self._state)

    def mark_irrigated(self):
        """Reset the days_since_irrigation counter (simulates irrigation event)."""
        self._state["days_since_irrigation"] = 0.0

    def mark_sprayed(self):
        """Reset the days_since_last_spray counter (simulates pesticide spray event)."""
        self._state["days_since_last_spray"] = 0.0