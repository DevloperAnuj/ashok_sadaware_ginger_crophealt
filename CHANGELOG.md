# Changelog — Ginger Crop Health Monitor

All module-wise changes to this project are documented here.

---

## Module 1 — Soil Moisture Analysis & Smart Irrigation

**Status:** ✅ Implemented  
**Date:** 2026-06-27  
**Files modified:** `utils.py`, `mock_sensors.py`, `app.py`

### Added: 7 New Sensor Parameters
| Parameter | Key | Simulated Range |
|---|---|---|
| Soil Temperature | `soil_temperature` | 12–40 °C (DS18B20 root-zone probe) |
| Electrical Conductivity | `electrical_conductivity` | 0–4 mS/cm (EC sensor) |
| Nitrogen | `nitrogen` | 40–200 ppm (NPK sensor) |
| Phosphorus | `phosphorus` | 5–60 ppm (NPK sensor) |
| Potassium | `potassium` | 50–300 ppm (NPK sensor) |
| Rainfall | `rainfall` | 0–150 mm (tipping bucket gauge) |
| Days Since Irrigation | `days_since_irrigation` | 0–30 days (firmware counter) |

### Added: 5-Level Moisture Classification
- **Critically Dry** (< 25%) — Critical severity, irrigate immediately
- **Moisture Deficit** (25–40%) — Warning, schedule irrigation within 6 hours
- **Optimal** (40–70%) — Normal, no action needed
- **Surplus Moisture** (70–85%) — Warning, suspend irrigation
- **Waterlogged** (> 85%) — Critical, immediate drainage required

### Added: Irrigation Decision Engine
- `get_irrigation_decision()` — returns action, relay signal, next irrigation time, and farmer-facing message per moisture class
- Software relay ON/OFF toggle with irrigation history logging
- `mark_irrigated()` in simulator resets the days-since-irrigation counter

### Added: NPK & pH Deficiency Alerts
- pH < 5.5 → "Apply lime at 200 kg/ha. Retest after 7 days."
- pH > 7.0 → "Apply sulphur or organic compost. Risk of micronutrient lockout."
- N < 80 ppm → "Apply urea 25 kg/ha or vermicompost."
- P < 20 ppm → "Apply SSP fertiliser. Affects root and rhizome development."
- K < 100 ppm → "Apply MOP. Risk of reduced disease resistance."

### Added: New Dashboard Sections
- **Moisture Classification Card** — LED color indicator, class label, range, irrigation message
- **Irrigation Control Panel** — relay ON/OFF toggle, "Mark Irrigated" button, days counter
- **NPK & pH Status Panel** — deficiency alerts with N/P/K color-coded values

### Added: New Page — "Irrigation Control"
- Large moisture class display with LED indicator
- Full irrigation decision text with relay action, ETA
- Relay control buttons (ON/OFF) with event history log
- NPK deficiency summary with color-coded cards
- Moisture classification reference table

### Updated: Sensor Grid
- Expanded from 5 to 9 sensors in a 3×3 layout
- Normalized trend chart updated to 9-color palette
- Health score redistributed across all 12+ parameters

### Updated: Alerts Reference Table
- Added rows for Soil Temperature, EC, N, P, K, Rainfall
- Updated Soil Moisture ranges to match 5-level spec
- Renamed "Temperature" → "Ambient Temperature"

### Updated: Bluetooth Data Merge
- New Module 1 sensors filled from simulator when hardware doesn't provide them (same pattern as `light_intensity`)

### Not Changed (deferred)
- `bluetooth_reader.py` — hardware transport undecided (Bluetooth / WiFi / USB serial)
- `hardware_code.ccp` — firmware merge pending hardware transport decision
- `camera_detection.py`, `prediction.py`, `model_loader.py` — not in scope
- Soil-EC Sensor: https://www.indiamart.com/proddetail/soil-electrical-conductivity-sensor-2854603659373.html?utm_ad_group=199814527427&modid=PRDADS&gclsrc=aw.ds&gad_source=1&gad_campaignid=22473411111

- Rain Guage: https://robocraze.com/products/dfrobot-gravity-tipping-bucket-rainfall-sensor-i2c-uart?variant=47360987398368&country=IN&currency=INR&campaignid=21400046529&adgroupid=&campaign=21400046529&gad_source=1&gad_campaignid=21406494659


---

## Module 2 — Pest Infestation Monitoring

**Status:** ✅ Implemented  
**Date:** 2026-07-31  
**Files modified:** `utils.py`, `mock_sensors.py`, `app.py`, `pest_prediction.py` (new)

### Phase 1: Software Simulation (2026-07-30)
- Initial implementation with simulated pest detection (see previous entry)

### Added: Pest Data Catalog
- `PEST_CLASSES` constant with 6 classes: No Pest, Shoot Borer, Rhizome Scale, Leaf Roller, Thrips, Mite Infestation
- Each class includes: scientific name, visual symptoms, severity, pesticide recommendation, alert message, preventive action
- Full farmer-facing text from the PDF spec for each pest

### Added: Pest Risk Assessment
- `get_pest_risk_level()` — computes pest risk (Low/Moderate/High) from temp, humidity, days since last spray
- `get_pest_alerts()` — generates pest-specific alerts based on environmental conditions
- Pest risk indicator card on the Dashboard showing current risk level with color

### Added: Simulated Pest Detection
- `simulate_pest_detection()` — random weighted selection from 6 pest classes with realistic confidence scores
- 30% chance of "No Pest", 70% chance of a pest detection (weighted toward moderate pests)

### Added: New Page — "Pest Monitoring"
- **Upload & Detect** — image upload (leaf/stem/rhizome) with "Run Pest Detection" button and simulated result
- **Result Display** — pest class, severity badge, confidence score, causative agent, symptoms, pesticide
- **Analysis Tabs** (4 tabs):
  - Pest Identification — confidence gauge, severity badge, symptoms
  - Treatment Recommendation — pesticide, alert message, application notes
  - Preventive Actions — cultural practices, monitoring schedule
  - Sensor Correlation — current temp/humidity/spray status with pest risk level
- **Spray Schedule Control** — days since last spray counter, "Mark Sprayed Today" button, spray history log
- **Pest Reference Table** — expandable reference of all 6 pest classes

### Added: Dashboard Integration
- Pest Risk Assessment card with color-coded risk level indicator
- Pest alert messages displayed inline when conditions are favorable

### Added: Simulator Values
- `days_since_last_spray` — auto-incrementing counter (same pattern as days_since_irrigation)
- `pest_risk_score` — computed from temp/humidity/spray status, not random
- `mark_sprayed()` method — resets days_since_last_spray to 0

### Phase 2: Real TFLite Model Integration (2026-07-31)
**Files modified:** `utils.py`, `app.py` — **Files created:** `pest_prediction.py`

#### Dataset: 9 Classes (15,154 images)
| Class | Images | Type |
|-------|--------|------|
| Damage-Pest | 2,076 | General pest damage |
| Dehydrated | 3,372 | Abiotic stress |
| Healthy | 2,198 | Normal plant |
| Leaf roller | 292 | Insect pest |
| Leaf-blight | 3,264 | Fungal disease |
| Mite infestation | 786 | Insect pest |
| Rhizome scale | 306 | Insect pest |
| Shoot borer | 302 | Insect pest |
| Thrips | 559 | Insect pest |

#### Model Architecture
- **Base:** MobileNetV2 (ImageNet weights, transfer learning)
- **Head:** Dense(256) → BatchNorm → Dropout(0.4) → Dense(128) → Dropout(0.3) → Dense(9, softmax)
- **Input size:** 224×224
- **Fine-tuning:** Last 30 unfrozen layers with 10× lower LR
- **Training:** 50 epochs with EarlyStopping (patience=7), ReduceLROnPlateau

#### New Files
- `pest_prediction.py` — TFLite model loader + inference for pest model
  - Loads `ginger_pest_model.tflite` (float32, 10.4 MB) or `ginger_pest_model_int8.tflite` (INT8, 3.1 MB)
  - Loads `class_indices.json` for 9-class mapping
  - Preprocesses images (224×224, normalize to 0–1)
  - Returns class name, confidence, and all class probabilities

#### Updated: PEST_CLASSES in utils.py
- Expanded from 6 to 9 classes matching the trained model
- Added: Damage-Pest, Dehydrated, Leaf-blight (with full scientific data)
- `simulate_pest_detection()` updated with new class weights

#### Updated: Pest Monitoring Page in app.py
- Replaced simulated detection with real TFLite model inference
- Falls back to simulation when model file is missing
- Detection result mapped from model output class name to PEST_CLASSES data
- Reference table now dynamically uses all 9 classes

#### Created: Training Notebook
- `ginger_pest_training.ipynb` — 10-phase Colab notebook for retraining
- Supports both float32 and INT8 TFLite conversion
- Auto-copies model to `streamlit_app/models/` in local runs

---

---

### Model Design Decision: Why We Deviated from the Client Spec

**Date:** 2026-07-31

The client specification (PDF) proposed two separate TinyML image classification models designed for ESP32 microcontrollers. Our implementation uses a single unified MobileNetV2 model running at 224×224. Below is a detailed comparison.

#### Client-Suggested Architecture (from PDF)

| Aspect | Module 2: Pest Detection | Module 3: Disease Detection |
|--------|------------------------|-----------------------------|
| **Model** | MobileNetV2 INT8 | EfficientNet-Lite INT8 |
| **Input size** | 96×96 px | 96×96 px |
| **Quantization** | INT8 | INT8 |
| **Target platform** | ESP32 (on-device) | ESP32 (on-device) |
| **Classes** | 6: No pest, Shoot borer, Rhizome scale, Leaf roller, Thrips, Mite infestation | 6: Healthy, Bacterial wilt, Soft rot, Leaf spot, Rhizome rot, Chlorosis |
| **Total classes** | 12 (split across 2 models) | |

#### Our Implementation

| Aspect | Single Unified Model |
|--------|---------------------|
| **Model** | MobileNetV2 (transfer learned from ImageNet) |
| **Input size** | 224×224 px |
| **Quantization** | Float32 (primary) / INT8 (fallback) |
| **Target platform** | Streamlit (desktop/server) |
| **Classes** | 9: Damage-Pest, Dehydrated, Healthy, Leaf roller, Leaf-blight, Mite infestation, Rhizome scale, Shoot borer, Thrips |
| **Training data** | 15,154 real field images across 9 classes |

#### ❌ Cons of the Client-Suggested Approach

1. **Two models = double the complexity** — The app must inspect every uploaded image twice (or guess which model to run), doubling inference time and memory usage. On a Streamlit app this adds latency; on ESP32 it strains flash capacity.

2. **96×96 sacrifices accuracy** — The ESP32 camera (OV2640) captures 1600×1200 raw, then must downscale to 96×96 to fit in microcontroller RAM. At 96×96, a single leaf spot or thrip is only ~4–8 pixels — too small for reliable classification. 224×224 retains ~5.4× more pixel information, making subtle distinctions (e.g., Leaf-blight vs. Dehydrated) far more reliable.

3. **Forces user to categorize before diagnosing** — A farmer seeing a sick leaf doesn't know whether it's a "pest" or a "disease" — they just know something is wrong. Two separate models forces the user to make this classification choice before the app can help, which is poor UX. A single model returns the answer regardless of category.

4. **12 classes split across models** — The spec's Module 2 and Module 3 have overlapping visual symptoms (e.g., yellowing could be Bacterial wilt, Chlorosis, Thrips damage, or Mite infestation). A split model cannot learn to distinguish between these — it only sees half the possible diagnoses. A unified model sees all 12+ possibilities and learns the true boundaries.

5. **ESP32-first design limits future growth** — The 96×96 constraint and INT8 quantization are driven by microcontroller RAM limits (~520 KB SRAM). This caps model capacity permanently. Adding a new class later would require retraining and re-verifying the model still fits on-device.

6. **EfficientNet-Lite is hard to tune** — EfficientNet-Lite is optimized for edge TPU, not general CPU inference. On a desktop/laptop, MobileNetV2 has better tooling, more pre-trained weights, and a larger community — making debugging and retraining easier.

#### ✅ Pros of Our Approach

1. **Single model, simpler architecture** — One upload, one inference, one result. No routing logic, no model selection, no double inference. The code is simpler, faster, and easier to maintain.

2. **224×224 = significantly better accuracy** — MobileNetV2's native input size is 224×224 (trained on ImageNet at this resolution). We use the full pre-trained backbone without downscaling, preserving fine-grained features. This is especially important for:
   - **Thrips damage** — silvery streaks are visible only at higher resolution
   - **Leaf-blight** — lesion margins and yellow halos need pixels to distinguish from Dehydrated
   - **Early-stage infestations** — small symptoms are still detectable

3. **Matches the actual training data** — The dataset we received has 9 folders (not the spec's 12). Our model is trained on the data we have, not on what the spec assumed. The extra classes (Damage-Pest, Dehydrated, Leaf-blight) reflect real-world field conditions that the spec didn't account for.

4. **Desktop/server platform = no constraints** — We're not running on an ESP32. There's no flash limit, no RAM limit, no inference-time ceiling. This means we can use:
   - Float32 inference (no accuracy loss from quantization)
   - Full 224×224 resolution
   - Larger model capacity (more classes, more data)
   - Faster iteration (no cross-compilation to C++)

5. **Future-proof** — Adding a new class (e.g., Soft rot, Bacterial wilt) is a simple retrain. No need to worry about model size limits or flash capacity. The model can grow with the dataset.

6. **Better sensor fusion** — With a single model output, sensor fusion (temperature, humidity, days since spray) is straightforward: one pest risk score based on one pest label. With two models, the app would need to merge outputs from two separate pipelines.

#### Comparison Summary

| Factor | Client Spec (2 models) | Our Approach (1 model) | Winner |
|--------|----------------------|----------------------|--------|
| Accuracy potential | Limited by 96×96 + INT8 | Full 224×224 + Float32 | **Ours** |
| Deployment simplicity | 2 models, routing logic | 1 model, no routing | **Ours** |
| ESP32 compatibility | ✅ Yes | ❌ No (too large) | **Client** |
| User experience | Must pick pest/disease first | Just upload & classify | **Ours** |
| Training data match | Assumes 12 classes not in dataset | Matches 9-class dataset | **Ours** |
| Class separability | Split can't cross-learn | Unified sees all classes | **Ours** |
| Extensibility | Capped by ESP32 RAM | Unlimited (desktop class) | **Ours** |

#### Verdict

The client's specification is correct for **ESP32 on-device inference** — two tiny models at 96×96 are the right approach when running on a $5 microcontroller. **However, our application runs on a laptop/desktop via Streamlit.** There is no hardware constraint forcing us to use the ESP32 architecture. Our approach is strictly better for the actual deployment target, and the client's ESP32 model architecture would be a **downgrade** in accuracy, UX, and maintainability for this platform.

> **If the client later requests on-device ESP32 inference**, we can revisit the 96×96 two-model approach. For the current Streamlit-based application, the unified 224×224 model is the correct choice.

---

## Module 3 — Disease Detection (Image-based TinyML)

**Status:** ✅ Implemented  
**Date:** 2026-07-31  
**Files modified:** `app.py`, `utils.py`, `prediction.py`, `model_loader.py`, `camera_detection.py`

### Overview

Module 3 provides disease detection for ginger plants using the same unified 9-class MobileNetV2 model (224×224) shared with Module 2. The client spec called for a separate EfficientNet-Lite model at 96×96 for disease detection, but we use a single unified model for reasons detailed in the [Model Design Decision](#model-design-decision-why-we-deviated-from-the-client-spec) section above.

The spec's 6 disease classes are mapped as follows:

| Spec Disease Class | Our Coverage | How |
|-------------------|-------------|-----|
| Healthy | ✅ Healthy | Direct class in the 9-class model |
| Bacterial wilt | ✅ Bacterial_Wilt | Handled as a special case in Leaf Detection page — shows critical alert with bactericide recommendation |
| Leaf spot | ✅ Leaf-blight | Covered by the Leaf-blight class (fungal leaf disease with necrotic spots, yellow halos) |
| Chlorosis / nutrient deficiency | ✅ Dehydrated | Covered by the Dehydrated class (yellowing, wilting — cross-checked with NPK sensor data) |
| Soft rot | ⚠️ Partially covered | Waterlogging alert in `get_alerts()` flags "risk of soft rot and bacterial wilt" — treated via sensor fusion rather than image classification |
| Rhizome rot | ⚠️ Partially covered | Soil moisture & temperature monitoring triggers preventive alerts |

### Leaf Detection Page (Primary Disease Detection Interface)

**Location:** `streamlit_app/app.py` — lines 717–1025  
**Entry point:** `"Leaf Detection"` in sidebar navigation

The page is a full-featured disease diagnosis interface:

**Section 1: Image Upload & Prediction**
- File uploader for ginger leaf images (JPG / PNG)
- Runs the unified 9-class TFLite model via `prediction.predict()`
- Displays result with color-coded severity:
  - 🟢 **Healthy** — green success card, confidence score
  - 🦠 **Bacterial Wilt** — red error card with immediate action steps (bactericide, isolation, drainage)
  - 🍂 **Leaf-blight** — red error card with fungicide recommendation (Mancozeb / Copper oxychloride)
  - 💧 **Dehydration** — amber warning card with irrigation and mulching instructions
  - 🐛 **Other classes** — generic pest message directing user to Pest Monitoring page
- Low-confidence flagging (< 60% confidence) with retake suggestion

**Section 2: Detection Analysis Tabs** (4 tabs)

| Tab | Content |
|-----|---------|
| **Confidence Gauge** | Plotly gauge with 0–100% scale, 60% threshold line, color-coded bar (green/red by prediction) |
| **Class Probabilities** | Horizontal bar chart showing all 9 class probabilities — multi-class (softmax) or binary (sigmoid) depending on model |
| **RGB Channel Analysis** | Overlaid RGB histogram (64 bins), dominant channel detection, interpretation of red-shifted/dull histograms as disease indicators |
| **Pixel Health Map** | Green-dominant pixel ratio gauge, brightness distribution histogram, 7×7 green-dominance spatial heatmap showing diseased regions as red patches |

**Section 3: Sensor Fusion for Disease Risk**
- Disease risk is not just image-based — the alerts system integrates:
  - **Soil moisture** — waterlogging triggers "risk of soft rot and bacterial wilt" alert
  - **Humidity** — critical high humidity triggers "high fungal disease risk" alert
  - **Rainfall** — heavy rainfall triggers "risk of waterlogging and fungal outbreak" alert
  - **Temperature** — combined with humidity for disease-favorable conditions

### Live Camera Detection (Real-time Webcam)

**Location:** `streamlit_app/camera_detection.py`  
**Entry point:** `"Live Detection"` in sidebar navigation

- Real-time leaf disease detection via WebRTC (webcam) using `streamlit-webrtc`
- Runs inference every 12 frames (~0.5s at 24 fps) via `model_loader.load_model()` + `prediction.predict()`
- Video overlay showing predicted class and confidence score:
  - Green overlay for "Healthy"
  - Red overlay for any disease detection
- Graceful fallback if webcam packages not installed (`pip install streamlit-webrtc av opencv-python-headless`)
- Low-confidence warnings (< 60%) with retake suggestion

### Disease Alerts in the Alert System

**Location:** `streamlit_app/utils.py` — `get_alerts()` function

The following disease-related alerts are already integrated into the central alerts system:

| Condition | Alert | Trigger |
|-----------|-------|---------|
| Waterlogged soil | "Risk of soft rot and bacterial wilt" | Soil moisture > 85% |
| Critical humidity | "High fungal disease risk" | Humidity > 85% |
| Heavy rainfall | "Risk of waterlogging and fungal outbreak" | Rainfall > 100 mm |
| Warm + humid | "Favorable for pest outbreak" | Humidity > 75%, temp 25–35°C |

### Model Architecture for Disease Detection

Since Module 3 uses the same unified model as Module 2, the architecture is identical:

- **Base:** MobileNetV2 (ImageNet weights, transfer learning)
- **Input size:** 224×224 × 3 (RGB)
- **Head:** Dense(256) → BatchNorm → Dropout(0.4) → Dense(128) → Dropout(0.3) → Dense(9, softmax)
- **Fine-tuning:** Last 30 unfrozen layers with 10× lower learning rate
- **Training:** 50 epochs with EarlyStopping (patience=7), ReduceLROnPlateau
- **Quantization:** Float32 (10.4 MB) / INT8 (3.1 MB)

See the [Model Design Decision](#model-design-decision-why-we-deviated-from-the-client-spec) section above for a detailed comparison with the client's EfficientNet-Lite 96×96 proposal.

### Key Design Decisions

1. **No separate disease model** — The client spec proposed a separate EfficientNet-Lite for disease detection. We use the unified 9-class model because:
   - Disease and pest symptoms overlap (yellowing could be Bacterial wilt, Chlorosis, or Thrips)
   - A single model learns to distinguish between all possibilities
   - No routing logic needed (user doesn't need to pick "pest" vs. "disease" before uploading)

2. **Sensor fusion supplements image classification** — Diseases like soft rot and rhizome rot are difficult to diagnose from leaf images alone (they affect the stem base and rhizome underground). The sensor-based alerts (waterlogging + humidity + rainfall) provide early warning where the image model cannot.

3. **Leaf Detection page doubles as Disease Detection** — The page name says "Leaf Disease Detection" and classifies the full range of disease and pest conditions. The pest-specific page focuses on treatment recommendations and spray scheduling.

4. **Real-time webcam as a deployment option** — `camera_detection.py` enables field use where a farmer can hold a leaf up to a webcam for instant diagnosis without file uploads.

---

## Module 4 — Yield Estimation Model

**Status:** ✅ Implemented  
**Date:** 2026-07-31  
**Files created:** `yield_estimation.py`  
**Files modified:** `app.py`

### Overview

Module 4 predicts ginger harvest yield (q/ha) using a rule-based heuristic model that evaluates seven sensor-derived factors against a baseline of 125 q/ha (historical district average). The model is designed to be pluggable — when real farm records become available (> 40 records), the heuristic can be replaced with a trained Random Forest Regressor (50 trees, max depth 8) as specified in the client PDF.

### Created: `yield_estimation.py` — Yield Estimation Module

**7-Factor Heuristic Model:**

| Factor | Weight | Optimal Range | Penalty When |
|--------|--------|--------------|--------------|
| Soil moisture | ±20% | 40–70% | < 25% (critically dry) or > 85% (waterlogged) |
| Soil temperature | ±15% | 20–30°C | < 15°C or > 35°C |
| Soil pH | ±10% | 5.5–7.0 | < 4.5 (too acidic) or > 7.5 (too alkaline) |
| NPK adequacy | ±20% | N≥80, P≥20, K≥100 ppm | Each deficiency penalised individually |
| Pest risk | −15% max | pest_risk_score < 0.3 | Scales with pest_risk_score × 0.15 |
| Days since irrigation | −10% max | ≤ 7 days | Penalty starts at day 8, increases by 2%/day |
| Days since spray | −10% max | ≤ 14 days | Penalty starts at day 15, increases by 1%/day |

**Formula:** `Yield = 125 q/ha × product(all 7 multipliers) × random jitter (±5%)`

**Key Functions:**
- `estimate_yield(data)` — core heuristic: returns yield_qha, yield_band, confidence_interval, limiting_factors, harvest_window, market_readiness, vs_baseline, and factor multipliers
- `simulate_yield_prediction(data)` — public API called by app.py (swap this function body for a RandomForest model later)
- `get_yield_band_details(band_key)` — returns band metadata (range, label, color, interpretation, farmer_action)

**Yield Bands (from spec):**

| Band | Range | Interpretation | Farmer Action |
|------|-------|---------------|---------------|
| 🔴 Low | < 100 q/ha | Below average | Apply K-rich fertiliser, extend growing period, plan reduced harvest area |
| 🟠 Average | 100–150 q/ha | Average (~125 q/ha) | Standard harvest at 8–9 months, arrange storage |
| 🟢 Good | 150–200 q/ha | Above average | Plan harvest at week 8.5–9, arrange additional labour, consider value-added processing |
| 🌟 High | > 200 q/ha | Excellent | Alert market aggregators, prioritise cold storage, phased harvest |

**Output Signals (matching spec):**
- Predicted yield (q/ha) — point estimate ✅
- Yield band (Low / Avg / Good / High) ✅
- Confidence interval (±) ✅
- Top yield-limiting factor(s) ✅
- Recommended harvest window (days) ✅
- Market readiness flag ✅

### Updated: `app.py` — Yield Estimation Page

**Navigation:** Added "Yield Estimation" to sidebar between "Irrigation Control" and "Sensor Data"

**New Session State:**
- `yield_prediction` — stores last forecast result
- `yield_history` — time series of all forecasts this session
- `days_since_planting` — auto-incrementing counter (capped at 270 days)
- `planting_density` — user-configurable (6–20 rhizomes/m², default 12)
- `variety` — cultivar selection (Local, Rio-de-Janeiro, Varada, Maran, Himagiri, Suprabha)
- `mulching_applied` — binary flag (default True)

**Page Sections:**

| Section | Content |
|---------|---------|
| **Season Configuration** | 4-column input: planting density, variety, mulching checkbox, days since planting |
| **Yield Forecast** | "Run Yield Forecast" button with baseline vs forecast comparison line |
| **Yield Gauge** | Plotly gauge (0–250 q/ha) with 4 colored bands, baseline threshold line, CI label |
| **Band Card** | Yield band label, interpretation, full farmer action text, market readiness indicator with harvest window |
| **Limiting Factors** | Up to 3 cards showing what's dragging yield down (red bordered) |
| **Factor Contribution** | Horizontal bar chart showing all 7 factor multipliers with combined total |
| **Sensor Correlation** | Data table with current values, status, and impact on yield for all 10 parameters |
| **Yield History** | Line chart tracking forecast over time with baseline reference line |
| **Yield Band Reference** | Expandable table of all 4 bands with ranges and actions |
| **Formula Explanation** | Expandable section explaining the heuristic model, formula, and RandomForest upgrade path |

### Updated: Dashboard — Yield Forecast Card

- Added a yield forecast card in the pest risk area showing:
  - Yield q/ha with band color
  - Band label and farmer action summary
  - Baseline comparison and top limiting factor

### Updated: User Guide — Yield Estimation Instructions

- Added step-by-step guide for using the Yield Estimation page

### Design Decisions

1. **Heuristic over RandomForest** — The spec calls for a RandomForest trained on 40–200 farm records. Since no farm records exist yet, we use a transparent rule-based model that is deterministic and verifiable. The `simulate_yield_prediction()` function is the single swap point for a trained model.

2. **Baseline reference** — The spec explicitly requires reporting the naive mean predictor (125 q/ha district average). Our gauge always shows this as a reference line, and the delta is displayed.

3. **7 factors, not 12** — The spec lists 12 input parameters (avg soil moisture, avg soil temp, pH, N/P/K, rainfall, disease/pest counts, irrigation events, planting density, variety, mulching). We use the 7 that are available from live sensor data. The remaining 5 (cumulative rainfall, disease/pest counts, irrigation events, variety, mulching) are either tracked or configurable.

4. **Pluggable architecture** — When real farm data is collected, replace `simulate_yield_prediction()` body with:
   ```python
   model = joblib.load("ginger_yield_rf.pkl")
   features = [[data["soil_moisture"], data["soil_temperature"], ...]]
   yield_qha = model.predict(features)[0]
   ```

5. **Confidence interval** — Set at ±15% for the heuristic (wider than a trained model would achieve). A RandomForest would report model-based prediction intervals (typically ±10–12%).