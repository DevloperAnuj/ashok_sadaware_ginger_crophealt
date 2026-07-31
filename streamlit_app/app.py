import time
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

from bluetooth_reader import BluetoothReader
from camera_detection import render_live_detection_page
from mock_sensors import SensorSimulator
from model_loader import load_model
from pest_prediction import load_pest_model, predict_pest
from prediction import predict
from utils import (
    THRESHOLDS,
    get_alerts,
    get_moisture_class,
    get_irrigation_decision,
    get_npk_alerts,
    get_moisture_led_color,
    PEST_CLASSES,
    PEST_KEYS,
    get_pest_risk_level,
    get_pest_alerts,
    simulate_pest_detection,
)
from yield_estimation import (
    YIELD_BANDS,
    YIELD_BAND_KEYS,
    simulate_yield_prediction,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Ginger Crop Health Monitor",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #061510 0%, #0c2218 55%, #143020 100%);
    border-right: 1px solid rgba(76,175,80,0.18);
}
[data-testid="stSidebarNav"] { display: none; }

/* Metric tiles */
[data-testid="stMetricValue"] {
    font-size: 2rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.02em;
}
[data-testid="stMetricLabel"] {
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    opacity: 0.65;
}

/* Card wrapper — applied via st.container with border=True */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 14px !important;
    border-color: rgba(76,175,80,0.22) !important;
    background: rgba(76,175,80,0.03) !important;
    padding: 0.25rem 0.25rem !important;
}

/* Tab strip */
[data-testid="stTabs"] button {
    font-size: 0.8rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

/* Gradient headings */
.page-title {
    font-size: 2.1rem;
    font-weight: 900;
    background: linear-gradient(100deg, #4caf50 0%, #a5d6a7 60%, #ffffff 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.15rem;
}
.section-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: #4caf50;
    font-weight: 700;
    margin: 1.4rem 0 0.4rem 0;
}
.glow-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(76,175,80,0.4), transparent);
    border: none;
    margin: 1.2rem 0;
}
/* Status pill */
.pill-ok   { display:inline-block; padding:2px 10px; border-radius:999px; background:#4caf5030; color:#81c784; font-size:0.78rem; font-weight:700; border:1px solid #4caf5060; }
.pill-warn { display:inline-block; padding:2px 10px; border-radius:999px; background:#ff980030; color:#ffb74d; font-size:0.78rem; font-weight:700; border:1px solid #ff980060; }
.pill-crit { display:inline-block; padding:2px 10px; border-radius:999px; background:#f4433630; color:#ef9a9a; font-size:0.78rem; font-weight:700; border:1px solid #f4433660; }
/* Score ring background */
.score-wrap {
    text-align:center;
    padding: 0.6rem 0;
}
</style>
""", unsafe_allow_html=True)

# ── Sensor metadata ───────────────────────────────────────────────────────────
SENSORS = [
    # Soil group
    {"key": "soil_moisture",       "label": "Soil Moisture",    "unit": "%",    "icon": "🌱"},
    {"key": "soil_temperature",    "label": "Soil Temp",        "unit": "°C",   "icon": "🌡"},
    {"key": "soil_ph",             "label": "Soil pH",          "unit": "",     "icon": "⚗"},
    {"key": "electrical_conductivity", "label": "EC",           "unit": "mS/cm","icon": "⚡"},
    # NPK group
    {"key": "nitrogen",            "label": "Nitrogen (N)",     "unit": "ppm",  "icon": "🧪"},
    {"key": "phosphorus",          "label": "Phosphorus (P)",   "unit": "ppm",  "icon": "🧪"},
    {"key": "potassium",           "label": "Potassium (K)",    "unit": "ppm",  "icon": "🧪"},
    # Environment group
    {"key": "rainfall",            "label": "Rainfall",         "unit": "mm",   "icon": "🌧"},
    {"key": "days_since_irrigation","label": "Days Since Irr.", "unit": "d",    "icon": "📅"},
]

# ── Session state ─────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history: list[dict] = []
if "simulator" not in st.session_state:
    st.session_state.simulator = SensorSimulator()
if "current_data" not in st.session_state:
    st.session_state.current_data: dict = {}
if "data_source" not in st.session_state:
    st.session_state.data_source = "Historical Data"
if "bt_reader" not in st.session_state:
    st.session_state.bt_reader = BluetoothReader()
if "irrigation_relay_on" not in st.session_state:
    st.session_state.irrigation_relay_on = False
if "irrigation_history" not in st.session_state:
    st.session_state.irrigation_history: list[dict] = []
if "pest_detection_result" not in st.session_state:
    st.session_state.pest_detection_result: dict | None = None
if "spray_history" not in st.session_state:
    st.session_state.spray_history: list[dict] = []
if "yield_prediction" not in st.session_state:
    st.session_state.yield_prediction: dict | None = None
if "yield_history" not in st.session_state:
    st.session_state.yield_history: list[dict] = []
if "days_since_planting" not in st.session_state:
    st.session_state.days_since_planting = 120.0
if "planting_density" not in st.session_state:
    st.session_state.planting_density = 12  # rhizomes/m²
if "variety" not in st.session_state:
    st.session_state.variety = "Local"
if "mulching_applied" not in st.session_state:
    st.session_state.mulching_applied = True

# ── Sensor tick — runs on every rerun regardless of page ─────────────────────
_bt: BluetoothReader = st.session_state.bt_reader
_sim: SensorSimulator = st.session_state.simulator

if st.session_state.data_source == "Bluetooth":
    if _bt.connected:
        _bt_data = _bt.get_latest()
        if _bt_data:
            # Hardware may not have all Module 1 sensors — fill missing from simulator
            _sim_data = _sim.read()
            _light = (st.session_state.current_data or {}).get("light_intensity") or _sim_data["light_intensity"]
            current_data = {
                **_bt_data,
                "light_intensity": _light,
                # Module 1: fill missing sensors from simulator
                "soil_temperature": _bt_data.get("soil_temperature") or _sim_data["soil_temperature"],
                "electrical_conductivity": _bt_data.get("electrical_conductivity") or _sim_data["electrical_conductivity"],
                "nitrogen": _bt_data.get("nitrogen") or _sim_data["nitrogen"],
                "phosphorus": _bt_data.get("phosphorus") or _sim_data["phosphorus"],
                "potassium": _bt_data.get("potassium") or _sim_data["potassium"],
                "rainfall": _bt_data.get("rainfall") or _sim_data["rainfall"],
                "days_since_irrigation": _bt_data.get("days_since_irrigation") or _sim_data["days_since_irrigation"],
            }
            st.session_state.current_data = current_data
            st.session_state.history.append({**current_data, "timestamp": datetime.now()})
        else:
            # Connected but no packet received yet — keep last data, don't add to history
            current_data = st.session_state.current_data or {}
    else:
        # Not connected — keep last known data, do not feed simulator values
        current_data = st.session_state.current_data or {}
else:
    # Historical Data
    current_data = _sim.read()
    st.session_state.current_data = current_data
    st.session_state.history.append({**current_data, "timestamp": datetime.now()})

if len(st.session_state.history) > 200:
    st.session_state.history = st.session_state.history[-200:]

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.markdown("## 🌿 Ginger Monitor")
st.sidebar.markdown('<hr style="border-color:rgba(76,175,80,0.2);margin:0.6rem 0;">', unsafe_allow_html=True)

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Leaf Detection", "Live Detection", "Pest Monitoring", "Irrigation Control", "Yield Estimation", "Sensor Data", "Alerts", "User Guide"],
    label_visibility="collapsed",
)

st.sidebar.markdown('<hr style="border-color:rgba(76,175,80,0.2);margin:0.6rem 0;">', unsafe_allow_html=True)

# ── Data Source panel ─────────────────────────────────────────────────────────
st.sidebar.markdown("#### 📡 Data Source")
_src = st.sidebar.radio(
    "Source",
    ["Historical Data", "Bluetooth (ESP32)"],
    index=0 if st.session_state.data_source == "Historical Data" else 1,
    label_visibility="collapsed",
)
st.session_state.data_source = "Bluetooth" if _src == "Bluetooth (ESP32)" else "Historical Data"

if st.session_state.data_source == "Bluetooth":
    _bt_ports = BluetoothReader.list_bt_ports()

    if not _bt_ports:
        st.sidebar.warning("No Bluetooth COM ports found.\nPair the ESP32 (GingerMonitor) via Windows Bluetooth settings first.")
    else:
        # Build label → device map  e.g. "COM5 — Standard Serial over Bluetooth link"
        _port_map = {f"{dev}  —  {desc}": dev for dev, desc in _bt_ports}
        _sel_label = st.sidebar.selectbox(
            "Bluetooth Port",
            list(_port_map.keys()),
            label_visibility="visible",
        )
        _sel_port = _port_map[_sel_label]

        _col_conn, _col_disc = st.sidebar.columns(2)
        with _col_conn:
            if st.button("Connect", use_container_width=True, disabled=_bt.connected):
                if _bt.connect(_sel_port):
                    st.rerun()
                else:
                    st.sidebar.error(f"Failed: {_bt.error}")
        with _col_disc:
            if st.button("Disconnect", use_container_width=True, disabled=not _bt.connected):
                _bt.disconnect()
                st.rerun()

    if _bt.connected:
        st.sidebar.success(f"Connected · **{_bt.device_name}** ({_bt.port})")
        _latest_bt = _bt.get_latest()
        if _latest_bt and 'temperature' in _latest_bt:
            st.sidebar.caption(
                f"T: {_latest_bt.get('temperature', '?')}°C  "
                f"H: {_latest_bt.get('humidity', '?')}%  "
                f"M: {_latest_bt.get('soil_moisture', '?')}%  "
                f"pH: {_latest_bt.get('soil_ph', '?')}"
            )
        else:
            st.sidebar.caption("Waiting for first packet…")

        # Live serial log
        _log_lines = _bt.get_log()
        if _log_lines:
            with st.sidebar.expander("Serial Log", expanded=False):
                st.caption(f"Showing last {min(len(_log_lines), 25)} lines. Max 200 total.")
                st.code("\n".join(_log_lines[-25:]), language=None)
        else:
            with st.sidebar.expander("Raw Bytes Log", expanded=False):
                _raw_log = _bt.get_raw_log()
                if _raw_log:
                    st.caption(f"Raw bytes received ({len(_raw_log)} packets)")
                    st.code("\n".join(_raw_log[-10:]), language=None)
                else:
                    st.caption("No raw bytes received yet.")
                    st.info("Trying to read data... Check if the ESP32 firmware is running and sending data.")
    else:
        st.sidebar.info("Not connected — select the Bluetooth port above and click Connect.")

st.sidebar.markdown('<hr style="border-color:rgba(76,175,80,0.2);margin:0.6rem 0;">', unsafe_allow_html=True)

# Only compute alerts when we have real data
if current_data:
    alerts = get_alerts(current_data)
    critical_count = sum(1 for a in alerts if a["level"] == "Critical")
    warning_count  = len(alerts)
else:
    alerts, critical_count, warning_count = [], 0, 0

if critical_count:
    st.sidebar.error(f"🚨  {critical_count} critical alert(s)")
elif warning_count:
    st.sidebar.warning(f"⚡  {warning_count} warning(s) active")
elif current_data:
    st.sidebar.success("✅  All systems normal")

if st.session_state.data_source == "Bluetooth" and _bt.connected:
    _src_label = f"{_bt.device_name} · {_bt.port}"
else:
    _src_label = "Historical Data"
st.sidebar.caption(f"Source: {_src_label} · {datetime.now().strftime('%H:%M:%S')}")

# ── Bluetooth connection gate — block all pages until connected ───────────────
if st.session_state.data_source == "Bluetooth" and not _bt.connected:
    st.markdown('<div class="page-title">Waiting for Hardware</div>', unsafe_allow_html=True)
    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)
    st.info(
        "**Bluetooth mode is active but no device is connected.**\n\n"
        "1. Make sure the ESP32 is powered on and Bluetooth is enabled on this PC.\n"
        "2. Pair **GingerMonitor** via **Windows Settings → Bluetooth & devices** (one-time).\n"
        "3. In the sidebar, select the correct **COM port** and click **Connect**.\n\n"
        "The dashboard will load automatically once data is received."
    )
    st.stop()


#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# HELPERS
#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

def compute_health_score(data: dict) -> int:
    score = 100

    # Ambient temperature
    t = data["temperature"]
    if t >= THRESHOLDS["temperature"]["critical_high"] or t <= THRESHOLDS["temperature"]["critical_low"]:
        score -= 16
    elif t >= THRESHOLDS["temperature"]["warning_high"] or t <= THRESHOLDS["temperature"]["warning_low"]:
        score -= 8

    # Humidity
    h = data["humidity"]
    if h >= THRESHOLDS["humidity"]["critical_high"] or h <= THRESHOLDS["humidity"]["critical_low"]:
        score -= 10
    elif h >= THRESHOLDS["humidity"]["warning_high"]:
        score -= 5

    # Soil moisture (5-level)
    m = data["soil_moisture"]
    if m >= 85 or m < 25:
        score -= 18
    elif m >= 70 or m < 40:
        score -= 8

    # Soil pH
    ph = data["soil_ph"]
    if ph <= THRESHOLDS["soil_ph"]["critical_low"] or ph >= THRESHOLDS["soil_ph"]["critical_high"]:
        score -= 12
    elif ph < THRESHOLDS["soil_ph"]["optimal_low"] or ph > THRESHOLDS["soil_ph"]["optimal_high"]:
        score -= 6

    # Light intensity
    lx = data.get("light_intensity", 420)
    if lx <= THRESHOLDS["light_intensity"]["critical_low"]:
        score -= 6
    elif lx <= THRESHOLDS["light_intensity"]["warning_low"]:
        score -= 3

    # Soil temperature
    st = data["soil_temperature"]
    sth = THRESHOLDS["soil_temperature"]
    if st >= sth["critical_high"] or st <= sth["critical_low"]:
        score -= 10
    elif st >= sth["warning_high"] or st <= sth["warning_low"]:
        score -= 5

    # Electrical conductivity
    ec = data["electrical_conductivity"]
    ech = THRESHOLDS["electrical_conductivity"]
    if ec >= ech["critical_high"] or ec <= ech["critical_low"]:
        score -= 8
    elif ec >= ech["warning_high"] or ec <= ech["warning_low"]:
        score -= 4

    # NPK levels
    n = data["nitrogen"]
    if n <= THRESHOLDS["nitrogen"]["critical_low"]:
        score -= 6
    elif n <= THRESHOLDS["nitrogen"]["warning_low"]:
        score -= 3

    p = data["phosphorus"]
    if p <= THRESHOLDS["phosphorus"]["critical_low"]:
        score -= 6
    elif p <= THRESHOLDS["phosphorus"]["warning_low"]:
        score -= 3

    k = data["potassium"]
    if k <= THRESHOLDS["potassium"]["critical_low"]:
        score -= 6
    elif k <= THRESHOLDS["potassium"]["warning_low"]:
        score -= 3

    # Rainfall
    rain = data.get("rainfall", 0)
    if rain >= THRESHOLDS["rainfall"]["critical_high"]:
        score -= 8
    elif rain >= THRESHOLDS["rainfall"]["warning_high"]:
        score -= 4

    # Days since irrigation
    dsi = data.get("days_since_irrigation", 0)
    if dsi > 14:
        score -= 10
    elif dsi > 7:
        score -= 5

    return max(0, score)


def _sensor_color(key: str, value: float) -> str:
    t = THRESHOLDS.get(key, {})
    if key == "temperature":
        if value >= t["critical_high"] or value <= t["critical_low"]: return "#f44336"
        if value >= t["warning_high"]  or value <= t["warning_low"]:  return "#ff9800"
    elif key == "humidity":
        if value >= t["critical_high"] or value <= t["critical_low"]: return "#f44336"
        if value >= t["warning_high"]:                                 return "#ff9800"
    elif key == "soil_moisture":
        if value >= 85 or value < 25: return "#f44336"
        if value >= 70 or value < 40: return "#ff9800"
    elif key == "soil_ph":
        if value <= t["critical_low"]  or value >= t["critical_high"]: return "#f44336"
        if value < t["optimal_low"]    or value > t["optimal_high"]:   return "#ff9800"
    elif key == "light_intensity":
        if value <= t["critical_low"]: return "#f44336"
        if value <= t["warning_low"]:  return "#ff9800"
    elif key == "soil_temperature":
        if value >= t["critical_high"] or value <= t["critical_low"]: return "#f44336"
        if value >= t["warning_high"]  or value <= t["warning_low"]:  return "#ff9800"
    elif key == "electrical_conductivity":
        if value >= t["critical_high"] or value <= t["critical_low"]: return "#f44336"
        if value >= t["warning_high"]  or value <= t["warning_low"]:  return "#ff9800"
    elif key in ("nitrogen", "phosphorus", "potassium"):
        if value <= t.get("critical_low", 0): return "#f44336"
        if value <= t.get("warning_low", 0):  return "#ff9800"
    elif key == "rainfall":
        if value >= t.get("critical_high", 999): return "#f44336"
        if value >= t.get("warning_high", 999):  return "#ff9800"
    elif key == "days_since_irrigation":
        if value > 14: return "#f44336"
        if value > 7:  return "#ff9800"
    return "#4caf50"


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def make_sparkline(values: list, color: str = "#4caf50") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=values,
        mode="lines",
        fill="tozeroy",
        line=dict(color=color, width=1.8, shape="spline"),
        fillcolor=_hex_to_rgba(color, 0.094),
        hoverinfo="none",
    ))
    fig.update_layout(
        height=68,
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
    )
    return fig


def plotly_base(height: int = 280, margin: dict | None = None) -> dict:
    return dict(
        height=height,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#d0d0d0", size=12),
        margin=margin if margin is not None else dict(l=10, r=10, t=36, b=10),
    )


#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PAGE: Dashboard
#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
if page == "Dashboard":
    st.markdown('<div class="page-title">Farm Dashboard</div>', unsafe_allow_html=True)
    st.caption("Live IoT sensor readings — auto-updates on every refresh")
    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)

    history = st.session_state.history
    prev = history[-2] if len(history) >= 2 else current_data

    # ── Health Score ──────────────────────────────────────────────────────────
    score = compute_health_score(current_data)
    score_color = "#4caf50" if score >= 70 else ("#ff9800" if score >= 45 else "#f44336")

    gauge_fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": "Farm Health Score", "font": {"size": 14, "color": "#9e9e9e"}},
        number={"suffix": " / 100", "font": {"size": 36, "color": score_color}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#555", "nticks": 6},
            "bar":  {"color": score_color, "thickness": 0.28},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [
                {"range": [0,  45], "color": "rgba(244,67,54,0.12)"},
                {"range": [45, 70], "color": "rgba(255,152,0,0.12)"},
                {"range": [70,100], "color": "rgba(76,175,80,0.12)"},
            ],
            "threshold": {
                "line": {"color": "rgba(255,255,255,0.25)", "width": 2},
                "thickness": 0.8,
                "value": 70,
            },
        },
    ))
    gauge_fig.update_layout(**plotly_base(height=220, margin=dict(l=20,r=20,t=20,b=0)))

    c_score, c_status = st.columns([1, 2])
    with c_score:
        st.plotly_chart(gauge_fig, use_container_width=True, config={"staticPlot": True})
    with c_status:
        st.markdown('<div class="section-label">Active Conditions</div>', unsafe_allow_html=True)
        if not alerts:
            st.success("All parameters within optimal range.")
        for a in alerts[:4]:
            if a["type"] == "error":
                st.error(a["message"], icon="🚨")
            else:
                st.warning(a["message"], icon="⚠️")
        if len(alerts) > 4:
            st.caption(f"…and {len(alerts) - 4} more alert(s) — see Alerts page.")

    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)

    # ── Sensor Cards (3×3 grid) ────────────────────────────────────────────────
    st.markdown('<div class="section-label">Live Sensor Readings</div>', unsafe_allow_html=True)

    recent_vals = {s["key"]: [h[s["key"]] for h in history[-40:]] for s in SENSORS}

    for row_i in range(3):
        cols = st.columns(3)
        for col_i in range(3):
            idx = row_i * 3 + col_i
            if idx >= len(SENSORS):
                break
            sensor = SENSORS[idx]
            key   = sensor["key"]
            val   = current_data[key]
            delta = val - prev[key]
            color = _sensor_color(key, val)
            spark_vals = recent_vals[key]

            with cols[col_i]:
                with st.container(border=True):
                    # Special formatting for NPK and pH (show decimals)
                    if key == "soil_ph":
                        delta_str = f"{delta:+.3f}"
                        val_str = f"{val:.2f}"
                    elif key == "electrical_conductivity":
                        delta_str = f"{delta:+.3f}"
                        val_str = f"{val:.2f}"
                    elif key == "days_since_irrigation":
                        delta_str = f"{delta:+.2f}"
                        val_str = f"{val:.1f}"
                    elif key == "rainfall":
                        delta_str = f"{delta:+.2f}"
                        val_str = f"{val:.1f}"
                    else:
                        delta_str = f"{delta:+.2f}"
                        val_str = f"{val:.1f}"

                    st.metric(
                        label=f"{sensor['icon']}  {sensor['label']}",
                        value=f"{val_str} {sensor['unit']}".strip(),
                        delta=delta_str,
                        delta_color="normal",
                    )
                    if len(spark_vals) > 2:
                        st.plotly_chart(
                            make_sparkline(spark_vals, color),
                            use_container_width=True,
                            config={"staticPlot": True},
                        )

    # ── Normalized overlay chart ───────────────────────────────────────────────
    st.markdown('<div class="section-label">All Sensors — Normalized Trend (40 reads)</div>', unsafe_allow_html=True)
    if len(history) > 3:
        df_mini = pd.DataFrame(history[-40:])
        norm_fig = go.Figure()
        palette = ["#4caf50","#2196f3","#ff9800","#e91e63","#ffeb3b","#9c27b0","#00bcd4","#ff5722","#795548"]
        for j, s in enumerate(SENSORS):
            vals = df_mini[s["key"]].tolist()
            lo, hi = min(vals), max(vals)
            normalised = [(v - lo) / (hi - lo + 1e-9) for v in vals]
            norm_fig.add_trace(go.Scatter(
                y=normalised, mode="lines",
                name=s["label"],
                line=dict(color=palette[j % len(palette)], width=1.5),
            ))
        norm_fig.update_layout(
            **plotly_base(140, margin=dict(l=0, r=0, t=28, b=0)),
            legend=dict(font=dict(size=9), orientation="h", y=-0.3),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False, range=[-0.05, 1.05]),
        )
        st.plotly_chart(norm_fig, use_container_width=True, config={"staticPlot": True})

    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)

    # ── Moisture Classification & Irrigation Panel ─────────────────────────────
    m_class = get_moisture_class(current_data["soil_moisture"])
    irr_decision = get_irrigation_decision(m_class["class_name"])

    col_mc, col_irr = st.columns([1, 1])
    with col_mc:
        with st.container(border=True):
            led_color = m_class["led_color"]
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:12px;margin-bottom:6px'>"
                f"<span style='display:inline-block;width:16px;height:16px;border-radius:50%;"
                f"background:{led_color};box-shadow:0 0 8px {led_color}80;'></span>"
                f"<span style='font-size:1.1rem;font-weight:700;'>Moisture: {m_class['label']}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<span style='color:#aaa;font-size:0.85rem'>Range: {m_class['range_label']} · "
                f"Current: {current_data['soil_moisture']:.1f}%</span>",
                unsafe_allow_html=True,
            )
            st.markdown(f"<div style='margin-top:8px;padding:8px;border-radius:8px;background:#ffffff08;font-size:0.9rem'>{irr_decision['message']}</div>", unsafe_allow_html=True)

    with col_irr:
        with st.container(border=True):
            st.markdown("**💧 Irrigation Control**")
            st.markdown(
                f"<span style='color:#aaa;font-size:0.85rem'>Days since last irrigation: "
                f"<b>{current_data['days_since_irrigation']:.0f}</b></span>",
                unsafe_allow_html=True,
            )
            relay_status = "🟢 ON" if st.session_state.irrigation_relay_on else "🔴 OFF"
            st.markdown(f"<span style='font-size:0.9rem'>Relay: <b>{relay_status}</b> · Action: <b>{irr_decision['action']}</b></span>", unsafe_allow_html=True)
            if irr_decision["relay"] == "ON" and not st.session_state.irrigation_relay_on:
                if st.button("💧  Activate Irrigation Relay", use_container_width=True):
                    st.session_state.irrigation_relay_on = True
                    st.session_state.irrigation_history.append({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "action": "Relay ON",
                        "moisture": f"{current_data['soil_moisture']:.1f}%",
                    })
                    _sim.mark_irrigated()
                    st.rerun()
            if st.session_state.irrigation_relay_on:
                if st.button("⏹  Turn Relay OFF", use_container_width=True):
                    st.session_state.irrigation_relay_on = False
                    st.session_state.irrigation_history.append({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "action": "Relay OFF",
                        "moisture": f"{current_data['soil_moisture']:.1f}%",
                    })
                    st.rerun()

    # ── NPK & pH Status Panel ──────────────────────────────────────────────────
    npk_alerts = get_npk_alerts(current_data)
    st.markdown('<div class="section-label">NPK & pH Status</div>', unsafe_allow_html=True)
    if npk_alerts:
        for a in npk_alerts:
            if a["type"] == "error":
                st.error(a["message"], icon="🚨")
            else:
                st.warning(a["message"], icon="⚠️")
    else:
        st.success("All NPK levels and pH within optimal range.")

    # ── NPK summary row ────────────────────────────────────────────────────────
    n_val = current_data["nitrogen"]
    p_val = current_data["phosphorus"]
    k_val = current_data["potassium"]
    c_n, c_p, c_k = st.columns(3)
    with c_n:
        n_color = _sensor_color("nitrogen", n_val)
        st.markdown(f"<span style='color:{n_color};font-weight:700'>N: {n_val:.0f} ppm</span>", unsafe_allow_html=True)
        st.caption("Optimal: 80–150 ppm")
    with c_p:
        p_color = _sensor_color("phosphorus", p_val)
        st.markdown(f"<span style='color:{p_color};font-weight:700'>P: {p_val:.0f} ppm</span>", unsafe_allow_html=True)
        st.caption("Optimal: 20–40 ppm")
    with c_k:
        k_color = _sensor_color("potassium", k_val)
        st.markdown(f"<span style='color:{k_color};font-weight:700'>K: {k_val:.0f} ppm</span>", unsafe_allow_html=True)
        st.caption("Optimal: 100–200 ppm")

    # ── Pest Risk Card ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Pest Risk Assessment</div>', unsafe_allow_html=True)
    pest_risk = get_pest_risk_level(current_data)
    pest_alerts = get_pest_alerts(current_data)
    col_pr1, col_pr2 = st.columns([1, 2])
    with col_pr1:
        risk_color = pest_risk["color"]
        st.markdown(
            f"<div style='text-align:center;padding:1rem;border-radius:12px;"
            f"background:{risk_color}15;border:2px solid {risk_color}60;'>"
            f"<div style='font-size:0.8rem;color:#aaa;text-transform:uppercase;letter-spacing:0.1em'>Pest Risk</div>"
            f"<div style='font-size:1.8rem;font-weight:900;color:{risk_color}'>{pest_risk['level']}</div>"
            f"<div style='color:#aaa;font-size:0.8rem'>Days since spray: {current_data.get('days_since_last_spray', 0):.0f}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_pr2:
        st.markdown(f"<div style='padding:8px;font-size:0.9rem'>{pest_risk['message']}</div>", unsafe_allow_html=True)
        if pest_alerts:
            for a in pest_alerts:
                if a["type"] == "error":
                    st.error(a["message"], icon="🐛")
                else:
                    st.warning(a["message"], icon="🐛")

    # ── Yield Estimation Card ──────────────────────────────────────────────────
    st.markdown('<div class="section-label">Yield Forecast</div>', unsafe_allow_html=True)
    _yield_data = {**current_data, "days_since_planting": st.session_state.days_since_planting}
    _yield_result = simulate_yield_prediction(_yield_data)
    _band = _yield_result["band_info"]
    col_y1, col_y2 = st.columns([1, 2])
    with col_y1:
        st.markdown(
            f"<div style='text-align:center;padding:1rem;border-radius:12px;"
            f"background:{_band['color']}15;border:2px solid {_band['color']}60;'>"
            f"<div style='font-size:0.8rem;color:#aaa;text-transform:uppercase;letter-spacing:0.1em'>Yield Forecast</div>"
            f"<div style='font-size:1.8rem;font-weight:900;color:{_band['color']}'>{_yield_result['yield_qha']} q/ha</div>"
            f"<div style='color:#aaa;font-size:0.8rem'>{_band['label']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_y2:
        st.markdown(
            f"<div style='padding:8px;font-size:0.9rem'>{_band['farmer_action'][:120]}…</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='font-size:0.8rem;color:#888'>"
            f"Baseline: {_yield_result['baseline']} q/ha · "
            f"Your forecast: {_yield_result['yield_qha']} q/ha "
            f"({_yield_result['vs_baseline']:+.1f}%) · "
            f"Limiting factors: {_yield_result['limiting_factors'][0] if _yield_result['limiting_factors'] else 'None'}"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)
    if st.session_state.data_source == "Bluetooth":
        time.sleep(2)
        st.rerun()
    else:
        c_btn, c_toggle = st.columns([1, 2])
        with c_btn:
            if st.button("⟳  Refresh Now", use_container_width=True):
                st.rerun()
        with c_toggle:
            if st.toggle("Auto-refresh every 5 s"):
                time.sleep(5)
                st.rerun()


#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PAGE: Leaf Detection
#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
elif page == "Leaf Detection":
    st.markdown('<div class="page-title">Leaf Disease Detection</div>', unsafe_allow_html=True)
    st.caption("Upload a ginger leaf photo — MobileNetV2 analyses and explains the result")
    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)

    model = load_model()
    if model is None:
        st.info(
            "**Model not available.** Train the model in Colab (`ginger_cnn_training.ipynb`) "
            "and place `ginger_disease_model.tflite` in `streamlit_app/models/`. "
            "The image analysis graphs below will still render from the raw image.",
            icon="ℹ️",
        )

    uploaded = st.file_uploader("Upload ginger leaf image (JPG / PNG)", type=["jpg", "jpeg", "png"])

    if uploaded is not None:
        pil_img = Image.open(uploaded).convert("RGB")
        img_array = np.array(pil_img.resize((224, 224)), dtype=np.float32)

        # Compute image-level stats regardless of model
        r_ch, g_ch, b_ch = img_array[:,:,0], img_array[:,:,1], img_array[:,:,2]
        green_mask  = (g_ch > r_ch * 1.05) & (g_ch > b_ch * 1.05) & (g_ch > 60)
        green_pct   = float(green_mask.mean() * 100)
        mean_bright = float(img_array.mean())

        # ── Top row: image + prediction ──────────────────────────────────────
        col_img, col_pred = st.columns([1, 1], gap="large")
        with col_img:
            st.image(pil_img, caption="Uploaded image", use_column_width="always")

        with col_pred:
            label, confidence, all_probs = None, None, None
            if model is not None:
                with st.spinner("Running MobileNetV2…"):
                    label, confidence, all_probs = predict(model, pil_img)

            if label is not None:
                # Map multi-class outputs to Healthy vs Unhealthy
                is_healthy = label == "Healthy"
                prob_healthy = confidence if is_healthy else 1.0 - confidence
                prob_disease = 1.0 - prob_healthy

                if confidence < 0.60:
                    st.warning(f"**Low Confidence · {label}** — {confidence*100:.1f} %\nRetake photo in better lighting.")
                elif is_healthy:
                    st.success(f"### 🌿 Healthy Plant\n**Confidence: {confidence*100:.1f} %**")
                    st.markdown("Maintain current conditions. Continue regular monitoring.")
                elif label == "Bacterial_Wilt":
                    st.error(f"### 🦠 Bacterial Wilt Detected\n**Confidence: {confidence*100:.1f} %**")
                    st.markdown("""
**Immediate Actions:**
- Apply copper-based bactericide.
- Remove & isolate infected rhizomes.
- Improve drainage, stop overhead irrigation.
""")
                elif label == "Leaf-blight":
                    st.error(f"### 🍂 Leaf Blight Detected\n**Confidence: {confidence*100:.1f} %**")
                    st.markdown("""
**Immediate Actions:**
- Apply Mancozeb 0.25% or Copper oxychloride 0.3%.
- Remove severely affected leaves.
- Improve air circulation, avoid overhead irrigation.
""")
                elif label == "Dehydrated":
                    st.warning(f"### 💧 Dehydration Symptoms\n**Confidence: {confidence*100:.1f} %**")
                    st.markdown("""
**Immediate Actions:**
- Check soil moisture and irrigate immediately.
- Apply mulch to retain soil moisture.
- Monitor for recovery within 24 hours.
""")
                else:
                    st.warning(f"### 🐛 {label} Detected\n**Confidence: {confidence*100:.1f} %**")
                    st.markdown(f"Check the **Pest Monitoring** page for detailed treatment recommendations.")
            else:
                st.info("Model not loaded — showing image analysis only below.")
                prob_healthy, prob_disease = 0.5, 0.5  # placeholder for charts

        # ── Analysis section ─────────────────────────────────────────────────
        st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Detection Reasoning — Visual Analysis</div>', unsafe_allow_html=True)

        tab1, tab2, tab3, tab4 = st.tabs([
            "Confidence Gauge",
            "Class Probabilities",
            "RGB Channel Analysis",
            "Pixel Health Map",
        ])

        # Tab 1: Confidence Gauge
        with tab1:
            if label is not None:
                gauge_color = "#4caf50" if label == "Healthy" else "#f44336"
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number+delta",
                    value=confidence * 100,
                    delta={"reference": 60, "valueformat": ".1f", "suffix": "% vs threshold"},
                    title={"text": f"Model Confidence · Predicted: <b>{label}</b>", "font": {"size": 14}},
                    number={"suffix": " %", "font": {"size": 42, "color": gauge_color}},
                    gauge={
                        "axis": {"range": [0, 100], "ticksuffix": "%", "nticks": 6},
                        "bar":  {"color": gauge_color, "thickness": 0.3},
                        "bgcolor": "rgba(0,0,0,0)",
                        "borderwidth": 0,
                        "steps": [
                            {"range": [0,  40], "color": "rgba(244,67,54,0.18)"},
                            {"range": [40, 60], "color": "rgba(255,152,0,0.18)"},
                            {"range": [60, 80], "color": "rgba(139,195,74,0.15)"},
                            {"range": [80,100], "color": "rgba(76,175,80,0.15)"},
                        ],
                        "threshold": {
                            "line": {"color": "rgba(255,255,255,0.67)", "width": 2},
                            "thickness": 0.85, "value": 60,
                        },
                    },
                ))
                fig_gauge.update_layout(**plotly_base(300, margin=dict(l=20,r=20,t=20,b=20)))
                st.plotly_chart(fig_gauge, use_container_width=True, config={"staticPlot": True})
                st.caption(
                    f"The model is **{confidence*100:.1f}% confident** this leaf is **{label}**. "
                    f"Predictions below 60% are flagged as low-confidence. "
                    f"The white line marks the 60% decision threshold."
                )
            else:
                st.info("Run the model to see the confidence gauge.")

        # Tab 2: Class Probabilities
        with tab2:
            if label is not None:
                if all_probs is not None:
                    # Multi-class model — show all 9 classes
                    cls_names = [p[0] for p in all_probs]
                    cls_vals  = [p[1] * 100 for p in all_probs]
                    colors = ["#4caf50" if n == "Healthy" else "#f44336" if n in ("Leaf-blight", "Bacterial_Wilt") else "#ff9800" for n in cls_names]
                    fig_bar = go.Figure()
                    fig_bar.add_trace(go.Bar(
                        x=cls_vals,
                        y=cls_names,
                        orientation="h",
                        marker=dict(color=colors, line=dict(color=colors, width=1.5)),
                        text=[f"{v:.1f}%" for v in cls_vals],
                        textposition="inside",
                        insidetextanchor="middle",
                        textfont=dict(size=13, color="white"),
                    ))
                    fig_bar.update_layout(
                        **plotly_base(300),
                        xaxis=dict(title="Probability (%)", range=[0, 100], gridcolor="#333"),
                        yaxis=dict(title=""),
                        showlegend=False,
                        bargap=0.25,
                    )
                    st.plotly_chart(fig_bar, use_container_width=True, config={"staticPlot": True})
                    st.caption(
                        f"Top prediction: **{label}** ({confidence*100:.1f}%). "
                        f"All 9 classes sorted by probability. "
                        f"The softmax output sums to 100%."
                    )
                else:
                    # Binary model — show 2 classes
                    fig_bar = go.Figure()
                    fig_bar.add_trace(go.Bar(
                        x=[prob_disease * 100, prob_healthy * 100],
                        y=["Bacterial Wilt", "Healthy"],
                        orientation="h",
                        marker=dict(
                            color=[
                                f"rgba(244,67,54,{0.4 + 0.5 * prob_disease})",
                                f"rgba(76,175,80,{0.4 + 0.5 * prob_healthy})",
                            ],
                            line=dict(color=["#f44336","#4caf50"], width=1.5),
                        ),
                        text=[f"{prob_disease*100:.1f}%", f"{prob_healthy*100:.1f}%"],
                        textposition="inside",
                        insidetextanchor="middle",
                        textfont=dict(size=15, color="white"),
                    ))
                    fig_bar.update_layout(
                        **plotly_base(220),
                        xaxis=dict(title="Probability (%)", range=[0, 100], gridcolor="#333"),
                        yaxis=dict(title=""),
                        showlegend=False,
                        bargap=0.35,
                    )
                    st.plotly_chart(fig_bar, use_container_width=True, config={"staticPlot": True})
                    st.caption(
                        f"P(Bacterial Wilt) = **{prob_disease*100:.1f}%** · "
                        f"P(Healthy) = **{prob_healthy*100:.1f}%**. "
                        f"The binary sigmoid output maps directly to these two complementary probabilities."
                    )
            else:
                st.info("Run the model to see class probabilities.")

        # Tab 3: RGB Channel Histogram
        with tab3:
            fig_rgb = go.Figure()
            ch_data  = [r_ch.flatten(), g_ch.flatten(), b_ch.flatten()]
            ch_names = ["Red", "Green", "Blue"]
            ch_colors = ["rgba(244,67,54,0.7)", "rgba(76,175,80,0.7)", "rgba(33,150,243,0.7)"]
            for vals, name, color in zip(ch_data, ch_names, ch_colors):
                fig_rgb.add_trace(go.Histogram(
                    x=vals, name=name, nbinsx=64,
                    marker_color=color,
                    opacity=0.75,
                ))
            fig_rgb.update_layout(
                **plotly_base(280),
                barmode="overlay",
                xaxis=dict(title="Pixel Intensity (0–255)", gridcolor="#333"),
                yaxis=dict(title="Pixel Count", gridcolor="#333"),
                legend=dict(orientation="h", y=1.08),
            )
            st.plotly_chart(fig_rgb, use_container_width=True, config={"staticPlot": True})

            g_mean = float(g_ch.mean())
            r_mean = float(r_ch.mean())
            b_mean = float(b_ch.mean())
            dominant = "Green" if g_mean >= r_mean and g_mean >= b_mean else ("Red" if r_mean >= b_mean else "Blue")
            st.caption(
                f"Channel means — R: {r_mean:.1f} · G: {g_mean:.1f} · B: {b_mean:.1f}. "
                f"Dominant channel: **{dominant}**. "
                f"Healthy ginger leaves typically show a strong green peak. "
                f"A red-shifted or dull histogram may indicate disease or stress."
            )

        # Tab 4: Pixel Health Map
        with tab4:
            # Green pixel ratio gauge
            fig_green = go.Figure(go.Indicator(
                mode="gauge+number",
                value=green_pct,
                title={"text": "Green-Dominant Pixel Ratio", "font": {"size": 13}},
                number={"suffix": " %", "font": {"size": 38,
                        "color": "#4caf50" if green_pct >= 40 else "#ff9800"}},
                gauge={
                    "axis": {"range": [0, 100], "ticksuffix": "%"},
                    "bar":  {"color": "#4caf50" if green_pct >= 40 else "#ff9800", "thickness": 0.28},
                    "bgcolor": "rgba(0,0,0,0)",
                    "borderwidth": 0,
                    "steps": [
                        {"range": [0,  25], "color": "rgba(244,67,54,0.15)"},
                        {"range": [25, 50], "color": "rgba(255,152,0,0.15)"},
                        {"range": [50,100], "color": "rgba(76,175,80,0.15)"},
                    ],
                },
            ))
            fig_green.update_layout(**plotly_base(240, margin=dict(l=20,r=20,t=20,b=10)))

            # Brightness distribution
            brightness = img_array.mean(axis=2).flatten()
            fig_bright = go.Figure(go.Histogram(
                x=brightness, nbinsx=48,
                marker_color="rgba(255,235,59,0.7)",
                name="Brightness",
            ))
            fig_bright.update_layout(
                **plotly_base(240),
                xaxis=dict(title="Avg Pixel Brightness", gridcolor="#333"),
                yaxis=dict(title="Count", gridcolor="#333"),
                showlegend=False,
                title=dict(text="Overall Brightness Distribution", font=dict(size=13)),
            )

            gc1, gc2 = st.columns(2)
            with gc1:
                st.plotly_chart(fig_green, use_container_width=True, config={"staticPlot": True})
            with gc2:
                st.plotly_chart(fig_bright, use_container_width=True, config={"staticPlot": True})

            # Colour region grid (3x3 mean colour heatmap)
            h_px, w_px = 224, 224
            grid_n = 7
            cell_h, cell_w = h_px // grid_n, w_px // grid_n
            z_vals = []
            for row_i in range(grid_n):
                row_z = []
                for col_j in range(grid_n):
                    patch = img_array[
                        row_i * cell_h:(row_i + 1) * cell_h,
                        col_j * cell_w:(col_j + 1) * cell_w,
                    ]
                    pg, pr, pb = patch[:,:,1].mean(), patch[:,:,0].mean(), patch[:,:,2].mean()
                    # Score: positive = green dominant, negative = not green
                    row_z.append(float(pg - max(pr, pb)))
                z_vals.append(row_z)

            fig_heatmap = go.Figure(go.Heatmap(
                z=z_vals,
                colorscale=[[0, "#b71c1c"], [0.4, "#e65100"], [0.6, "#827717"], [1, "#1b5e20"]],
                zmin=-80, zmax=80,
                showscale=True,
                colorbar=dict(title="Green<br>Dominance", thickness=12),
            ))
            fig_heatmap.update_layout(
                **plotly_base(300),
                title=dict(text="Green-Dominance Spatial Heatmap (7×7 grid)", font=dict(size=13)),
                xaxis=dict(visible=False), yaxis=dict(visible=False, autorange="reversed"),
            )
            st.plotly_chart(fig_heatmap, use_container_width=True, config={"staticPlot": True})
            st.caption(
                f"**Green pixel ratio: {green_pct:.1f}%** — pixels where green channel "
                f"dominates red and blue. "
                f"Mean brightness: {mean_bright:.1f}/255. "
                f"The heatmap shows which spatial regions of the leaf are green-dominant (dark green) "
                f"vs yellowing/browning (red). Diseased areas typically appear as red patches."
            )


#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PAGE: Live Detection
#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
elif page == "Live Detection":
    st.markdown('<div class="page-title">Live Camera Detection</div>', unsafe_allow_html=True)
    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)
    render_live_detection_page()


#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PAGE: Pest Monitoring
#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
elif page == "Pest Monitoring":
    st.markdown('<div class="page-title">Pest Infestation Monitoring</div>', unsafe_allow_html=True)
    st.caption("Upload a ginger leaf, stem, or rhizome image — MobileNetV2 pest classification with treatment recommendations")
    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)

    # ── Load the real pest model ─────────────────────────────────────────────────
    pest_model = load_pest_model()
    if pest_model is None:
        st.info(
            "**Pest model not available.** Place `ginger_pest_model.tflite` and "
            "`class_indices.json` in `streamlit_app/models/`. "
            "Using simulated detection as fallback.",
            icon="ℹ️",
        )

    # ── Section 1: Image Upload & Detection ────────────────────────────────────
    st.markdown('<div class="section-label">Upload & Detect</div>', unsafe_allow_html=True)
    col_upload, col_info = st.columns([1, 1])
    with col_upload:
        uploaded = st.file_uploader(
            "Upload leaf / stem / rhizome image (JPG / PNG)",
            type=["jpg", "jpeg", "png"],
            key="pest_uploader",
        )
    with col_info:
        st.markdown(
            f"<div style='padding:8px;font-size:0.85rem;color:#aaa'>"
            f"<b>Sensor Fusion Inputs:</b><br>"
            f"🌡 Temp: {current_data['temperature']:.1f}°C · "
            f"💧 Humidity: {current_data['humidity']:.1f}%<br>"
            f"📅 Days since last spray: {current_data.get('days_since_last_spray', 0):.0f}<br>"
            f"🐛 Pest risk: <b>{get_pest_risk_level(current_data)['level']}</b>"
            f"</div>",
            unsafe_allow_html=True,
        )

    if uploaded is not None:
        pil_img = Image.open(uploaded).convert("RGB")

        col_img, col_result = st.columns([1, 1], gap="large")
        with col_img:
            st.image(pil_img, caption="Uploaded image", use_column_width="always")

        with col_result:
            if st.button("🔍  Run Pest Detection", use_container_width=True, type="primary"):
                with st.spinner("Analyzing image for pest infestation…"):
                    if pest_model is not None:
                        # Use the real TFLite model
                        class_name, confidence, probs = predict_pest(pest_model, pil_img)
                        if class_name is not None:
                            # Look up pest info from PEST_CLASSES
                            pest_info = PEST_CLASSES.get(class_name, {})
                            result = {
                                "pest_key": class_name,
                                "class_name": pest_info.get("class_name", class_name),
                                "causative_agent": pest_info.get("causative_agent"),
                                "visual_symptoms": pest_info.get("visual_symptoms", "No description"),
                                "severity": pest_info.get("severity", "Moderate"),
                                "severity_color": pest_info.get("severity_color", "#ff9800"),
                                "recommended_pesticide": pest_info.get("recommended_pesticide", "Consult local expert"),
                                "alert_message": pest_info.get("alert_message", "Pest detected — take action."),
                                "preventive_action": pest_info.get("preventive_action", "Monitor regularly."),
                                "confidence": round(confidence, 3),
                                "all_probs": probs.tolist() if probs is not None else None,
                            }
                        else:
                            result = None
                    else:
                        # Fallback to simulated detection
                        result = simulate_pest_detection()
                    st.session_state.pest_detection_result = result

            if st.session_state.pest_detection_result:
                r = st.session_state.pest_detection_result
                sev_color = r["severity_color"]

                if r["class_name"] == "Healthy":
                    st.success(f"### 🌿 {r['class_name']}\n**Confidence: {r['confidence']*100:.1f}%**")
                elif r["severity"] == "Critical":
                    st.error(f"### 🐛 {r['class_name']} Detected\n**Confidence: {r['confidence']*100:.1f}%**\n**Severity: Critical**", icon="🚨")
                else:
                    st.warning(f"### 🐛 {r['class_name']} Detected\n**Confidence: {r['confidence']*100:.1f}%**\n**Severity: Moderate**", icon="⚠️")

                st.markdown(
                    f"<div style='margin-top:8px;padding:10px;border-radius:8px;"
                    f"background:{sev_color}10;border:1px solid {sev_color}40;font-size:0.9rem'>"
                    f"<b>Causative Agent:</b> {r['causative_agent'] or 'N/A'}<br>"
                    f"<b>Symptoms:</b> {r['visual_symptoms']}<br>"
                    f"<b>Pesticide:</b> {r['recommended_pesticide']}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # ── Section 2: Analysis Tabs ────────────────────────────────────────────
        if st.session_state.pest_detection_result:
            r = st.session_state.pest_detection_result
            st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)
            st.markdown('<div class="section-label">Pest Analysis — Recommendations</div>', unsafe_allow_html=True)

            t1, t2, t3, t4 = st.tabs([
                "Pest Identification",
                "Treatment Recommendation",
                "Preventive Actions",
                "Sensor Correlation",
            ])

            # Tab 1: Pest Identification
            with t1:
                sev_color = r["severity_color"]
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number+delta",
                    value=r["confidence"] * 100,
                    delta={"reference": 60, "valueformat": ".1f", "suffix": "% vs threshold"},
                    title={"text": f"Detection Confidence · <b>{r['class_name']}</b>", "font": {"size": 14}},
                    number={"suffix": " %", "font": {"size": 42, "color": sev_color}},
                    gauge={
                        "axis": {"range": [0, 100], "ticksuffix": "%", "nticks": 6},
                        "bar":  {"color": sev_color, "thickness": 0.3},
                        "bgcolor": "rgba(0,0,0,0)",
                        "borderwidth": 0,
                        "steps": [
                            {"range": [0,  40], "color": "rgba(244,67,54,0.18)"},
                            {"range": [40, 60], "color": "rgba(255,152,0,0.18)"},
                            {"range": [60, 80], "color": "rgba(139,195,74,0.15)"},
                            {"range": [80,100], "color": "rgba(76,175,80,0.15)"},
                        ],
                        "threshold": {
                            "line": {"color": "rgba(255,255,255,0.67)", "width": 2},
                            "thickness": 0.85, "value": 60,
                        },
                    },
                ))
                fig_gauge.update_layout(**plotly_base(300, margin=dict(l=20,r=20,t=20,b=20)))
                st.plotly_chart(fig_gauge, use_container_width=True, config={"staticPlot": True})

                # Severity badge
                severity_badge = (
                    f'<span class="pill-crit">{r["severity"]}</span>'
                    if r["severity"] == "Critical"
                    else f'<span class="pill-warn">{r["severity"]}</span>'
                    if r["severity"] == "Moderate"
                    else f'<span class="pill-ok">{r["severity"]}</span>'
                )
                st.markdown(
                    f"<div style='font-size:0.9rem'>"
                    f"<b>Pest:</b> {r['class_name']}<br>"
                    f"<b>Agent:</b> {r['causative_agent'] or 'N/A'}<br>"
                    f"<b>Severity:</b> {severity_badge}<br>"
                    f"<b>Symptoms:</b> {r['visual_symptoms']}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            # Tab 2: Treatment Recommendation
            with t2:
                st.markdown(f"### Recommended Pesticide")
                st.info(r["recommended_pesticide"])
                st.markdown("### Alert Message")
                st.warning(r["alert_message"])
                st.markdown("### Application Notes")
                st.markdown(
                    "- Apply during early morning or late evening when beneficial insects are less active.\n"
                    "- Ensure thorough coverage of affected plant parts.\n"
                    "- Rotate pesticides with different modes of action to prevent resistance.\n"
                    "- Follow recommended pre-harvest interval before collecting rhizomes."
                )

            # Tab 3: Preventive Actions
            with t3:
                st.markdown(f"### Preventive Measures")
                st.success(r["preventive_action"])
                st.markdown("### Cultural Practices")
                st.markdown(
                    "- Maintain field hygiene — remove weed hosts and crop debris.\n"
                    "- Practice crop rotation with non-host crops (cereals, legumes).\n"
                    "- Ensure proper spacing for air circulation.\n"
                    "- Avoid overhead irrigation to reduce leaf wetness.\n"
                    "- Use certified disease-free seed rhizomes.\n"
                    "- Install pheromone traps and sticky traps for monitoring."
                )

            # Tab 4: Sensor Correlation
            with t4:
                pest_risk = get_pest_risk_level(current_data)
                risk_color = pest_risk["color"]
                st.markdown(
                    f"<div style='text-align:center;padding:1rem;border-radius:12px;"
                    f"background:{risk_color}15;border:2px solid {risk_color}60;'>"
                    f"<div style='font-size:0.8rem;color:#aaa;text-transform:uppercase'>Current Pest Risk</div>"
                    f"<div style='font-size:2rem;font-weight:900;color:{risk_color}'>{pest_risk['level']}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<div style='margin-top:12px;font-size:0.9rem'>"
                    f"<b>Environmental Conditions:</b><br>"
                    f"• Temperature: {current_data['temperature']:.1f}°C "
                    f"{'⚠️' if 22 <= current_data['temperature'] <= 35 else '✅'}"
                    f" (favorable range: 22–35°C)<br>"
                    f"• Humidity: {current_data['humidity']:.1f}% "
                    f"{'⚠️' if current_data['humidity'] > 70 else '✅'}"
                    f" (high risk: >70%)<br>"
                    f"• Days since last spray: {current_data.get('days_since_last_spray', 0):.0f} "
                    f"{'⚠️' if current_data.get('days_since_last_spray', 0) > 14 else '✅'}"
                    f" (overdue: >14 days)<br>"
                    f"• Pest risk score: {current_data.get('pest_risk_score', 0):.2f} / 1.0"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # ── Section 3: Spray Schedule Control ──────────────────────────────────────
    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Spray Schedule</div>', unsafe_allow_html=True)

    col_s1, col_s2, col_s3 = st.columns([1, 1, 1])
    with col_s1:
        dsls = current_data.get("days_since_last_spray", 0)
        spray_color = "#f44336" if dsls > 14 else ("#ff9800" if dsls > 7 else "#4caf50")
        st.markdown(
            f"<div style='text-align:center;padding:1rem;border-radius:12px;"
            f"background:{spray_color}10;border:1px solid {spray_color}40'>"
            f"<div style='font-size:0.75rem;color:#aaa;text-transform:uppercase'>Days Since Last Spray</div>"
            f"<div style='font-size:2.5rem;font-weight:900;color:{spray_color}'>{dsls:.0f}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_s2:
        st.markdown("<div style='padding-top:12px'>", unsafe_allow_html=True)
        if st.button("🧴  Mark Sprayed Today", use_container_width=True, type="primary"):
            st.session_state.pest_detection_result = None
            st.session_state.spray_history.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "action": "Pesticide spray applied",
                "pest_risk_before": pest_risk['level'],
            })
            _sim.mark_sprayed()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col_s3:
        pest_risk = get_pest_risk_level(current_data)
        st.markdown(
            f"<div style='text-align:center;padding:12px;font-size:0.85rem;color:#aaa'>"
            f"<b>Recommended schedule:</b> spray every 14 days<br>"
            f"<b>Current status:</b> {'⚠️ Overdue' if dsls > 14 else '✅ Within schedule'}"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Spray History ──────────────────────────────────────────────────────────
    if st.session_state.spray_history:
        st.markdown('<div style="margin-top:12px"></div>', unsafe_allow_html=True)
        st.markdown("**Spray History**")
        st.dataframe(
            pd.DataFrame(st.session_state.spray_history[-20:]),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"{len(st.session_state.spray_history)} spray event(s) recorded")

    # ── Pest reference table ───────────────────────────────────────────────────
    with st.expander("📖 Pest Identification Reference"):
        pest_ref_data = []
        for pk in PEST_KEYS:
            p = PEST_CLASSES[pk]
            pest_ref_data.append({
                "Pest": p["class_name"],
                "Agent": p["causative_agent"] or "—",
                "Severity": p["severity"],
                "Symptoms": p["visual_symptoms"],
                "Pesticide": p["recommended_pesticide"],
            })
        st.dataframe(pd.DataFrame(pest_ref_data), use_container_width=True, hide_index=True)


#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PAGE: Irrigation Control
#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
elif page == "Irrigation Control":
    st.markdown('<div class="page-title">Irrigation Control</div>', unsafe_allow_html=True)
    st.caption("Soil moisture classification, relay control, and irrigation scheduling")
    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)

    m_class = get_moisture_class(current_data["soil_moisture"])
    irr_decision = get_irrigation_decision(m_class["class_name"])

    # ── Top: Moisture status + decision ────────────────────────────────────────
    mc1, mc2 = st.columns([1, 1])
    with mc1:
        led_color = m_class["led_color"]
        st.markdown(
            f"<div style='text-align:center;padding:1.5rem;border-radius:16px;"
            f"background:{led_color}15;border:2px solid {led_color}60;'>"
            f"<span style='display:inline-block;width:24px;height:24px;border-radius:50%;"
            f"background:{led_color};box-shadow:0 0 12px {led_color}80;'></span>"
            f"<div style='font-size:2rem;font-weight:900;margin:8px 0;color:{led_color}'>{m_class['class_name']}</div>"
            f"<div style='color:#aaa'>Soil Moisture: {current_data['soil_moisture']:.1f}% · "
            f"Range: {m_class['range_label']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with mc2:
        with st.container(border=True):
            st.markdown("**📋 Irrigation Decision**")
            st.markdown(f"<div style='padding:8px;border-radius:8px;background:#ffffff08;font-size:0.95rem'>{irr_decision['message']}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='margin-top:8px;color:#aaa;font-size:0.85rem'>"
                        f"Action: <b>{irr_decision['action']}</b> · "
                        f"Relay: <b>{irr_decision['relay']}</b> · "
                        f"Next irrigation: <b>{'Now' if irr_decision['next_irrigation_min'] == 0 else f'{irr_decision['next_irrigation_min']} min' if irr_decision['next_irrigation_min'] else 'N/A'}</b>"
                        f"</div>", unsafe_allow_html=True)

    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)

    # ── Relay Control ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Relay Control</div>', unsafe_allow_html=True)
    rc1, rc2, rc3 = st.columns([1, 1, 1])
    with rc1:
        relay_status = "🟢 ON" if st.session_state.irrigation_relay_on else "🔴 OFF"
        st.markdown(f"<div style='text-align:center;font-size:1.2rem'><b>Relay: {relay_status}</b></div>", unsafe_allow_html=True)
    with rc2:
        if not st.session_state.irrigation_relay_on:
            if st.button("💧  Turn Relay ON", use_container_width=True, type="primary"):
                st.session_state.irrigation_relay_on = True
                st.session_state.irrigation_history.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "action": "Relay ON",
                    "moisture": f"{current_data['soil_moisture']:.1f}%",
                })
                _sim.mark_irrigated()
                st.rerun()
        else:
            if st.button("⏹  Turn Relay OFF", use_container_width=True, type="secondary"):
                st.session_state.irrigation_relay_on = False
                st.session_state.irrigation_history.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "action": "Relay OFF",
                    "moisture": f"{current_data['soil_moisture']:.1f}%",
                })
                st.rerun()
    with rc3:
        st.markdown(f"<div style='text-align:center;color:#aaa;font-size:0.85rem;padding-top:8px'>"
                    f"Days since irrigation: <b>{current_data['days_since_irrigation']:.0f}</b></div>",
                    unsafe_allow_html=True)

    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)

    # ── NPK Deficiency Summary ─────────────────────────────────────────────────
    st.markdown('<div class="section-label">NPK & pH Deficiency Status</div>', unsafe_allow_html=True)
    npk_alerts = get_npk_alerts(current_data)
    if npk_alerts:
        for a in npk_alerts:
            if a["type"] == "error":
                st.error(a["message"], icon="🚨")
            else:
                st.warning(a["message"], icon="⚠️")
    else:
        st.success("All NPK levels and pH within optimal range.")

    # ── NPK side-by-side ───────────────────────────────────────────────────────
    n_val = current_data["nitrogen"]
    p_val = current_data["phosphorus"]
    k_val = current_data["potassium"]
    cn1, cn2, cn3 = st.columns(3)
    with cn1:
        n_color = _sensor_color("nitrogen", n_val)
        st.markdown(f"<div style='text-align:center;padding:12px;border-radius:12px;background:{n_color}10;border:1px solid {n_color}40'>"
                    f"<div style='font-size:1.1rem;font-weight:700;color:{n_color}'>N: {n_val:.0f} ppm</div>"
                    f"<div style='color:#aaa;font-size:0.8rem'>Optimal: 80–150</div></div>",
                    unsafe_allow_html=True)
    with cn2:
        p_color = _sensor_color("phosphorus", p_val)
        st.markdown(f"<div style='text-align:center;padding:12px;border-radius:12px;background:{p_color}10;border:1px solid {p_color}40'>"
                    f"<div style='font-size:1.1rem;font-weight:700;color:{p_color}'>P: {p_val:.0f} ppm</div>"
                    f"<div style='color:#aaa;font-size:0.8rem'>Optimal: 20–40</div></div>",
                    unsafe_allow_html=True)
    with cn3:
        k_color = _sensor_color("potassium", k_val)
        st.markdown(f"<div style='text-align:center;padding:12px;border-radius:12px;background:{k_color}10;border:1px solid {k_color}40'>"
                    f"<div style='font-size:1.1rem;font-weight:700;color:{k_color}'>K: {k_val:.0f} ppm</div>"
                    f"<div style='color:#aaa;font-size:0.8rem'>Optimal: 100–200</div></div>",
                    unsafe_allow_html=True)

    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)

    # ── Irrigation History ─────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Irrigation History</div>', unsafe_allow_html=True)
    if st.session_state.irrigation_history:
        st.dataframe(
            pd.DataFrame(st.session_state.irrigation_history[-50:]),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"{len(st.session_state.irrigation_history)} event(s) recorded")
    else:
        st.info("No irrigation events recorded this session.")

    # ── Moisture classification reference ──────────────────────────────────────
    with st.expander("📖 Moisture Classification Reference"):
        st.dataframe(
            pd.DataFrame([
                {"Level": "Critically Dry",    "Range": "< 25%",      "Severity": "Critical", "Action": "Irrigate immediately — 45 min drip"},
                {"Level": "Moisture Deficit",  "Range": "25 – 40%",   "Severity": "Warning",  "Action": "Schedule irrigation within 6 hours"},
                {"Level": "Optimal",           "Range": "40 – 70%",   "Severity": "Normal",   "Action": "No irrigation needed"},
                {"Level": "Surplus Moisture",  "Range": "70 – 85%",   "Severity": "Warning",  "Action": "Suspend irrigation, open drainage"},
                {"Level": "Waterlogged",       "Range": "> 85%",      "Severity": "Critical", "Action": "Immediate drainage required"},
            ]),
            use_container_width=True,
            hide_index=True,
        )
#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PAGE: Yield Estimation
#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
elif page == "Yield Estimation":
    st.markdown('<div class="page-title">Yield Estimation</div>', unsafe_allow_html=True)
    st.caption("Predict ginger harvest yield from sensor data — rule-based heuristic model (RandomForest-ready)")
    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)

    # ── Increment days_since_planting on each read ──────────────────────────────
    st.session_state.days_since_planting += 1.0 / 60.0
    if st.session_state.days_since_planting > 270:
        st.session_state.days_since_planting = 270.0

    current_data["days_since_planting"] = st.session_state.days_since_planting
    current_data["planting_density"] = st.session_state.planting_density
    current_data["variety"] = st.session_state.variety
    current_data["mulching_applied"] = st.session_state.mulching_applied

    # ── Section 1: Season Inputs ────────────────────────────────────────────────
    st.markdown('<div class="section-label">Season Configuration</div>', unsafe_allow_html=True)
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)

    with col_s1:
        st.session_state.planting_density = st.number_input(
            "Planting density (rhizomes/m²)",
            min_value=6, max_value=20, value=st.session_state.planting_density,
            step=1, help="Typical ginger: 10–15 rhizomes/m²",
        )
    with col_s2:
        st.session_state.variety = st.selectbox(
            "Variety / Cultivar",
            ["Local", "Rio-de-Janeiro", "Varada", "Maran", "Himagiri", "Suprabha"],
            index=["Local", "Rio-de-Janeiro", "Varada", "Maran", "Himagiri", "Suprabha"].index(st.session_state.variety)
            if st.session_state.variety in ["Local", "Rio-de-Janeiro", "Varada", "Maran", "Himagiri", "Suprabha"]
            else 0,
        )
    with col_s3:
        st.session_state.mulching_applied = st.checkbox(
            "Mulching applied", value=st.session_state.mulching_applied,
            help="Organic mulch (straw / leaves) retains moisture and suppresses weeds",
        )
    with col_s4:
        planting_days = st.number_input(
            "Days since planting",
            min_value=30, max_value=270, value=int(st.session_state.days_since_planting),
            step=5, help="Approximate days since ginger rhizomes were planted",
        )
        st.session_state.days_since_planting = float(planting_days)

    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)

    # ── Section 2: Yield Prediction ────────────────────────────────────────────
    st.markdown('<div class="section-label">Yield Forecast</div>', unsafe_allow_html=True)

    col_run, col_info = st.columns([1, 2])
    with col_run:
        if st.button("📊  Run Yield Forecast", use_container_width=True, type="primary"):
            with st.spinner("Computing yield estimate from sensor data…"):
                result = simulate_yield_prediction(current_data)
                st.session_state.yield_prediction = result
                st.session_state.yield_history.append({
                    **result,
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "days_since_planting": st.session_state.days_since_planting,
                })
                if len(st.session_state.yield_history) > 100:
                    st.session_state.yield_history = st.session_state.yield_history[-100:]

    with col_info:
        if st.session_state.yield_prediction:
            r = st.session_state.yield_prediction
            band = r["band_info"]
            st.markdown(
                f"<div style='padding:6px 0;font-size:0.85rem;color:#aaa'>"
                f"Baseline: <b>{r['baseline']} q/ha</b> (district avg) · "
                f"Your forecast: <b>{r['yield_qha']} q/ha</b> "
                f"({r['vs_baseline']:+.1f}% vs baseline) · "
                f"CI: {r['confidence_interval'][0]}–{r['confidence_interval'][1]} q/ha"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)

    # ── Results display ─────────────────────────────────────────────────────────
    if st.session_state.yield_prediction:
        r = st.session_state.yield_prediction
        band = r["band_info"]

        # Top row: yield gauge + band card
        col_gauge, col_band = st.columns([1, 1], gap="large")

        with col_gauge:
            fig_yield = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=r["yield_qha"],
                delta={
                    "reference": r["baseline"],
                    "valueformat": ".1f",
                    "suffix": " q/ha vs baseline",
                    "position": "bottom",
                },
                title={
                    "text": f"Predicted Yield · <b>{band['label']}</b>",
                    "font": {"size": 14},
                },
                number={
                    "suffix": " q/ha",
                    "font": {"size": 44, "color": band["color"]},
                },
                gauge={
                    "axis": {
                        "range": [0, 250],
                        "ticksuffix": " q/ha",
                        "nticks": 6,
                        "tickwidth": 1,
                        "tickcolor": "#666",
                    },
                    "bar": {"color": band["color"], "thickness": 0.3},
                    "bgcolor": "rgba(0,0,0,0)",
                    "borderwidth": 0,
                    "steps": [
                        {"range": [0,   100], "color": "rgba(244,67,54,0.15)"},
                        {"range": [100, 150], "color": "rgba(255,152,0,0.15)"},
                        {"range": [150, 200], "color": "rgba(76,175,80,0.15)"},
                        {"range": [200, 250], "color": "rgba(27,94,32,0.15)"},
                    ],
                    "threshold": {
                        "line": {"color": "rgba(255,255,255,0.5)", "width": 2},
                        "thickness": 0.85,
                        "value": r["baseline"],
                    },
                },
            ))
            fig_yield.update_layout(**plotly_base(300, margin=dict(l=20,r=20,t=20,b=20)))
            st.plotly_chart(fig_yield, use_container_width=True, config={"staticPlot": True})
            st.caption(
                f"Baseline (district avg): <b>{r['baseline']} q/ha</b>. "
                f"White line marks the baseline. "
                f"Confidence interval: {r['confidence_interval'][0]}–{r['confidence_interval'][1]} q/ha.",
                unsafe_allow_html=True,
            )

        with col_band:
            # Band card with interpretation
            st.markdown(
                f"<div style='border:1px solid {band['color']}40;border-radius:12px;"
                f"padding:1.2rem 1.5rem;background:{band['color']}08;height:100%;'>"
                f"<div style='font-size:1.6rem;font-weight:900;color:{band['color']};'>{band['label']}</div>"
                f"<div style='font-size:0.85rem;color:#aaa;margin:0.3rem 0 0.8rem 0;'>{band['interpretation']}</div>"
                f"<div style='font-size:0.9rem;color:#ddd;line-height:1.6;'>{band['farmer_action']}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

            # Market readiness indicator
            readiness = r["market_readiness"]
            if readiness == "Ready":
                r_color = "#4caf50"
                r_icon = "✅"
            elif readiness == "Prepare":
                r_color = "#ff9800"
                r_icon = "🔄"
            else:
                r_color = "#666"
                r_icon = "⏳"

            st.markdown(
                f"<div style='margin-top:0.8rem;padding:0.6rem 1rem;border-radius:8px;"
                f"border:1px solid {r_color}40;background:{r_color}08;'>"
                f"<span style='font-size:0.75rem;text-transform:uppercase;color:#888;'>Market Readiness</span><br>"
                f"<span style='font-size:1.1rem;font-weight:700;color:{r_color};'>{r_icon} {readiness}</span>"
                f"<span style='font-size:0.85rem;color:#aaa;margin-left:0.8rem;'>"
                f"Harvest in ~{r['harvest_window']} days</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # ── Section 3: Limiting Factor Analysis ─────────────────────────────────
        st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Yield-Limiting Factors</div>', unsafe_allow_html=True)

        if r["limiting_factors"]:
            cols = st.columns(len(r["limiting_factors"]))
            for i, factor in enumerate(r["limiting_factors"]):
                with cols[i]:
                    st.markdown(
                        f"<div style='border:1px solid #f4433640;border-radius:10px;"
                        f"padding:0.8rem 1rem;background:#f4433608;height:100%;'>"
                        f"<span style='font-size:0.9rem;color:#ef9a9a;'>⚠️ {factor}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
        else:
            st.success("No significant yield-limiting factors detected. All parameters are in optimal range.")

        # ── Section 4: Multiplier Breakdown ─────────────────────────────────────
        st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Factor Contribution Breakdown</div>', unsafe_allow_html=True)

        mults = r["multipliers"]
        # Remove 'combined' from the list
        factor_keys = [k for k in mults if k != "combined"]
        factor_labels = {
            "soil_moisture": "Soil Moisture",
            "soil_temperature": "Soil Temperature",
            "soil_ph": "Soil pH",
            "npk": "NPK Adequacy",
            "pest_risk": "Pest Risk",
            "irrigation": "Irrigation Timeliness",
            "spray": "Spray Coverage",
        }

        # Build a horizontal bar chart of multipliers
        factor_names = [factor_labels.get(k, k) for k in factor_keys]
        factor_vals = [mults[k] * 100 for k in factor_keys]  # convert to %
        factor_colors = ["#4caf50" if v >= 90 else "#ff9800" if v >= 75 else "#f44336" for v in factor_vals]

        fig_factors = go.Figure()
        fig_factors.add_trace(go.Bar(
            x=factor_vals,
            y=factor_names,
            orientation="h",
            marker=dict(color=factor_colors, line=dict(color=factor_colors, width=1.5)),
            text=[f"{v:.0f}%" for v in factor_vals],
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(size=12, color="white"),
        ))
        fig_factors.update_layout(
            **plotly_base(260),
            xaxis=dict(title="Multiplier Effect on Yield (%)", range=[0, 110], gridcolor="#333"),
            yaxis=dict(title=""),
            showlegend=False,
            bargap=0.3,
            title=dict(
                text=f"Combined multiplier: <b>{mults['combined']*100:.1f}%</b> of baseline yield",
                font=dict(size=13),
            ),
        )
        st.plotly_chart(fig_factors, use_container_width=True, config={"staticPlot": True})
        st.caption(
            "Each factor shows how much of the baseline yield it contributes. "
            "100% = optimal, < 75% = significant penalty. "
            "The combined multiplier is the product of all seven factors."
        )

        # ── Section 5: Sensor Correlation ───────────────────────────────────────
        st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Sensor Correlation</div>', unsafe_allow_html=True)

        corr_data = {
            "Parameter": ["Soil Moisture", "Soil Temp", "Soil pH", "Nitrogen", "Phosphorus", "Potassium",
                          "Days Since Irrigation", "Days Since Spray", "Pest Risk", "Days Since Planting"],
            "Current Value": [
                f"{current_data.get('soil_moisture', 55):.1f} %",
                f"{current_data.get('soil_temperature', 25):.1f} °C",
                f"{current_data.get('soil_ph', 6.2):.2f}",
                f"{current_data.get('nitrogen', 120):.0f} ppm",
                f"{current_data.get('phosphorus', 30):.0f} ppm",
                f"{current_data.get('potassium', 150):.0f} ppm",
                f"{current_data.get('days_since_irrigation', 0):.0f} d",
                f"{current_data.get('days_since_last_spray', 0):.0f} d",
                f"{current_data.get('pest_risk_score', 0):.2f}",
                f"{st.session_state.days_since_planting:.0f} d",
            ],
            "Status": [],
            "Impact on Yield": [],
        }

        # Determine status for each parameter
        moist = current_data.get("soil_moisture", 55)
        corr_data["Status"].append("✅ Optimal" if 40 <= moist <= 70 else "⚠️ Suboptimal")

        st_temp = current_data.get("soil_temperature", 25)
        corr_data["Status"].append("✅ Optimal" if 20 <= st_temp <= 30 else "⚠️ Suboptimal")

        ph = current_data.get("soil_ph", 6.2)
        corr_data["Status"].append("✅ Optimal" if 5.5 <= ph <= 7.0 else "⚠️ Suboptimal")

        n = current_data.get("nitrogen", 120)
        corr_data["Status"].append("✅ OK" if n >= 80 else "⚠️ Low")

        p = current_data.get("phosphorus", 30)
        corr_data["Status"].append("✅ OK" if p >= 20 else "⚠️ Low")

        k = current_data.get("potassium", 150)
        corr_data["Status"].append("✅ OK" if k >= 100 else "⚠️ Low")

        dsi = current_data.get("days_since_irrigation", 0)
        corr_data["Status"].append("✅ OK" if dsi <= 7 else "⚠️ Overdue")

        dsls = current_data.get("days_since_last_spray", 0)
        corr_data["Status"].append("✅ OK" if dsls <= 14 else "⚠️ Overdue")

        pr = current_data.get("pest_risk_score", 0)
        corr_data["Status"].append("✅ Low" if pr < 0.3 else "⚠️ Elevated")

        corr_data["Status"].append(f"{st.session_state.days_since_planting:.0f} / 270 d")

        # Impact on yield
        impacts = []
        for mult_key, mult_val in [
            ("soil_moisture", mults["soil_moisture"]),
            ("soil_temperature", mults["soil_temperature"]),
            ("soil_ph", mults["soil_ph"]),
            ("npk", mults["npk"]),
            ("npk", mults["npk"]),
            ("npk", mults["npk"]),
            ("irrigation", mults["irrigation"]),
            ("spray", mults["spray"]),
            ("pest_risk", mults["pest_risk"]),
            (None, 1.0),
        ]:
            if mult_val >= 0.95:
                impacts.append("🟢 Positive")
            elif mult_val >= 0.80:
                impacts.append("🟡 Neutral")
            else:
                impacts.append("🔴 Negative")

        corr_data["Impact on Yield"] = impacts

        st.dataframe(
            pd.DataFrame(corr_data),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Parameter": st.column_config.TextColumn("Parameter", width="medium"),
                "Current Value": st.column_config.TextColumn("Current Value", width="small"),
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Impact on Yield": st.column_config.TextColumn("Impact on Yield", width="small"),
            },
        )

        # ── Section 6: Yield History ────────────────────────────────────────────
        if st.session_state.yield_history:
            st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)
            st.markdown('<div class="section-label">Yield Forecast History</div>', unsafe_allow_html=True)

            hist_df = pd.DataFrame(st.session_state.yield_history[-20:])
            if not hist_df.empty and "yield_qha" in hist_df.columns:
                fig_history = go.Figure()
                fig_history.add_trace(go.Scatter(
                    x=hist_df["timestamp"],
                    y=hist_df["yield_qha"],
                    mode="lines+markers",
                    name="Predicted Yield",
                    line=dict(color="#4caf50", width=2),
                    marker=dict(color="#4caf50", size=6),
                ))
                # Add baseline reference line
                fig_history.add_hline(
                    y=r["baseline"],
                    line_dash="dash",
                    line_color="#888",
                    annotation_text=f"Baseline: {r['baseline']} q/ha",
                    annotation_font=dict(color="#888", size=11),
                )
                fig_history.update_layout(
                    **plotly_base(240),
                    xaxis=dict(title="Time", gridcolor="#333"),
                    yaxis=dict(title="Yield (q/ha)", gridcolor="#333", range=[0, 250]),
                    showlegend=False,
                    title=dict(text="Yield Forecast Trend", font=dict(size=13)),
                )
                st.plotly_chart(fig_history, use_container_width=True, config={"staticPlot": True})
                st.caption("Yield forecast updates over time. Each forecast run uses current sensor data.")

    else:
        # No prediction yet
        st.info(
            "Configure your season parameters above, then click **Run Yield Forecast** "
            "to estimate your expected ginger harvest yield.",
            icon="📊",
        )

        # Show yield band reference table
        st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Yield Band Reference</div>', unsafe_allow_html=True)
        ref_rows = []
        for band_key in YIELD_BAND_KEYS:
            b = YIELD_BANDS[band_key]
            lo, hi = b["range"]
            range_str = f"{lo}–{hi} q/ha" if hi < 999 else f"> {lo} q/ha"
            ref_rows.append({
                "Band": b["label"],
                "Range": range_str,
                "Interpretation": b["interpretation"],
                "Farmer Action": b["farmer_action"][:80] + "…",
            })
        st.dataframe(
            pd.DataFrame(ref_rows),
            use_container_width=True,
            hide_index=True,
        )

        # Formula explanation
        with st.expander("📐 How the yield estimate is calculated"):
            st.markdown("""
The yield estimate uses a **rule-based heuristic model** that evaluates seven factors:

| Factor | Weight | Conditions |
|--------|--------|------------|
| Soil moisture | ±20% | Optimal 40–70% |
| Soil temperature | ±15% | Optimal 20–30°C |
| Soil pH | ±10% | Optimal 5.5–7.0 |
| NPK adequacy | ±20% | N ≥ 80, P ≥ 20, K ≥ 100 ppm |
| Pest risk | −15% max | pest_risk_score × 0.15 penalty |
| Days since irrigation | −10% max | Penalty starts after 7 days |
| Days since spray | −10% max | Penalty starts after 14 days |

**Formula:** `Yield = 125 q/ha × product(all 7 multipliers) × random jitter (±5%)`

The baseline of **125 q/ha** is the historical district average for ginger.

> When real farm records become available (> 40 records), replace this heuristic
> with a **Random Forest Regressor (50 trees, depth 8)** for higher accuracy.
""")

#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
elif page == "Sensor Data":
    st.markdown('<div class="page-title">Sensor History</div>', unsafe_allow_html=True)
    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)

    history = st.session_state.history
    if len(history) < 3:
        st.info("Gathering data… enable auto-refresh on the Dashboard or navigate between pages.")
    else:
        df = pd.DataFrame(history)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")

        palette = ["#4caf50","#2196f3","#ff9800","#e91e63","#ffeb3b"]
        for i, sensor in enumerate(SENSORS):
            color = _sensor_color(sensor["key"], current_data[sensor["key"]])
            fig = go.Figure(go.Scatter(
                x=df.index, y=df[sensor["key"]],
                mode="lines",
                line=dict(color=color, width=2, shape="spline"),
                fill="tozeroy",
                fillcolor=_hex_to_rgba(color, 0.082),
                name=sensor["label"],
            ))
            fig.update_layout(
                **plotly_base(180),
                title=dict(text=f"{sensor['icon']} {sensor['label']} ({sensor['unit']})", font=dict(size=13)),
                xaxis=dict(gridcolor="#2a2a2a", showgrid=True),
                yaxis=dict(gridcolor="#2a2a2a", showgrid=True),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True, config={"staticPlot": False})

        st.caption(f"{len(history)} readings stored · max 200 per session")


#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PAGE: Alerts
#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
elif page == "Alerts":
    st.markdown('<div class="page-title">Alerts & Recommendations</div>', unsafe_allow_html=True)
    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)

    if not alerts:
        st.success("No active alerts — all sensor readings are within optimal range.")
    else:
        for a in alerts:
            if a["type"] == "error":
                st.error(a["message"], icon="🚨")
            else:
                st.warning(a["message"], icon="⚠️")

    # ── Pest alerts section ────────────────────────────────────────────────────
    pest_alerts = get_pest_alerts(current_data)
    if pest_alerts:
        st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-label">🐛 Pest Risk Alerts</div>', unsafe_allow_html=True)
        for a in pest_alerts:
            if a["type"] == "error":
                st.error(a["message"], icon="🐛")
            else:
                st.warning(a["message"], icon="🐛")

    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)
    st.markdown("**Optimal Ranges — Ginger Cultivation**")
    st.dataframe(
        pd.DataFrame([
            {"Parameter": "Ambient Temperature",   "Optimal": "20 – 32 °C",      "Warning": "32 – 38 °C",              "Critical": "< 15 °C  or  > 38 °C"},
            {"Parameter": "Humidity",              "Optimal": "40 – 75 %",       "Warning": "75 – 85 %",                "Critical": "< 30 %  or  > 85 %"},
            {"Parameter": "Soil Moisture",         "Optimal": "40 – 70 %",       "Warning": "25–40% or 70–85%",         "Critical": "< 25% or > 85%"},
            {"Parameter": "Soil pH",               "Optimal": "5.5 – 7.0",       "Warning": "4.5–5.5 or 7–8",           "Critical": "< 4.5  or  > 8.0"},
            {"Parameter": "Light Intensity",       "Optimal": "100 – 800 lx",    "Warning": "50 – 100 lx",              "Critical": "< 50 lx"},
            {"Parameter": "Soil Temperature",      "Optimal": "20 – 30 °C",      "Warning": "30 – 35 °C  or 15–20°C",  "Critical": "< 15 °C  or  > 35 °C"},
            {"Parameter": "EC (Electrical Cond.)", "Optimal": "0.5 – 1.5 mS/cm", "Warning": "1.5–2.5 mS/cm",          "Critical": "< 0.1  or  > 3.0 mS/cm"},
            {"Parameter": "Nitrogen (N)",           "Optimal": "80 – 150 ppm",   "Warning": "60 – 80 ppm",              "Critical": "< 60 ppm"},
            {"Parameter": "Phosphorus (P)",         "Optimal": "20 – 40 ppm",    "Warning": "15 – 20 ppm",              "Critical": "< 15 ppm"},
            {"Parameter": "Potassium (K)",          "Optimal": "100 – 200 ppm",  "Warning": "80 – 100 ppm",             "Critical": "< 80 ppm"},
            {"Parameter": "Rainfall",               "Optimal": "< 50 mm/day",    "Warning": "50 – 100 mm/day",          "Critical": "> 100 mm/day"},
        ]),
        use_container_width=True,
        hide_index=True,
    )


#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PAGE: User Guide
#═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
elif page == "User Guide":
    st.markdown('<div class="page-title">User Guide</div>', unsafe_allow_html=True)
    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)

    st.markdown("""
## Overview
The **Ginger Crop Health Monitor** is a real-time IoT + AI dashboard for monitoring ginger farm
conditions and detecting leaf disease using computer vision.

---

## Dashboard
- Displays a **Farm Health Score (0–100)** computed from all five sensor readings.
- Each sensor card shows the **current value**, **delta from previous read**, and a **live sparkline**.
- The normalised overlay chart lets you spot correlated spikes across sensors.
- In **Historical Data** mode, use **Auto-refresh (every 5 s)** or **Refresh Now** manually.
- In **Bluetooth** mode, the dashboard auto-refreshes every 2 s from live ESP32 hardware data.

| Sensor | Optimal Range | Icon |
|---|---|---|
| Temperature | 20 – 32 °C | 🌡 |
| Humidity | 40 – 75 % | 💧 |
| Soil Moisture | 30 – 70 % | 🌱 |
| Soil pH | 5.5 – 7.0 | ⚗ |
| Light Intensity | 100 – 800 lux | ☀ |

---

## Leaf Detection
1. Click **Browse files** and upload a JPG/PNG photo of a ginger leaf.
2. The AI model (MobileNetV2 TFLite) classifies it as **Healthy** or **Bacterial Wilt**.
3. Four reasoning graphs are shown below the prediction:

| Tab | What it shows |
|---|---|
| **Confidence Gauge** | How certain the model is (arc gauge, threshold at 60%) |
| **Class Probabilities** | P(Bacterial Wilt) vs P(Healthy) as horizontal bars |
| **RGB Channel Analysis** | Pixel intensity histogram for Red, Green, Blue channels |
| **Pixel Health Map** | Green-dominance gauge, brightness distribution, 7×7 spatial heatmap |

> **Low Confidence warning** appears when model confidence is between 40–60%.
> Retake the photo closer to the leaf, in good natural light, against a plain background.

---

## Live Detection
Opens your webcam via WebRTC. The AI label overlays the video and updates every ~12 frames (~0.5 s at 24 fps).
Requires **Chrome** or **Edge**. Click **Start** to begin streaming.

---

## Sensor Data
- Full-history line charts for all five sensors (up to 200 readings per session).
- Charts are interactive — hover to read exact values, drag to zoom.

---

## Yield Estimation
1. Set your **season parameters**: planting density, variety, mulching, days since planting.
2. Click **Run Yield Forecast** to estimate harvest yield (q/ha).
3. View the **yield band** (Low / Average / Good / High) with farmer action text.
4. The **yield gauge** shows your forecast vs baseline (125 q/ha district average).
5. **Limiting factors** identify what's dragging yield down.
6. The **factor breakdown** shows each sensor's contribution as a multiplier.
7. **Yield history** chart tracks how your forecast changes over time.

---

## Alerts
- Lists all active threshold violations with severity (Critical / Warning).
- Reference table shows optimal, warning, and critical ranges for all parameters.

---

## Model Setup (required for AI features)
1. Upload your dataset to **Google Drive** at `My Drive/Datasets/ginger_plant_dataset/train/`.
2. Open `ginger_cnn_training.ipynb` in **Google Colab** (GPU runtime → T4).
3. Run Phases 1–8 to train. Then run **Phase 9** to convert and download `ginger_disease_model.tflite`.
4. Place the `.tflite` file inside `streamlit_app/models/`.
5. Restart the Streamlit app — the model loads automatically.

---

## Running the App
```bash
streamlit run streamlit_app/app.py
```
""")
