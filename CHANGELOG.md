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

## Module 3 — Disease Detection (Image-based TinyML)

**Status:** ⏳ Pending

---

## Module 4 — Yield Estimation Model

**Status:** ⏳ Pending