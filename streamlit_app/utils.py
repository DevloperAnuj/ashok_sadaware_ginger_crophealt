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
        "critical_low": 25.0,
        "warning_low": 40.0,
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
    # ── Module 1: New sensors ──────────────────────────────────────────────────
    "soil_temperature": {
        "critical_low": 15.0,
        "warning_low": 20.0,
        "warning_high": 30.0,
        "critical_high": 35.0,
    },
    "electrical_conductivity": {
        "optimal_low": 0.5,
        "optimal_high": 1.5,
        "warning_low": 0.3,
        "warning_high": 2.5,
        "critical_low": 0.1,
        "critical_high": 3.0,
    },
    "nitrogen": {
        "critical_low": 60.0,
        "warning_low": 80.0,
        "optimal_low": 80.0,
        "optimal_high": 150.0,
    },
    "phosphorus": {
        "critical_low": 15.0,
        "warning_low": 20.0,
        "optimal_low": 20.0,
        "optimal_high": 40.0,
    },
    "potassium": {
        "critical_low": 80.0,
        "warning_low": 100.0,
        "optimal_low": 100.0,
        "optimal_high": 200.0,
    },
    "rainfall": {
        "warning_high": 50.0,
        "critical_high": 100.0,
    },
}

# ── Moisture Classification (5-level) ──────────────────────────────────────────

def get_moisture_class(moisture_pct: float) -> dict:
    """
    Classify soil moisture into 5 levels per Module 1 spec.
    Returns dict with: class_name, severity, label, led_color, range_label.
    """
    if moisture_pct < 25:
        return {
            "class_name": "Critically Dry",
            "severity": "Critical",
            "label": "🔴 Critically Dry",
            "led_color": "#f44336",
            "range_label": "< 25%",
        }
    elif moisture_pct < 40:
        return {
            "class_name": "Moisture Deficit",
            "severity": "Warning",
            "label": "🟠 Moisture Deficit",
            "led_color": "#ff9800",
            "range_label": "25 – 40%",
        }
    elif moisture_pct <= 70:
        return {
            "class_name": "Optimal",
            "severity": "Normal",
            "label": "🟢 Optimal",
            "led_color": "#4caf50",
            "range_label": "40 – 70%",
        }
    elif moisture_pct <= 85:
        return {
            "class_name": "Surplus Moisture",
            "severity": "Warning",
            "label": "🟡 Surplus Moisture",
            "led_color": "#ffeb3b",
            "range_label": "70 – 85%",
        }
    else:
        return {
            "class_name": "Waterlogged",
            "severity": "Critical",
            "label": "🔴 Waterlogged",
            "led_color": "#f44336",
            "range_label": "> 85%",
        }


def get_moisture_led_color(moisture_class: str) -> str:
    """Return the LED color hex for a moisture class name."""
    mapping = {
        "Critically Dry": "#f44336",
        "Moisture Deficit": "#ff9800",
        "Optimal": "#4caf50",
        "Surplus Moisture": "#ffeb3b",
        "Waterlogged": "#f44336",
    }
    return mapping.get(moisture_class, "#4caf50")


# ── Irrigation Decision Engine ──────────────────────────────────────────────────

def get_irrigation_decision(moisture_class: str) -> dict:
    """
    Return irrigation recommendation based on moisture class.
    Returns dict with: action, message, relay, next_irrigation_min.
    """
    decisions = {
        "Critically Dry": {
            "action": "IRRIGATE_NOW",
            "relay": "ON",
            "next_irrigation_min": 0,
            "message": (
                "Trigger irrigation relay immediately. "
                "Activate drip for 45 min. "
                "Suggest mulching to retain moisture. "
                "Check for wilting symptoms."
            ),
        },
        "Moisture Deficit": {
            "action": "SCHEDULE",
            "relay": "ON",
            "next_irrigation_min": 360,
            "message": (
                "Schedule irrigation within 6 hours. "
                "Moisture low — irrigate before noon. "
                "Recommend 20–30 min drip cycle. "
                "Monitor next reading."
            ),
        },
        "Optimal": {
            "action": "NONE",
            "relay": "OFF",
            "next_irrigation_min": None,
            "message": (
                "Soil moisture optimal — no action. "
                "Continue monitoring every 2 hours."
            ),
        },
        "Surplus Moisture": {
            "action": "SUSPEND",
            "relay": "OFF",
            "next_irrigation_min": None,
            "message": (
                "Suspend irrigation. "
                "Excess moisture — risk of root rot. "
                "Open drainage channels. "
                "Reduce next irrigation cycle by 50%."
            ),
        },
        "Waterlogged": {
            "action": "DRAIN",
            "relay": "OFF",
            "next_irrigation_min": None,
            "message": (
                "Waterlogging detected — risk of soft rot and bacterial wilt. "
                "Immediate drainage required. "
                "Trigger drainage pump relay if present. "
                "Inspect rhizomes within 24 h."
            ),
        },
    }
    return decisions.get(moisture_class, decisions["Optimal"])


# ── NPK & pH Deficiency Alerts ─────────────────────────────────────────────────

def get_npk_alerts(data: dict) -> list[dict]:
    """
    Return a list of NPK/pH deficiency alerts with actionable farmer recommendations.
    Each alert has: level, type, message, parameter.
    """
    alerts = []
    ph = data.get("soil_ph", 6.2)
    n  = data.get("nitrogen", 120)
    p  = data.get("phosphorus", 30)
    k  = data.get("potassium", 150)

    # pH alerts
    if ph < 5.5:
        alerts.append({
            "level": "Warning", "type": "warning", "parameter": "pH",
            "message": f"Acidic soil detected (pH {ph:.2f}) — apply lime at 200 kg/ha. Retest after 7 days.",
        })
    elif ph > 7.0:
        alerts.append({
            "level": "Warning", "type": "warning", "parameter": "pH",
            "message": f"Alkaline soil detected (pH {ph:.2f}) — apply sulphur or organic compost. Risk of micronutrient lockout.",
        })

    # NPK alerts
    if n < 80:
        level = "Critical" if n < 60 else "Warning"
        alerts.append({
            "level": level, "type": "error" if n < 60 else "warning", "parameter": "N",
            "message": f"Nitrogen deficiency ({n:.0f} ppm) — apply urea 25 kg/ha or vermicompost. Yellowing expected in 5–7 days if untreated.",
        })

    if p < 20:
        level = "Critical" if p < 15 else "Warning"
        alerts.append({
            "level": level, "type": "error" if p < 15 else "warning", "parameter": "P",
            "message": f"Phosphorus low ({p:.0f} ppm) — apply SSP fertiliser. Affects root and rhizome development.",
        })

    if k < 100:
        level = "Critical" if k < 80 else "Warning"
        alerts.append({
            "level": level, "type": "error" if k < 80 else "warning", "parameter": "K",
            "message": f"Potassium deficiency ({k:.0f} ppm) — apply MOP. Risk of reduced disease resistance and poor rhizome fill.",
        })

    return alerts


# ── Module 2: Pest Data Catalog ──────────────────────────────────────────────────

PEST_CLASSES = {
    "Damage-Pest": {
        "class_name": "Damage-Pest",
        "causative_agent": "General pest complex",
        "visual_symptoms": "Chewed leaf margins, irregular holes, defoliation, visible pest damage",
        "severity": "Moderate",
        "severity_color": "#ff9800",
        "recommended_pesticide": "Broad-spectrum insecticide (Cypermethrin 0.01%) or neem-based spray",
        "alert_message": "General pest damage detected. Identify specific pest before treatment. Apply broad-spectrum insecticide if damage is severe. Monitor for specific pest signs.",
        "preventive_action": "Regular field scouting. Maintain crop hygiene. Use light traps for monitoring. Encourage natural predators.",
    },
    "Dehydrated": {
        "class_name": "Dehydrated",
        "causative_agent": "Abiotic stress — water deficiency",
        "visual_symptoms": "Leaf curling, yellowing, wilting, dry leaf tips, reduced turgor",
        "severity": "Moderate",
        "severity_color": "#ff9800",
        "recommended_pesticide": "None — irrigate immediately. Apply mulch to retain soil moisture.",
        "alert_message": "Dehydration symptoms detected. Check soil moisture and irrigate immediately. Apply mulch to reduce evaporation. Monitor for recovery within 24 hours.",
        "preventive_action": "Maintain regular irrigation schedule. Apply organic mulch. Monitor soil moisture levels daily. Provide shade during heat waves.",
    },
    "Healthy": {
        "class_name": "Healthy",
        "causative_agent": None,
        "visual_symptoms": "Clean leaf, vibrant green colour, no holes or discolouration, normal turgor",
        "severity": "Normal",
        "severity_color": "#4caf50",
        "recommended_pesticide": "None",
        "alert_message": "No pest detected. Continue weekly monitoring. Schedule next inspection in 7 days.",
        "preventive_action": "Maintain regular monitoring schedule. Ensure optimal field hygiene. Continue irrigation and nutrient management.",
    },
    "Leaf roller": {
        "class_name": "Leaf Roller",
        "causative_agent": "Udaspes folus",
        "visual_symptoms": "Leaves rolled and bound with silk thread, feeding inside the roll",
        "severity": "Moderate",
        "severity_color": "#ff9800",
        "recommended_pesticide": "Malathion 0.1% or Trichogramma parasitoids (biological control)",
        "alert_message": "Leaf roller detected. Manually unroll and crush larvae. Spray Malathion 0.1% or release Trichogramma parasitoids as biological control.",
        "preventive_action": "Manually unroll and crush larvae. Release Trichogramma parasitoids as biological control. Maintain natural enemy populations.",
    },
    "Leaf-blight": {
        "class_name": "Leaf-blight",
        "causative_agent": "Fungal pathogen (Alternaria spp. / Colletotrichum spp.)",
        "visual_symptoms": "Brown/black necrotic spots on leaves, yellow halos around lesions, leaf tip dieback",
        "severity": "Critical",
        "severity_color": "#f44336",
        "recommended_pesticide": "Mancozeb 0.25% or Copper oxychloride 0.3% — apply as foliar spray",
        "alert_message": "Leaf blight detected. Apply Mancozeb 0.25% or Copper oxychloride 0.3% immediately. Remove severely affected leaves. Improve air circulation and avoid overhead irrigation.",
        "preventive_action": "Ensure proper plant spacing for air circulation. Avoid overhead irrigation. Remove and destroy infected plant debris. Practice crop rotation with non-host crops.",
    },
    "Mite infestation": {
        "class_name": "Mite Infestation",
        "causative_agent": "Polyphagotarsonemus latus",
        "visual_symptoms": "Bronze discolouration, fine webbing on leaf underside, leaf distortion",
        "severity": "Moderate",
        "severity_color": "#ff9800",
        "recommended_pesticide": "Dicofol 0.05% or Spiromesifen",
        "alert_message": "Mite damage detected. Spray Dicofol 0.05% or Spiromesifen. Avoid dusty field conditions. Increase irrigation frequency slightly to raise humidity.",
        "preventive_action": "Avoid dusty field conditions. Maintain slightly higher humidity through light irrigation. Remove weed hosts. Monitor leaf undersides regularly.",
    },
    "Rhizome scale": {
        "class_name": "Rhizome Scale",
        "causative_agent": "Aspidiella hartii",
        "visual_symptoms": "White/grey encrustations on rhizome surface, stunted shoot emergence",
        "severity": "Critical",
        "severity_color": "#f44336",
        "recommended_pesticide": "Quinalphos 0.075%",
        "alert_message": "Rhizome scale infestation. Treat seed rhizomes with Quinalphos 0.075% before planting. Remove heavily infested clumps. Avoid waterlogging.",
        "preventive_action": "Treat seed rhizomes before planting. Remove heavily infested clumps. Ensure good drainage. Practice crop rotation.",
    },
    "Shoot borer": {
        "class_name": "Shoot Borer",
        "causative_agent": "Conogethes punctiferalis",
        "visual_symptoms": "Entry holes at pseudostem base, frass accumulation, wilting central shoot ('dead heart')",
        "severity": "Critical",
        "severity_color": "#f44336",
        "recommended_pesticide": "Chlorpyriphos 0.05% or neem-based spray",
        "alert_message": "Shoot borer detected. Remove and destroy infested shoots immediately. Apply Chlorpyriphos 0.05% or neem-based spray. Install pheromone traps 5 m apart.",
        "preventive_action": "Install pheromone traps at 5 m spacing. Remove and destroy infested shoots promptly. Avoid monocropping; practice crop rotation with cereals.",
    },
    "Thrips": {
        "class_name": "Thrips",
        "causative_agent": "Scirtothrips dorsalis",
        "visual_symptoms": "Silvery streaks on leaf surface, curling leaf margins, stippling",
        "severity": "Moderate",
        "severity_color": "#ff9800",
        "recommended_pesticide": "Spinosad 0.01% or neem oil 3%",
        "alert_message": "Thrips infestation. Apply blue sticky traps at canopy level. Spray Spinosad 0.01% or neem oil 3%. Increase humidity by light irrigation.",
        "preventive_action": "Install blue sticky traps at canopy level. Avoid water stress. Maintain light irrigation to increase humidity. Use reflective mulch.",
    },
}

PEST_KEYS = list(PEST_CLASSES.keys())


def get_pest_risk_level(data: dict) -> dict:
    """
    Compute pest risk level from environmental conditions.
    Returns dict with: level, color, message.
    """
    temp = data.get("temperature", 27.0)
    hum = data.get("humidity", 65.0)
    dsls = data.get("days_since_last_spray", 0)

    # Pest-favorable conditions
    temp_favorable = 22 <= temp <= 35
    hum_favorable = hum > 70
    spray_overdue = dsls > 14

    if temp_favorable and hum_favorable and spray_overdue:
        return {
            "level": "High",
            "color": "#f44336",
            "message": f"High pest risk — warm, humid ({temp:.0f}°C, {hum:.0f}%) and no spray for {dsls:.0f} days. Schedule spraying immediately.",
        }
    elif (temp_favorable and hum_favorable) or spray_overdue:
        return {
            "level": "Moderate",
            "color": "#ff9800",
            "message": f"Moderate pest risk — conditions favorable ({temp:.0f}°C, {hum:.0f}%). Monitor crops closely.",
        }
    else:
        return {
            "level": "Low",
            "color": "#4caf50",
            "message": "Low pest risk — environmental conditions not favorable for pest outbreak.",
        }


def get_pest_alerts(data: dict) -> list[dict]:
    """Return pest-specific alerts based on environmental conditions."""
    alerts = []
    risk = get_pest_risk_level(data)
    if risk["level"] == "High":
        alerts.append({
            "level": "Critical", "type": "error",
            "message": risk["message"],
        })
    elif risk["level"] == "Moderate":
        alerts.append({
            "level": "Warning", "type": "warning",
            "message": risk["message"],
        })
    return alerts


def simulate_pest_detection() -> dict:
    """
    Simulate a pest detection result (for when no real ML model is available).
    Returns a dict with keys matching PEST_CLASSES entry + confidence.
    """
    import random
    # Weighted: 30% Healthy, rest distributed across other classes
    weights = [8, 8, 30, 8, 10, 8, 10, 10, 8]
    pest_key = random.choices(PEST_KEYS, weights=weights, k=1)[0]
    pest = PEST_CLASSES[pest_key]
    confidence = random.uniform(0.65, 0.98)
    return {
        "pest_key": pest_key,
        "class_name": pest["class_name"],
        "causative_agent": pest["causative_agent"],
        "visual_symptoms": pest["visual_symptoms"],
        "severity": pest["severity"],
        "severity_color": pest["severity_color"],
        "recommended_pesticide": pest["recommended_pesticide"],
        "alert_message": pest["alert_message"],
        "preventive_action": pest["preventive_action"],
        "confidence": round(confidence, 3),
    }


# ── General Alerts (all sensors) ────────────────────────────────────────────────

def get_alerts(data: dict) -> list[dict]:
    """Return a list of alert dicts with keys: level, message, type (error|warning)."""
    alerts = []

    # ── Ambient temperature ────────────────────────────────────────────────────
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

    # ── Humidity ───────────────────────────────────────────────────────────────
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

    # ── Soil moisture (5-level) ────────────────────────────────────────────────
    moist = data.get("soil_moisture", 55.0)
    m_class = get_moisture_class(moist)
    if m_class["severity"] == "Critical":
        if moist > 85:
            alerts.append({"level": "Critical", "type": "error",
                            "message": f"Waterlogged ({moist:.1f} %) — immediate drainage required. Risk of soft rot and bacterial wilt."})
        else:
            alerts.append({"level": "Critical", "type": "error",
                            "message": f"Soil critically dry ({moist:.1f} %) — trigger irrigation relay immediately."})
    elif m_class["severity"] == "Warning":
        if moist > 70:
            alerts.append({"level": "Warning", "type": "warning",
                            "message": f"Excess moisture ({moist:.1f} %) — suspend irrigation, risk of root rot."})
        else:
            alerts.append({"level": "Warning", "type": "warning",
                            "message": f"Moisture deficit ({moist:.1f} %) — schedule irrigation within 6 hours."})

    # ── Soil pH ────────────────────────────────────────────────────────────────
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

    # ── Light intensity ────────────────────────────────────────────────────────
    light = data.get("light_intensity", 420.0)
    l = THRESHOLDS["light_intensity"]
    if light <= l["critical_low"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"Light intensity critically low ({light:.0f} lux) — photosynthesis impaired."})
    elif light <= l["warning_low"]:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"Light intensity low ({light:.0f} lux) — consider shade adjustment."})

    # ── Module 1: New sensor alerts ────────────────────────────────────────────

    # Soil temperature
    st_temp = data.get("soil_temperature", 25.0)
    st = THRESHOLDS["soil_temperature"]
    if st_temp >= st["critical_high"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"Soil temperature critically high ({st_temp:.1f} °C) — root damage risk."})
    elif st_temp <= st["critical_low"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"Soil temperature critically low ({st_temp:.1f} °C) — root growth inhibited."})
    elif st_temp >= st["warning_high"]:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"Soil temperature elevated ({st_temp:.1f} °C) — monitor root zone."})
    elif st_temp <= st["warning_low"]:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"Soil temperature low ({st_temp:.1f} °C) — microbial activity reduced."})

    # Electrical conductivity
    ec = data.get("electrical_conductivity", 1.0)
    e = THRESHOLDS["electrical_conductivity"]
    if ec >= e["critical_high"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"EC critically high ({ec:.2f} mS/cm) — salinity stress, risk of root burn."})
    elif ec <= e["critical_low"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"EC critically low ({ec:.2f} mS/cm) — insufficient nutrients available."})
    elif ec >= e["warning_high"]:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"EC elevated ({ec:.2f} mS/cm) — monitor salt accumulation."})
    elif ec <= e["warning_low"]:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"EC low ({ec:.2f} mS/cm) — consider fertilisation."})

    # Nitrogen
    n = data.get("nitrogen", 120)
    n_th = THRESHOLDS["nitrogen"]
    if n <= n_th["critical_low"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"Nitrogen critically low ({n:.0f} ppm) — severe deficiency, apply urea 25 kg/ha immediately."})
    elif n <= n_th["warning_low"]:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"Nitrogen low ({n:.0f} ppm) — apply urea or vermicompost soon."})

    # Phosphorus
    phos = data.get("phosphorus", 30)
    ph_th = THRESHOLDS["phosphorus"]
    if phos <= ph_th["critical_low"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"Phosphorus critically low ({phos:.0f} ppm) — apply SSP fertiliser immediately."})
    elif phos <= ph_th["warning_low"]:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"Phosphorus low ({phos:.0f} ppm) — apply SSP fertiliser."})

    # Potassium
    pot = data.get("potassium", 150)
    k_th = THRESHOLDS["potassium"]
    if pot <= k_th["critical_low"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"Potassium critically low ({pot:.0f} ppm) — apply MOP immediately."})
    elif pot <= k_th["warning_low"]:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"Potassium low ({pot:.0f} ppm) — apply MOP. Risk of reduced disease resistance."})

    # Rainfall
    rain = data.get("rainfall", 0.0)
    r = THRESHOLDS["rainfall"]
    if rain >= r["critical_high"]:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"Heavy rainfall ({rain:.1f} mm) — risk of waterlogging and fungal outbreak. Ensure drainage."})
    elif rain >= r["warning_high"]:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"Significant rainfall ({rain:.1f} mm) — monitor soil moisture and disease risk."})

    # Days since irrigation
    dsi = data.get("days_since_irrigation", 0)
    if dsi > 7:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"No irrigation for {dsi:.0f} days — check soil moisture, consider irrigation if dry."})
    elif dsi > 14:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"No irrigation for {dsi:.0f} days — drought stress likely. Irrigate immediately."})

    # ── Module 2: Pest alerts ─────────────────────────────────────────────────────
    dsls = data.get("days_since_last_spray", 0)
    if dsls > 14:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"No pesticide spray for {dsls:.0f} days — pest risk elevated. Consider scheduled spraying."})
    elif dsls > 21:
        alerts.append({"level": "Critical", "type": "error",
                        "message": f"No pesticide spray for {dsls:.0f} days — high pest risk. Schedule spray immediately."})

    hum = data.get("humidity", 65.0)
    temp = data.get("temperature", 27.0)
    if hum > 75 and 25 <= temp <= 35:
        alerts.append({"level": "Warning", "type": "warning",
                        "message": f"Warm and humid conditions ({temp:.1f}°C, {hum:.1f}%) — favorable for pest outbreak. Increase monitoring frequency."})

    return alerts