"""
Real-time leaf disease detection via webcam (WebRTC).
"""

import threading

import streamlit as st
from PIL import Image

from model_loader import load_model
from prediction import predict

# ── WebRTC availability check (done once at import time) ──────────────────────
_WEBRTC_ERROR: str = ""
try:
    import av
    import cv2
    from streamlit_webrtc import (
        RTCConfiguration,
        VideoProcessorBase,
        WebRtcMode,
        webrtc_streamer,
    )
    _WEBRTC_OK = True
except Exception as _e:
    _WEBRTC_OK = False
    _WEBRTC_ERROR = f"{type(_e).__name__}: {_e}"

_STUN = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
) if _WEBRTC_OK else None


# ── Video processor (runs in background thread inside streamlit-webrtc) ───────
if _WEBRTC_OK:
    class LeafVideoProcessor(VideoProcessorBase):
        """Runs MobileNetV2 every N frames and overlays the result on the stream."""

        _PREDICT_EVERY = 12  # frames between inference calls

        def __init__(self):
            self._model = load_model()
            self._lock = threading.Lock()
            self._label: str = ""
            self._confidence: float = 0.0
            self._frame_n: int = 0

        def recv(self, frame: "av.VideoFrame") -> "av.VideoFrame":
            img_bgr = frame.to_ndarray(format="bgr24")
            self._frame_n += 1

            if self._frame_n % self._PREDICT_EVERY == 0 and self._model is not None:
                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                label, conf = predict(self._model, Image.fromarray(img_rgb))
                with self._lock:
                    self._label = label or ""
                    self._confidence = conf or 0.0

            with self._lock:
                label, confidence = self._label, self._confidence

            if label:
                _draw_overlay(img_bgr, label, confidence)

            return av.VideoFrame.from_ndarray(img_bgr, format="bgr24")

        def current_result(self) -> tuple[str, float]:
            with self._lock:
                return self._label, self._confidence


def _draw_overlay(img_bgr, label: str, confidence: float) -> None:
    is_healthy = label == "Healthy"
    color = (50, 200, 50) if is_healthy else (30, 30, 220)
    text = f"{label}  {confidence * 100:.1f}%"
    font, scale, thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.85, 2
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    pad = 8
    cv2.rectangle(img_bgr, (0, 0), (tw + pad * 2, th + baseline + pad * 2), (0, 0, 0), -1)
    cv2.putText(img_bgr, text, (pad, th + pad), font, scale, color, thickness, cv2.LINE_AA)


# ── Public render function called from app.py ─────────────────────────────────
def render_live_detection_page() -> None:
    st.title("Live Camera — Leaf Disease Detection")

    if not _WEBRTC_OK:
        st.warning(
            "Real-time video packages are not installed or failed to load. Run:\n"
            "```\npip install streamlit-webrtc av opencv-python-headless\n```"
        )
        if _WEBRTC_ERROR:
            st.error(f"Import error detail: `{_WEBRTC_ERROR}`")
        return

    model = load_model()
    if model is None:
        st.info(
            "No model loaded — place `ginger_disease_model.tflite` in `streamlit_app/models/` "
            "to enable AI inference on the video stream. "
            "The camera preview will still open.",
            icon="ℹ️",
        )

    st.markdown(
        "Point your camera at a **ginger leaf**. "
        "The AI label updates approximately every 12 frames (~0.5 s at 24 fps)."
    )

    ctx = webrtc_streamer(
        key="leaf-live",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=_STUN,
        video_processor_factory=LeafVideoProcessor,
        media_stream_constraints={"video": True, "audio": False},
        async_processing=True,
    )

    if ctx.video_processor:
        label, confidence = ctx.video_processor.current_result()
        if label:
            _show_result_banner(label, confidence)
        else:
            st.caption("Waiting for first prediction…")


def _show_result_banner(label: str, confidence: float) -> None:
    if confidence < 0.60:
        st.warning(
            f"**Low Confidence — {label}** ({confidence * 100:.1f} %)\n\n"
            "The model is uncertain. Retake the photo in better lighting "
            "or closer to the leaf."
        )
    elif label == "Bacterial_Wilt":
        st.error(f"**Disease Detected: Bacterial Wilt** — {confidence * 100:.1f} % confidence")
        st.markdown("""
**Recommended Actions:**
- Apply copper-based bactericide immediately.
- Isolate and remove heavily infected rhizomes.
- Improve field drainage; avoid waterlogging.
- Avoid overhead irrigation to reduce leaf wetness.
""")
    else:
        st.success(f"**Healthy Plant** — {confidence * 100:.1f} % confidence")
        st.markdown("Continue regular monitoring and maintain optimal soil conditions.")
