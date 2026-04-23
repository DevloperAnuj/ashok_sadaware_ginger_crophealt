THRESHOLDS = {
    "temperature": {
        "critical_low": 15.0,
        "warning_low": 20.0,
        "warning_high": 32.0,
        "critical_high": 38.0,
    },
    "humidity": {
        "critical_low": 30.0,
        "warning_low": 40.0,
        "warning_high": 75.0,
        "critical_high": 85.0,
    },
    "soil_moisture": {
        "critical_low": 20.0,
        "warning_low": 30.0,
        "warning_high": 70.0,
        "critical_high": 85.0,
    },
    "soil_ph": {
        "critical_low": 4.5,
        "optimal_low": 5.5,
        "optimal_high": 7.0,
        "critical_high": 8.0,
    },
    "light_intensity": {
        "critical_low": 50.0,
        "warning_low": 100.0,
    },
}


def get_alerts(data: dict) -> list[dict]:
    """Return a list of alert dicts with keys: level, message, type (error|warning)."""
    alerts = []

    temp = data.get("temperature", 25.0)
    t = THRESHOLDS["temperature"]
    if temp >= t["critical_high"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"Temperature critically high ({temp:.1f} °C) — heat stress risk."})
    elif temp <= t["critical_low"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"Temperature critically low ({temp:.1f} °C) — cold damage risk."})
    elif temp >= t["warning_high"]:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"Temperature elevated ({temp:.1f} °C) — monitor closely."})
    elif temp <= t["warning_low"]:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"Temperature low ({temp:.1f} °C) — growth may slow."})

    hum = data.get("humidity", 65.0)
    h = THRESHOLDS["humidity"]
    if hum >= h["critical_high"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"Humidity critically high ({hum:.1f} %) — high fungal disease risk."})
    elif hum <= h["critical_low"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"Humidity critically low ({hum:.1f} %) — dehydration risk."})
    elif hum >= h["warning_high"]:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"Humidity elevated ({hum:.1f} %) — watch for disease signs."})

    moist = data.get("soil_moisture", 55.0)
    m = THRESHOLDS["soil_moisture"]
    if moist >= m["critical_high"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"Soil moisture too high ({moist:.1f} %) — waterlogging / root rot risk."})
    elif moist <= m["critical_low"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"Soil moisture critically low ({moist:.1f} %) — irrigate immediately."})
    elif moist <= m["warning_low"]:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"Soil moisture low ({moist:.1f} %) — consider irrigation soon."})

    ph = data.get("soil_ph", 6.2)
    p = THRESHOLDS["soil_ph"]
    if ph <= p["critical_low"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"Soil pH too acidic ({ph:.2f}) — apply agricultural lime."})
    elif ph >= p["critical_high"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"Soil pH too alkaline ({ph:.2f}) — apply elemental sulfur."})
    elif ph < p["optimal_low"] or ph > p["optimal_high"]:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"Soil pH outside optimal range ({ph:.2f}) — optimal is 5.5–7.0."})

    light = data.get("light_intensity", 420.0)
    l = THRESHOLDS["light_intensity"]
    if light <= l["critical_low"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"Light intensity critically low ({light:.0f} lux) — photosynthesis impaired."})
    elif light <= l["warning_low"]:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"Light intensity low ({light:.0f} lux) — consider shade adjustment."})

    return alerts
