import os
import streamlit as st

_MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")


@st.cache_resource
def load_model():
    """
    Load ginger_disease_model.tflite from streamlit_app/models/.
    Returns an allocated Interpreter, or None if the file is missing.
    """
    model_path = os.path.join(_MODELS_DIR, "ginger_disease_model.tflite")
    if not os.path.exists(model_path):
        return None
    try:
        from ai_edge_litert.interpreter import Interpreter
        interpreter = Interpreter(model_path=model_path)
        interpreter.allocate_tensors()
        return interpreter
    except Exception as exc:
        st.warning(f"Model could not be loaded: {exc}")
        return None
