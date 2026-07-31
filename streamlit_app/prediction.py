import json
import os
import numpy as np
from PIL import Image

# Binary model: Bacterial_Wilt → 0,  Healthy → 1
BINARY_CLASSES = {0: "Bacterial_Wilt", 1: "Healthy"}
IMG_SIZE = (224, 224)

_MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
_INDICES_PATH = os.path.join(_MODELS_DIR, "class_indices.json")


def _load_multi_class_names() -> dict:
    """Load class_indices.json and return {index: class_name} mapping."""
    if not os.path.exists(_INDICES_PATH):
        return {}
    with open(_INDICES_PATH, "r") as f:
        idx_to_name = json.load(f)  # {"Damage-Pest": 0, ...}
    return {v: k for k, v in idx_to_name.items()}  # {0: "Damage-Pest", ...}


def preprocess_image(image: Image.Image) -> np.ndarray:
    image = image.convert("RGB")
    image = image.resize(IMG_SIZE)
    arr = np.array(image, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)  # shape: (1, 224, 224, 3)


def predict(model, image: Image.Image) -> tuple[str | None, float | None, list | None]:
    """
    Run inference using a TFLite Interpreter (ai-edge-litert).
    Handles both binary (sigmoid, 1 output) and multi-class (softmax, 9 outputs) models.

    Returns (label, confidence, all_probs) where:
      - label: class name string
      - confidence: float ∈ [0.5, 1.0] for binary, raw softmax prob for multi-class
      - all_probs: list of (class_name, probability) tuples, or None for binary
    Returns (None, None, None) when model is unavailable.
    """
    if model is None:
        return None, None, None

    processed = preprocess_image(image)

    input_details  = model.get_input_details()
    output_details = model.get_output_details()

    model.set_tensor(input_details[0]["index"], processed)
    model.invoke()
    output = model.get_tensor(output_details[0]["index"])[0]  # shape: (1,) or (9,)

    num_outputs = len(output)

    if num_outputs == 1:
        # ── Binary model (sigmoid) ──────────────────────────────────────────
        raw_prob = float(output[0])  # P(Healthy)
        label      = BINARY_CLASSES[1] if raw_prob > 0.5 else BINARY_CLASSES[0]
        confidence = raw_prob if raw_prob > 0.5 else 1.0 - raw_prob
        return label, confidence, None

    else:
        # ── Multi-class model (softmax) ─────────────────────────────────────
        multi_class_names = _load_multi_class_names()
        pred_idx = int(np.argmax(output))
        confidence = float(output[pred_idx])
        class_name = multi_class_names.get(pred_idx, f"Class_{pred_idx}")
        # Build list of (class_name, prob) for all classes
        all_probs = [
            (multi_class_names.get(i, f"Class_{i}"), float(output[i]))
            for i in range(num_outputs)
        ]
        # Sort by probability descending
        all_probs.sort(key=lambda x: x[1], reverse=True)
        return class_name, confidence, all_probs