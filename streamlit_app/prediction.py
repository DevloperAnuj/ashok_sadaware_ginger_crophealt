import numpy as np
from PIL import Image

# Alphabetical class ordering produced by flow_from_directory:
# Bacterial_Wilt → 0,  Healthy → 1
CLASS_INDICES = {0: "Bacterial_Wilt", 1: "Healthy"}
IMG_SIZE = (224, 224)


def preprocess_image(image: Image.Image) -> "np.ndarray":
    image = image.convert("RGB")
    image = image.resize(IMG_SIZE)
    arr = np.array(image, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)  # shape: (1, 224, 224, 3)


def predict(model, image: Image.Image) -> tuple[str | None, float | None]:
    """
    Run inference using a TFLite Interpreter (ai-edge-litert).
    Returns (label, confidence) where confidence ∈ [0.5, 1.0].
    Returns (None, None) when model is unavailable.
    """
    if model is None:
        return None, None

    processed = preprocess_image(image)

    input_details  = model.get_input_details()
    output_details = model.get_output_details()

    model.set_tensor(input_details[0]["index"], processed)
    model.invoke()
    raw_prob = float(model.get_tensor(output_details[0]["index"])[0][0])  # P(Healthy)

    label      = CLASS_INDICES[1] if raw_prob > 0.5 else CLASS_INDICES[0]
    confidence = raw_prob if raw_prob > 0.5 else 1.0 - raw_prob
    return label, confidence
