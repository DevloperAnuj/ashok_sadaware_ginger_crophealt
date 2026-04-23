# User Manual — Ginger Crop Health Monitor

## Project Summary

The **Ginger Crop Health Monitor** is an IoT + AI system designed for real-time monitoring of ginger cultivation. It combines physical soil and climate sensors connected to an ESP32 microcontroller with a deep learning model (MobileNetV2) that detects ginger leaf disease from camera images.

The system has two layers:

- **Hardware layer** — ESP32 with DHT22 (temperature/humidity), soil moisture sensor, and pH sensor. Readings are broadcast over Classic Bluetooth to a Windows PC.
- **Software layer** — Streamlit web dashboard that displays sensor data, fires threshold alerts, and runs AI leaf disease detection via webcam or uploaded photo.

---

## Pages

### Dashboard

The main overview page. Shows the current state of all five sensors at a glance.

- **Farm Health Score** — A single 0–100 score computed from all sensor readings. Green (≥70) = healthy, orange (45–69) = caution, red (<45) = critical.
- **Sensor Cards** — Each card shows the live value, the change from the previous reading (delta), and a sparkline of the last 40 readings.
- **Active Conditions** — Top four alerts are shown inline. Full list is on the Alerts page.
- **All Sensors overlay** — Normalised trend chart showing all five sensors together to spot correlated changes.
- **Refresh** — In Historical Data mode, use the Refresh Now button or toggle Auto-refresh (every 5 s). In Bluetooth mode, the dashboard refreshes automatically every 2 s from live hardware.

---

### Leaf Detection

Upload a photo of a ginger leaf for AI disease analysis.

**How to use:**
1. Click **Browse files** and select a JPG or PNG image of a ginger leaf.
2. The model predicts **Healthy** or **Bacterial Wilt** with a confidence percentage.
3. If confidence is below 60%, a low-confidence warning is shown — retake the photo in better lighting, closer to the leaf, against a plain background.

**Analysis tabs shown after upload:**

| Tab | Description |
|---|---|
| Confidence Gauge | Arc gauge showing model confidence. White threshold line at 60%. |
| Class Probabilities | Horizontal bars showing P(Bacterial Wilt) and P(Healthy). |
| RGB Channel Analysis | Pixel intensity histogram for Red, Green, Blue channels. Healthy leaves show a strong green peak. |
| Pixel Health Map | Green-dominance ratio gauge, brightness distribution histogram, and a 7×7 spatial heatmap showing which parts of the leaf are green vs yellowing. |

**If Bacterial Wilt is detected**, the recommended actions are displayed:
- Apply copper-based bactericide immediately
- Isolate and remove heavily infected rhizomes
- Improve field drainage and avoid overhead irrigation

---

### Live Detection

Real-time webcam disease detection using WebRTC.

**How to use:**
1. Click **Start** — the browser will ask for camera permission. Click **Allow**.
2. Point the camera at a ginger leaf.
3. The AI label (`Healthy` or `Bacterial Wilt`) and confidence percentage appear as an overlay on the video, updating approximately every 12 frames (~0.5 s at 24 fps).
4. Click **Stop** to close the camera.

> Requires **Chrome** or **Edge**. The stream runs entirely on your local machine (no video is sent to the internet).

---

### Sensor Data

Full session history for all five sensors as interactive line charts.

- Up to **200 readings** are stored per session.
- Hover over a chart to read exact values at any point.
- Drag to zoom into a time range; double-click to reset.
- Charts update each time the page is visited or the app refreshes.

---

### Alerts

Real-time list of all active threshold violations.

- **Critical** alerts (red) — values outside safe operating limits. Immediate action needed.
- **Warning** alerts (orange) — values approaching limits. Monitor closely.
- **All clear** (green) — all parameters within optimal range.

**Reference table — Optimal ranges for ginger cultivation:**

| Parameter | Optimal | Warning | Critical |
|---|---|---|---|
| Temperature | 20 – 32 °C | 32 – 38 °C | < 15 °C or > 38 °C |
| Humidity | 40 – 75 % | 75 – 85 % | < 30 % or > 85 % |
| Soil Moisture | 30 – 70 % | < 30 % | < 20 % or > 85 % |
| Soil pH | 5.5 – 7.0 | 4.5–5.5 or 7–8 | < 4.5 or > 8.0 |
| Light Intensity | 100 – 800 lux | 50 – 100 lux | < 50 lux |

---

## Data Source

The sidebar **Data Source** panel switches between two modes:

### Historical Data (default)
Uses a built-in sensor simulator. Useful for testing the dashboard without hardware. The simulator generates realistic fluctuating values within normal ginger cultivation ranges.

### Bluetooth (ESP32)
Reads live values from the ESP32 GingerMonitor hardware over a Bluetooth COM port.

**To connect:**
1. Power on the ESP32.
2. On Windows, go to **Settings → Bluetooth & devices** and pair the device named **GingerMonitor** (one-time setup).
3. In the app sidebar, select **Bluetooth (ESP32)**.
4. Choose the COM port (e.g. `COM5 — GingerMonitor`) from the dropdown.
5. Click **Connect**.
6. The dashboard loads automatically once the first data packet is received.

When connected, the sidebar shows the device name, latest readings summary, and a **Serial Log** expander with raw timestamped lines from the ESP32.

> The hardware does not have a light sensor. Light intensity is taken from the simulator and merged with the real readings.

**Moisture calibration:** The soil moisture sensor reads 4095 (dry, open air) and drops when wet. The conversion to percentage uses calibration constants in `bluetooth_reader.py`:
- `DRY_RAW = 4095` — sensor in open air
- `WET_RAW = 1500` — sensor submerged in water (adjust after measuring your sensor)

To calibrate: dip the sensor in water, note the ADC value printed in the Serial Log, and update `WET_RAW` in `bluetooth_reader.py`.

---

## Setting Up the AI Model

The AI model must be trained once in Google Colab before AI features (Leaf Detection, Live Detection) work.

**Steps:**
1. Upload your dataset to Google Drive at:
   ```
   My Drive/Datasets/ginger_plant_dataset/train/Bacterial_Wilt/
   My Drive/Datasets/ginger_plant_dataset/train/Healthy/
   ```
2. Open `ginger_cnn_training.ipynb` in [Google Colab](https://colab.research.google.com).
3. Set the runtime to **GPU → T4** (Runtime → Change runtime type).
4. Run all cells (Runtime → Run all).
5. After training completes, run **Phase 9** — it converts the model to TFLite and downloads `ginger_disease_model.tflite`.
6. Place the downloaded file into `streamlit_app/models/`.
7. Restart the Streamlit app — the model loads automatically.

> If Colab disconnects after training but before Phase 9: start a new session, upload the `.h5` file, and run Phase 9 alone — it is self-contained.

---

## Running the App

```bash
streamlit run streamlit_app/app.py
```

Open `http://localhost:8501` in Chrome or Edge.

---

## Troubleshooting

| Issue | Solution |
|---|---|
| No Bluetooth ports shown | Pair the ESP32 in Windows Bluetooth settings first |
| Connect button fails | Check the COM port in Device Manager; try re-pairing |
| Moisture always 0% or 100% | Calibrate `WET_RAW` in `bluetooth_reader.py` |
| Live camera not starting | Allow camera permission in the browser; use Chrome or Edge |
| Model not loading | Check `streamlit_app/models/ginger_disease_model.tflite` exists |
| Low confidence predictions | Use better lighting; move camera/photo closer to the leaf |
| WebRTC stream won't start | Disable VPN or firewall rules blocking WebRTC STUN traffic |
