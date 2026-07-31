import os
import streamlit as st

_MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

# Priority order of model files to try
_MODEL_PRIORITY = [
    "ginger_disease_model.tflite",   # 1. Old binary disease model (Bacterial_Wilt / Healthy)
    "ginger_pest_model.tflite",      # 2. New 9-class pest model (includes Healthy)
    "ginger_pest_model_int8.tflite", # 3. INT8 quantized pest model (fallback)
]


@st.cache_resource
def load_model():
    """
    Load a TFLite model from streamlit_app/models/.
    Tries multiple model filenames in priority order.
    Returns an allocated Interpreter, or None if no model is found.
    """
    model_path = None
    for name in _MODEL_PRIORITY:
        candidate = os.path.join(_MODELS_DIR, name)
        if os.path.exists(candidate):
            model_path = candidate
            break

    if model_path is None:
        return None

    try:
        from ai_edge_litert.interpreter import Interpreter
        interpreter = Interpreter(model_path=model_path)
        interpreter.allocate_tensors()
        return interpreter
    except Exception as exc:
        st.warning(f"Model could not be loaded: {exc}")
        return None


