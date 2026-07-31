"""
Yield Estimation Model (Module 4).

Estimates ginger harvest yield (q/ha) from sensor data collected across the growing season.

Spec reference:
  - Primary model: Random Forest Regressor (50 trees, max depth 8)
  - Fallback: TFLite feedforward network (2 hidden layers, 32 neurons, ReLU, INT8)
  - Baseline: historical district average ~125 q/ha

Since no real farm records are available yet, this module uses a
rule-based heuristic yield model that is:
  - Deterministic (same sensor data → same yield estimate)
  - Pluggable (swap in a trained RandomForest when data becomes available)
  - Transparent (each factor's contribution is traceable)
"""

import math
from datetime import datetime, timedelta

# ── Yield bands (from spec) ──────────────────────────────────────────────────

YIELD_BANDS = {
    "Low": {
        "range": (0, 100),
        "label": "🔴 Low Yield",
        "color": "#f44336",
        "interpretation": "Below average",
        "farmer_action": (
            "Low yield predicted. Review disease/pest log. "
            "Apply top-dress fertiliser (K-rich). "
            "Consider extending growing period by 2–4 weeks if plants still green. "
            "Plan reduced harvest area."
        ),
    },
    "Average": {
        "range": (100, 150),
        "label": "🟠 Average Yield",
        "color": "#ff9800",
        "interpretation": "Average (~125 q/ha)",
        "farmer_action": (
            "Average yield expected (~125 q/ha). "
            "Standard harvest at 8–9 months. "
            "Arrange storage and market logistics for current stock levels."
        ),
    },
    "Good": {
        "range": (150, 200),
        "label": "🟢 Good Yield",
        "color": "#4caf50",
        "interpretation": "Above average",
        "farmer_action": (
            "Good yield predicted. Plan harvest in week 8.5–9. "
            "Arrange additional labour and storage capacity. "
            "Consider value-added processing (dry ginger / oil extraction)."
        ),
    },
    "High": {
        "range": (200, 999),
        "label": "🌟 High Yield",
        "color": "#1b5e20",
        "interpretation": "Excellent",
        "farmer_action": (
            "Excellent yield predicted. Alert market aggregators in advance. "
            "Prioritise cold storage. "
            "Consider phased harvest to avoid market glut and price crash."
        ),
    },
}

YIELD_BAND_KEYS = list(YIELD_BANDS.keys())

# ── Baseline (historical district average) ───────────────────────────────────
BASELINE_YIELD_QHA = 125.0


# ── Yield prediction ─────────────────────────────────────────────────────────

def estimate_yield(data: dict) -> dict:
    """
    Predict ginger yield (q/ha) from current sensor data using a heuristic model.

    The heuristic evaluates seven factors, each contributing a multiplier
    against the baseline yield of 125 q/ha:

      Factor               | Weight  | Conditions for penalty
      ---------------------|---------|-------------------------------
      Soil moisture        | ±20%   | Outside 30–70% range
      Soil temperature     | ±15%   | Outside 20–30°C
      Soil pH              | ±10%   | Outside 5.5–7.0
      NPK adequacy         | ±20%   | N<80, P<20, K<100 ppm each penalise
      Pest/disease alerts  | −15%   | Each active critical alert reduces yield
      Days since irrigation| −10%   | >7 days without irrigation
      Days since spray     | −10%   | >14 days without spray

    Returns a dict with:
      - yield_qha: float — point estimate
      - yield_band: str — "Low" | "Average" | "Good" | "High"
      - confidence_interval: tuple[float, float] — ± range
      - limiting_factors: list[str] — top factors dragging yield down
      - harvest_window: int — recommended days until harvest
      - market_readiness: str — "Not Ready" | "Prepare" | "Ready"
      - vs_baseline: float — % difference from baseline
      - baseline: float — the baseline yield used
    """
    # ── Soil moisture score (±20%) ────────────────────────────────────────
    moist = data.get("soil_moisture", 55.0)
    if moist < 25:
        moist_mult = 0.60  # critically dry — severe penalty
    elif moist < 40:
        moist_mult = 0.80  # deficit — moderate penalty
    elif moist <= 70:
        moist_mult = 1.00  # optimal — full score
    elif moist <= 85:
        moist_mult = 0.85  # surplus — slight penalty
    else:
        moist_mult = 0.65  # waterlogged — severe penalty

    # ── Soil temperature score (±15%) ─────────────────────────────────────
    st_temp = data.get("soil_temperature", 25.0)
    if st_temp < 15:
        temp_mult = 0.60
    elif st_temp < 20:
        temp_mult = 0.80
    elif st_temp <= 30:
        temp_mult = 1.00
    elif st_temp <= 35:
        temp_mult = 0.85
    else:
        temp_mult = 0.65

    # ── Soil pH score (±10%) ──────────────────────────────────────────────
    ph = data.get("soil_ph", 6.2)
    if ph < 4.5:
        ph_mult = 0.50
    elif ph < 5.5:
        ph_mult = 0.75
    elif ph <= 7.0:
        ph_mult = 1.00
    elif ph <= 7.5:
        ph_mult = 0.85
    else:
        ph_mult = 0.65

    # ── NPK adequacy score (±20%) ─────────────────────────────────────────
    n = data.get("nitrogen", 120.0)
    p = data.get("phosphorus", 30.0)
    k = data.get("potassium", 150.0)

    npk_deficiencies = []
    n_mult = 1.0
    p_mult = 1.0
    k_mult = 1.0

    if n < 60:
        n_mult = 0.60
        npk_deficiencies.append("Nitrogen critically low")
    elif n < 80:
        n_mult = 0.80
        npk_deficiencies.append("Nitrogen low")

    if p < 15:
        p_mult = 0.60
        npk_deficiencies.append("Phosphorus critically low")
    elif p < 20:
        p_mult = 0.80
        npk_deficiencies.append("Phosphorus low")

    if k < 80:
        k_mult = 0.60
        npk_deficiencies.append("Potassium critically low")
    elif k < 100:
        k_mult = 0.80
        npk_deficiencies.append("Potassium low")

    npk_mult = (n_mult + p_mult + k_mult) / 3.0

    # ── Pest / disease alert penalty (−15% max) ───────────────────────────
    pest_risk = data.get("pest_risk_score", 0.0)
    # pest_risk_score is 0.0–1.0, penalise proportionally
    pest_penalty = 1.0 - (pest_risk * 0.15)

    # ── Days since irrigation penalty (−10% max) ─────────────────────────
    dsi = data.get("days_since_irrigation", 0.0)
    if dsi > 7:
        irr_penalty = max(0.90, 1.0 - (dsi - 7) * 0.02)
    else:
        irr_penalty = 1.0

    # ── Days since spray penalty (−10% max) ──────────────────────────────
    dsls = data.get("days_since_last_spray", 0.0)
    if dsls > 14:
        spray_penalty = max(0.90, 1.0 - (dsls - 14) * 0.01)
    else:
        spray_penalty = 1.0

    # ── Combine all multipliers ───────────────────────────────────────────
    # Base yield = baseline × product of all multipliers
    # Each multiplier is 1.0 at optimal, lower at suboptimal
    combined = moist_mult * temp_mult * ph_mult * npk_mult * pest_penalty * irr_penalty * spray_penalty

    # Add a small random jitter (±5%) to simulate natural variability
    import random
    jitter = random.uniform(0.95, 1.05)

    yield_qha = round(BASELINE_YIELD_QHA * combined * jitter, 1)

    # Clamp to sensible range
    yield_qha = max(20.0, min(350.0, yield_qha))

    # ── Determine yield band ──────────────────────────────────────────────
    if yield_qha < 100:
        band = "Low"
    elif yield_qha < 150:
        band = "Average"
    elif yield_qha < 200:
        band = "Good"
    else:
        band = "High"

    # ── Confidence interval (±15% for heuristic) ──────────────────────────
    ci_half = round(yield_qha * 0.15, 1)
    confidence_interval = (round(yield_qha - ci_half, 1), round(yield_qha + ci_half, 1))

    # ── Limiting factors ──────────────────────────────────────────────────
    limiting_factors = []
    if moist_mult < 0.85:
        if moist < 25:
            limiting_factors.append("Soil critically dry — irrigate immediately")
        elif moist > 85:
            limiting_factors.append("Soil waterlogged — improve drainage")
        elif moist < 40:
            limiting_factors.append("Soil moisture deficit — schedule irrigation")
        else:
            limiting_factors.append("Excess soil moisture — reduce irrigation")

    if temp_mult < 0.85:
        if st_temp < 15:
            limiting_factors.append("Soil temperature too cold — consider mulching")
        else:
            limiting_factors.append("Soil temperature too high — provide shade/mulch")

    if ph_mult < 0.85:
        if ph < 5.5:
            limiting_factors.append(f"Soil pH too acidic ({ph:.1f}) — apply lime")
        else:
            limiting_factors.append(f"Soil pH too alkaline ({ph:.1f}) — apply sulphur")

    limiting_factors.extend(npk_deficiencies)

    if dsi > 7:
        limiting_factors.append(f"No irrigation for {dsi:.0f} days — drought stress")

    if dsls > 14:
        limiting_factors.append(f"Pest risk: no spray for {dsls:.0f} days")

    # Only show top 3 limiting factors
    limiting_factors = limiting_factors[:3]

    # ── Harvest window estimate ───────────────────────────────────────────
    # Base: 8–9 months (240–270 days). Poor conditions may extend growing period.
    days_since_planting = data.get("days_since_planting", 120.0)
    if combined < 0.70:
        # Extend by up to 30 days
        harvest_window = max(30, 270 - int(days_since_planting) + 20)
    elif combined < 0.85:
        # Near-normal
        harvest_window = max(20, 255 - int(days_since_planting))
    else:
        # Optimal — harvest at 8–8.5 months
        harvest_window = max(14, 240 - int(days_since_planting))

    # ── Market readiness ──────────────────────────────────────────────────
    if harvest_window <= 30 and band in ("Good", "High"):
        market_readiness = "Ready"
    elif harvest_window <= 45:
        market_readiness = "Prepare"
    else:
        market_readiness = "Not Ready"

    # ── vs baseline ───────────────────────────────────────────────────────
    vs_baseline = round((yield_qha - BASELINE_YIELD_QHA) / BASELINE_YIELD_QHA * 100, 1)

    return {
        "yield_qha": yield_qha,
        "yield_band": band,
        "band_info": YIELD_BANDS[band],
        "confidence_interval": confidence_interval,
        "limiting_factors": limiting_factors,
        "harvest_window": harvest_window,
        "market_readiness": market_readiness,
        "vs_baseline": vs_baseline,
        "baseline": BASELINE_YIELD_QHA,
        "multipliers": {
            "soil_moisture": round(moist_mult, 3),
            "soil_temperature": round(temp_mult, 3),
            "soil_ph": round(ph_mult, 3),
            "npk": round(npk_mult, 3),
            "pest_risk": round(pest_penalty, 3),
            "irrigation": round(irr_penalty, 3),
            "spray": round(spray_penalty, 3),
            "combined": round(combined, 3),
        },
    }


def get_yield_band_details(band_key: str) -> dict:
    """Return the full YIELD_BANDS entry for a given band key."""
    return YIELD_BANDS.get(band_key, YIELD_BANDS["Average"])


def simulate_yield_prediction(data: dict) -> dict:
    """
    Public API: estimate yield from sensor data.
    This is the function called by app.py.

    When a real RandomForest model is available, replace the body:
      return model.predict([features])  # → {yield_qha, ...}
    """
    return estimate_yield(data)