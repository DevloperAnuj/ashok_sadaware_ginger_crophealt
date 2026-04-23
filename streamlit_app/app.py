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
from prediction import predict
from utils import THRESHOLDS, get_alerts

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
    {"key": "temperature",    "label": "Temperature",    "unit": "°C",   "icon": "🌡"},
    {"key": "humidity",       "label": "Humidity",       "unit": "%",    "icon": "💧"},
    {"key": "soil_moisture",  "label": "Soil Moisture",  "unit": "%",    "icon": "🌱"},
    {"key": "soil_ph",        "label": "Soil pH",        "unit": "",     "icon": "⚗"},
    {"key": "light_intensity","label": "Light",          "unit": "lux",  "icon": "☀"},
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

# ── Sensor tick — runs on every rerun regardless of page ─────────────────────
_bt: BluetoothReader = st.session_state.bt_reader
_sim: SensorSimulator = st.session_state.simulator

if st.session_state.data_source == "Bluetooth":
    if _bt.connected:
        _bt_data = _bt.get_latest()
        if _bt_data:
            # Hardware has no light sensor — keep light from last known or simulator
            _light = (st.session_state.current_data or {}).get("light_intensity") or _sim.read()["light_intensity"]
            current_data = {**_bt_data, "light_intensity": _light}
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
    ["Dashboard", "Leaf Detection", "Live Detection", "Sensor Data", "Alerts", "User Guide"],
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
        if _latest_bt:
            st.sidebar.caption(
                f"T: {_latest_bt['temperature']}°C  "
                f"H: {_latest_bt['humidity']}%  "
                f"M: {_latest_bt['soil_moisture']}%  "
                f"pH: {_latest_bt['soil_ph']}"
            )
        else:
            st.sidebar.caption("Waiting for first packet…")

        # Live serial log
        _log_lines = _bt.get_log()
        if _log_lines:
            with st.sidebar.expander("Serial Log", expanded=False):
                st.code("\n".join(_log_lines[-30:]), language=None)
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


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def compute_health_score(data: dict) -> int:
    score = 100
    t = data["temperature"]
    if t >= THRESHOLDS["temperature"]["critical_high"] or t <= THRESHOLDS["temperature"]["critical_low"]:
        score -= 28
    elif t >= THRESHOLDS["temperature"]["warning_high"] or t <= THRESHOLDS["temperature"]["warning_low"]:
        score -= 12

    h = data["humidity"]
    if h >= THRESHOLDS["humidity"]["critical_high"] or h <= THRESHOLDS["humidity"]["critical_low"]:
        score -= 22
    elif h >= THRESHOLDS["humidity"]["warning_high"]:
        score -= 10

    m = data["soil_moisture"]
    if m >= THRESHOLDS["soil_moisture"]["critical_high"] or m <= THRESHOLDS["soil_moisture"]["critical_low"]:
        score -= 20
    elif m <= THRESHOLDS["soil_moisture"]["warning_low"]:
        score -= 8

    ph = data["soil_ph"]
    if ph <= THRESHOLDS["soil_ph"]["critical_low"] or ph >= THRESHOLDS["soil_ph"]["critical_high"]:
        score -= 18
    elif ph < THRESHOLDS["soil_ph"]["optimal_low"] or ph > THRESHOLDS["soil_ph"]["optimal_high"]:
        score -= 8

    lx = data["light_intensity"]
    if lx <= THRESHOLDS["light_intensity"]["critical_low"]:
        score -= 12
    elif lx <= THRESHOLDS["light_intensity"]["warning_low"]:
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
        if value >= t["critical_high"] or value <= t["critical_low"]: return "#f44336"
        if value <= t["warning_low"]:                                  return "#ff9800"
    elif key == "soil_ph":
        if value <= t["critical_low"]  or value >= t["critical_high"]: return "#f44336"
        if value < t["optimal_low"]    or value > t["optimal_high"]:   return "#ff9800"
    elif key == "light_intensity":
        if value <= t["critical_low"]: return "#f44336"
        if value <= t["warning_low"]:  return "#ff9800"
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


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Dashboard
# ═════════════════════════════════════════════════════════════════════════════
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
        st.plotly_chart(gauge_fig, width="stretch", config={"staticPlot": True})
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

    # ── Sensor Cards (3 + 2 layout) ───────────────────────────────────────────
    st.markdown('<div class="section-label">Live Sensor Readings</div>', unsafe_allow_html=True)

    recent_vals = {s["key"]: [h[s["key"]] for h in history[-40:]] for s in SENSORS}

    row1 = st.columns(3)
    row2 = st.columns(3)
    grid = row1 + row2[:2] + [row2[2]]  # 5 sensors + empty last slot

    for i, sensor in enumerate(SENSORS):
        key   = sensor["key"]
        val   = current_data[key]
        delta = val - prev[key]
        color = _sensor_color(key, val)
        spark_vals = recent_vals[key]

        col = (row1 + row2)[i]
        with col:
            with st.container(border=True):
                st.metric(
                    label=f"{sensor['icon']}  {sensor['label']}",
                    value=f"{val:.1f} {sensor['unit']}".strip(),
                    delta=f"{delta:+.2f}" if key != "soil_ph" else f"{delta:+.3f}",
                    delta_color="normal",
                )
                if len(spark_vals) > 2:
                    st.plotly_chart(
                        make_sparkline(spark_vals, color),
                        width="stretch",
                        config={"staticPlot": True},
                    )

    # Last column of row2 — mini sensor trend overview
    with row2[2]:
        with st.container(border=True):
            st.markdown("**All Sensors — 40 reads**")
            if len(history) > 3:
                df_mini = pd.DataFrame(history[-40:])
                norm_fig = go.Figure()
                palette = ["#4caf50","#2196f3","#ff9800","#e91e63","#ffeb3b"]
                for j, s in enumerate(SENSORS):
                    vals = df_mini[s["key"]].tolist()
                    lo, hi = min(vals), max(vals)
                    normalised = [(v - lo) / (hi - lo + 1e-9) for v in vals]
                    norm_fig.add_trace(go.Scatter(
                        y=normalised, mode="lines",
                        name=s["label"],
                        line=dict(color=palette[j], width=1.5),
                    ))
                norm_fig.update_layout(
                    **plotly_base(140, margin=dict(l=0, r=0, t=28, b=0)),
                    legend=dict(font=dict(size=9), orientation="h", y=-0.3),
                    xaxis=dict(visible=False),
                    yaxis=dict(visible=False, range=[-0.05, 1.05]),
                )
                st.plotly_chart(norm_fig, width="stretch", config={"staticPlot": True})

    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)
    if st.session_state.data_source == "Bluetooth":
        # Always auto-refresh when reading from hardware
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


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Leaf Detection
# ═════════════════════════════════════════════════════════════════════════════
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
            st.image(pil_img, caption="Uploaded image", width="stretch")

        with col_pred:
            label, confidence = None, None
            if model is not None:
                with st.spinner("Running MobileNetV2…"):
                    label, confidence = predict(model, pil_img)

            if label is not None:
                prob_healthy = confidence if label == "Healthy" else 1.0 - confidence
                prob_disease = 1.0 - prob_healthy

                if confidence < 0.60:
                    st.warning(f"**Low Confidence · {label}** — {confidence*100:.1f} %\nRetake photo in better lighting.")
                elif label == "Bacterial_Wilt":
                    st.error(f"### 🦠 Bacterial Wilt Detected\n**Confidence: {confidence*100:.1f} %**")
                    st.markdown("""
**Immediate Actions:**
- Apply copper-based bactericide.
- Remove & isolate infected rhizomes.
- Improve drainage, stop overhead irrigation.
""")
                else:
                    st.success(f"### 🌿 Healthy Plant\n**Confidence: {confidence*100:.1f} %**")
                    st.markdown("Maintain current conditions. Continue regular monitoring.")
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
                st.plotly_chart(fig_gauge, width="stretch", config={"staticPlot": True})
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
                st.plotly_chart(fig_bar, width="stretch", config={"staticPlot": True})
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
            st.plotly_chart(fig_rgb, width="stretch", config={"staticPlot": True})

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
                st.plotly_chart(fig_green, width="stretch", config={"staticPlot": True})
            with gc2:
                st.plotly_chart(fig_bright, width="stretch", config={"staticPlot": True})

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
            st.plotly_chart(fig_heatmap, width="stretch", config={"staticPlot": True})
            st.caption(
                f"**Green pixel ratio: {green_pct:.1f}%** — pixels where green channel "
                f"dominates red and blue. "
                f"Mean brightness: {mean_bright:.1f}/255. "
                f"The heatmap shows which spatial regions of the leaf are green-dominant (dark green) "
                f"vs yellowing/browning (red). Diseased areas typically appear as red patches."
            )


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Live Detection
# ═════════════════════════════════════════════════════════════════════════════
elif page == "Live Detection":
    st.markdown('<div class="page-title">Live Camera Detection</div>', unsafe_allow_html=True)
    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)
    render_live_detection_page()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Sensor Data
# ═════════════════════════════════════════════════════════════════════════════
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
            st.plotly_chart(fig, width="stretch", config={"staticPlot": False})

        st.caption(f"{len(history)} readings stored · max 200 per session")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Alerts
# ═════════════════════════════════════════════════════════════════════════════
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

    st.markdown('<div class="glow-divider"></div>', unsafe_allow_html=True)
    st.markdown("**Optimal Ranges — Ginger Cultivation**")
    st.dataframe(
        pd.DataFrame([
            {"Parameter": "Temperature",   "Optimal": "20 – 32 °C",  "Warning": "32 – 38 °C",        "Critical": "< 15 °C  or  > 38 °C"},
            {"Parameter": "Humidity",      "Optimal": "40 – 75 %",   "Warning": "75 – 85 %",          "Critical": "< 30 %  or  > 85 %"},
            {"Parameter": "Soil Moisture", "Optimal": "30 – 70 %",   "Warning": "< 30 %",             "Critical": "< 20 %  or  > 85 %"},
            {"Parameter": "Soil pH",       "Optimal": "5.5 – 7.0",   "Warning": "4.5–5.5 or 7–8",     "Critical": "< 4.5  or  > 8.0"},
            {"Parameter": "Light",         "Optimal": "100 – 800 lx","Warning": "50 – 100 lx",        "Critical": "< 50 lx"},
        ]),
        width="stretch",
        hide_index=True,
    )


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: User Guide
# ═════════════════════════════════════════════════════════════════════════════
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
