import os
from pathlib import Path
from urllib.request import urlretrieve

import cv2
import mediapipe as mp
import numpy as np

# Try to force TensorFlow/Keras to use GPU (for emotionModel.hdf5 inference).
os.environ.setdefault("TF_FORCE_GPU_ALLOW_GROWTH", "true")
try:
    import tensorflow as tf

    gpus = tf.config.list_physical_devices("GPU")
    if gpus:
        # Enable memory growth so TF doesn't grab all VRAM at once.
        for gpu in gpus:
            try:
                tf.config.experimental.set_memory_growth(gpu, True)
            except Exception:
                pass
        # Optional: pin to the first GPU.
        tf.config.set_visible_devices(gpus[0], "GPU")
        print(f"[TF] Using GPU: {gpus[0].name}")
    else:
        print("[TF] No GPU detected, running on CPU")
except Exception:
    # If TensorFlow isn't available, fallback to whatever backend `keras` uses.
    tf = None

try:
    from keras.models import load_model
except Exception:
    from tensorflow.keras.models import load_model


RTSP_URL = "rtsp://192.168.1.168:8080/h264_ulaw.sdp"
WINDOW_NAME = "RTSP Emotion (Keras + MediaPipe)"
BASE_DIR = Path(__file__).resolve().parent

EMOTION_MODEL_CANDIDATES = [
    BASE_DIR / "emotionModel.hdf5",
    BASE_DIR / "models" / "emotionModel.hdf5",
]
MP_FACE_DETECTOR_MODEL_PATH = BASE_DIR / "blaze_face_short_range.tflite"
MP_FACE_DETECTOR_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
)
EMOTIONS = {
    0: {"name": "Angry", "color": (0, 0, 255)},  # must be red
    1: {"name": "Disgust", "color": (164, 175, 49)},
    2: {"name": "Fear", "color": (40, 52, 155)},
    3: {"name": "Happy", "color": (23, 164, 28)},
    4: {"name": "Sad", "color": (164, 93, 23)},
    5: {"name": "Surprise", "color": (218, 229, 97)},
    6: {"name": "Neutral", "color": (108, 72, 200)},
}


def pick_existing_path(candidates, entity_name):
    for path in candidates:
        if path.exists():
            return path
    checked = "\n - ".join(str(p) for p in candidates)
    raise FileNotFoundError(
        f"{entity_name} not found. Checked:\n - {checked}"
    )


def ensure_mp_face_detector_model():
    if MP_FACE_DETECTOR_MODEL_PATH.exists():
        return
    print(f"Downloading MediaPipe face detector: {MP_FACE_DETECTOR_MODEL_URL}")
    urlretrieve(MP_FACE_DETECTOR_MODEL_URL, MP_FACE_DETECTOR_MODEL_PATH)
    print(f"Saved MediaPipe model to: {MP_FACE_DETECTOR_MODEL_PATH}")


def make_mediapipe_face_detector():
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision

    options = mp_vision.FaceDetectorOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(MP_FACE_DETECTOR_MODEL_PATH)),
        running_mode=mp_vision.RunningMode.VIDEO,
        min_detection_confidence=0.5,
    )
    return mp_vision.FaceDetector.create_from_options(options)


def detect_faces_mediapipe(detector, frame_bgr, timestamp_ms):
    h, w = frame_bgr.shape[:2]
    boxes = []
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    result = detector.detect_for_video(mp_image, int(timestamp_ms))
    if not result.detections:
        return boxes
    for det in result.detections:
        bbox = det.bounding_box
        x, y, fw, fh = bbox.origin_x, bbox.origin_y, bbox.width, bbox.height
        x = int(max(0, x))
        y = int(max(0, y))
        fw = int(max(1, fw))
        fh = int(max(1, fh))
        x2 = min(w, x + fw)
        y2 = min(h, y + fh)
        boxes.append((x, y, max(1, x2 - x), max(1, y2 - y)))
    return boxes


def open_rtsp_stream(url):
    # Prefer TCP for RTSP transport when using FFMPEG backend.
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if cap.isOpened():
        return cap
    cap.release()

    # Fallback: let OpenCV choose backend automatically.
    cap = cv2.VideoCapture(url)
    if cap.isOpened():
        return cap
    cap.release()

    # Last fallback: append transport hint directly to URL.
    sep = "&" if "?" in url else "?"
    cap = cv2.VideoCapture(f"{url}{sep}rtsp_transport=tcp")
    if cap.isOpened():
        return cap
    cap.release()
    return None


def main():
    emotion_model_path = pick_existing_path(EMOTION_MODEL_CANDIDATES, "Emotion model")
    ensure_mp_face_detector_model()
    emotion_classifier = load_model(str(emotion_model_path), compile=False)
    emotion_target_size = emotion_classifier.input_shape[1:3]

    cap = open_rtsp_stream(RTSP_URL)
    if cap is None:
        print(f"Cannot open stream: {RTSP_URL}")
        return

    detector = make_mediapipe_face_detector()
    timestamp_ms = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Frame read failed, retrying...")
            if cv2.waitKey(100) & 0xFF == ord("q"):
                break
            continue

        frame = cv2.resize(frame, (960, 540))
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        timestamp_ms += 33
        faces = detect_faces_mediapipe(detector, frame, timestamp_ms)

        for (x, y, w, h) in faces:

            x = max(0, x)
            y = max(0, y)
            w = max(1, w)
            h = max(1, h)
            x2 = min(frame.shape[1], x + w)
            y2 = min(frame.shape[0], y + h)

            gray_face = gray_frame[y:y2, x:x2]
            if gray_face.size == 0:
                continue

            while True:
                try:
                    gray_face = cv2.resize(gray_face, emotion_target_size)
                    break
                except cv2.error:
                    gray_face = gray_face[:-1, :-1]
                    if gray_face.size == 0:
                        break
            if gray_face.size == 0:
                continue

            gray_face = gray_face.astype("float32")
            gray_face = gray_face / 255.0
            gray_face = (gray_face - 0.5) * 2.0
            gray_face = np.expand_dims(gray_face, 0)
            gray_face = np.expand_dims(gray_face, -1)

            emotion_prediction = emotion_classifier.predict(gray_face, verbose=0)
            emotion_probability = float(np.max(emotion_prediction))
            emotion_label = int(np.argmax(emotion_prediction))

            if emotion_probability > 0.36 and emotion_label in EMOTIONS:
                info = EMOTIONS[emotion_label]
                color = info["color"]
                label = info["name"]
                cv2.rectangle(frame, (x, y), (x2, y2), color, 2)
                cv2.putText(
                    frame,
                    f"{label} {emotion_probability:.2f}",
                    (x, max(20, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    color,
                    2,
                    cv2.LINE_AA,
                )
            else:
                cv2.rectangle(frame, (x, y), (x2, y2), (255, 255, 255), 2)
                cv2.putText(
                    frame,
                    "Low confidence",
                    (x, max(20, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2,
                    cv2.LINE_AA,
                )

        if len(faces) == 0:
            cv2.putText(
                frame,
                "No face detected",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )

        cv2.imshow(WINDOW_NAME, frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    detector.close()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
