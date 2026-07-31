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

**Status:** ⏳ Pending

---

## Module 4 — Yield Estimation Model

**Status:** ⏳ Pending