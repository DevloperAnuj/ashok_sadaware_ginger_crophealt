import json
import os
import numpy as np
import streamlit as st
from PIL import Image

_MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
_MODEL_PATH = os.path.join(_MODELS_DIR, "ginger_pest_model.tflite")
_INDICES_PATH = os.path.join(_MODELS_DIR, "class_indices.json")
IMG_SIZE = (224, 224)


def _load_class_indices() -> dict:
    """Load class_indices.json and return {index: class_name} mapping."""
    if not os.path.exists(_INDICES_PATH):
        st.warning(f"class_indices.json not found at {_INDICES_PATH}")
        return {}
    with open(_INDICES_PATH, "r") as f:
        idx_to_name = json.load(f)  # {"Damage-Pest": 0, "Dehydrated": 1, ...}
    # Reverse to {0: "Damage-Pest", 1: "Dehydrated", ...}
    return {v: k for k, v in idx_to_name.items()}


@st.cache_resource
def load_pest_model():
    """
    Load ginger_pest_model.tflite from streamlit_app/models/.
    Returns an allocated Interpreter, or None if the file is missing.
    """
    if not os.path.exists(_MODEL_PATH):
        return None
    try:
        from ai_edge_litert.interpreter import Interpreter
        interpreter = Interpreter(model_path=_MODEL_PATH)
        interpreter.allocate_tensors()
        return interpreter
    except Exception as exc:
        st.warning(f"Pest model could not be loaded: {exc}")
        return None


def preprocess_image(image: Image.Image) -> np.ndarray:
    """Resize and normalize image for model input."""
    image = image.convert("RGB")
    image = image.resize(IMG_SIZE)
    arr = np.array(image, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)  # shape: (1, 224, 224, 3)


def predict_pest(model, image: Image.Image) -> tuple[str | None, float | None, np.ndarray | None]:
    """
    Run inference using the pest TFLite model.
    Returns (class_name, confidence, all_probabilities).
    Returns (None, None, None) when model is unavailable.
    """
    if model is None:
        return None, None, None

    idx_to_class = _load_class_indices()
    if not idx_to_class:
        return None, None, None

    processed = preprocess_image(image)

    input_details = model.get_input_details()
    output_details = model.get_output_details()

    model.set_tensor(input_details[0]["index"], processed)
    model.invoke()
    probs = model.get_tensor(output_details[0]["index"])[0]  # shape: (9,)

    pred_idx = int(np.argmax(probs))
    confidence = float(probs[pred_idx])
    class_name = idx_to_class.get(pred_idx, "Unknown")

    return class_name, confidence, probs