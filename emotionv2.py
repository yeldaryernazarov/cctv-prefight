"""
Emotion Detector — RTSP stream (Pure PyTorch)
Face detection: MTCNN (facenet-pytorch)
Emotion model:  ViT fine-tuned on AffectNet (HuggingFace)

Install:
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
    pip install facenet-pytorch transformers opencv-python pillow

Usage:
    python emotion_detector.py
    python emotion_detector.py --source rtsp://192.168.1.168:8080/h264_ulaw.sdp
    python emotion_detector.py --source 0   # webcam fallback
"""

import cv2
import time
import argparse
import threading
import numpy as np
from collections import deque
from PIL import Image

import torch
from facenet_pytorch import MTCNN
from transformers import AutoImageProcessor, AutoModelForImageClassification
# ── Config ────────────────────────────────────────────────────────────────────
RTSP_URL        = "rtsp://192.168.1.168:8080/h264_ulaw.sdp"
ANALYZE_EVERY   = 3          # analyze every N frames
SMOOTH_K        = 5          # rolling average over last K detections
ANGER_THRESHOLD = 0.35       # smoothed anger score threshold
FONT            = cv2.FONT_HERSHEY_SIMPLEX

# emotions from the model that map to ANGER
ANGER_LABELS    = {"angry", "anger", "disgust", "contempt"}

# HuggingFace model — ViT trained on AffectNet (7 classes)
MODEL_NAME      = "trpakov/vit-face-expression"
# ──────────────────────────────────────────────────────────────────────────────


def setup_device():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        print(f"[INFO] GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("[WARN] GPU not found, running on CPU")
    return device


def load_models(device):
    print("[INFO] Loading MTCNN face detector...")
    mtcnn = MTCNN(
        keep_all=True,
        device=device,
        min_face_size=60,
        thresholds=[0.6, 0.7, 0.7],
        post_process=False,
    )

    print(f"[INFO] Loading emotion model: {MODEL_NAME} ...")
    extractor = AutoImageProcessor.from_pretrained(MODEL_NAME)
    model     = AutoModelForImageClassification.from_pretrained(MODEL_NAME)
    model.to(device).eval()
    print(f"[INFO] Model labels: {list(model.config.id2label.values())}")
    return mtcnn, extractor, model


def predict_emotion(face_crop_rgb, extractor, model, device):
    """Run emotion inference on a single face crop (numpy RGB)."""
    pil_img = Image.fromarray(face_crop_rgb)
    inputs  = extractor(images=pil_img, return_tensors="pt")
    inputs  = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        logits = model(**inputs).logits
        probs  = torch.softmax(logits, dim=-1)[0].cpu().numpy()

    id2label = model.config.id2label
    emotions = {id2label[i].lower(): float(probs[i]) for i in range(len(probs))}
    dominant = max(emotions, key=emotions.get)
    return emotions, dominant


def anger_score(emotions: dict) -> float:
    return sum(v for k, v in emotions.items() if k in ANGER_LABELS)


def draw_face(frame, x1, y1, x2, y2, dominant, angry: bool, score: float):
    color  = (0, 0, 220) if angry else (50, 200, 50)
    border = 3 if angry else 2
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, border)

    text = f"ANGER  {score*100:.0f}%" if angry else "NEUTRAL"
    (tw, th), _ = cv2.getTextSize(text, FONT, 0.7, 2)
    pad = 6
    cv2.rectangle(frame,
                  (x1, y1 - th - pad * 2),
                  (x1 + tw + pad * 2, y1),
                  color, -1)
    cv2.putText(frame, text, (x1 + pad, y1 - pad),
                FONT, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

    # anger bar under the box
    w     = x2 - x1
    bar_w = int(w * min(score, 1.0))
    cv2.rectangle(frame, (x1, y2 + 2), (x2, y2 + 10), (60, 60, 60), -1)
    cv2.rectangle(frame, (x1, y2 + 2), (x1 + bar_w, y2 + 10), (0, 0, 220), -1)
    cv2.putText(frame, "anger", (x1, y2 + 22),
                FONT, 0.4, (200, 200, 200), 1, cv2.LINE_AA)


class FrameReader(threading.Thread):
    def __init__(self, source):
        super().__init__(daemon=True)
        self.cap  = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open source: {source}")
        self.ret   = False
        self.frame = None
        self.lock  = threading.Lock()

    def run(self):
        while True:
            ret, frame = self.cap.read()
            with self.lock:
                self.ret, self.frame = ret, frame

    def read(self):
        with self.lock:
            return self.ret, (self.frame.copy() if self.frame is not None else None)


def main(source):
    device = setup_device()
    mtcnn, extractor, model = load_models(device)

    print(f"[INFO] Connecting to: {source}")
    reader = FrameReader(source)
    reader.start()
    time.sleep(1.0)

    frame_idx  = 0
    last_faces = []   # list of (x1,y1,x2,y2, dominant, angry, score)
    anger_hist = deque(maxlen=SMOOTH_K)

    cv2.namedWindow("Emotion Detector", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Emotion Detector", 960, 540)
    print("[INFO] Running. Press Q to quit.")

    while True:
        ret, frame = reader.read()
        if not ret or frame is None:
            time.sleep(0.05)
            continue

        frame_idx += 1
        overlay = frame.copy()

        if frame_idx % ANALYZE_EVERY == 0:
            rgb          = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            boxes, _     = mtcnn.detect(rgb)
            last_faces   = []

            if boxes is not None:
                for box in boxes:
                    x1, y1, x2, y2 = [int(v) for v in box]
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
                    if x2 <= x1 or y2 <= y1:
                        continue

                    face_crop = rgb[y1:y2, x1:x2]
                    try:
                        emotions, dominant = predict_emotion(
                            face_crop, extractor, model, device
                        )
                        score = anger_score(emotions)
                        anger_hist.append(score)
                        smoothed = float(np.mean(anger_hist))
                        angry    = smoothed >= ANGER_THRESHOLD
                        last_faces.append((x1, y1, x2, y2, dominant, angry, smoothed))
                    except Exception as e:
                        print(f"[WARN] Inference failed: {e}")

        for (x1, y1, x2, y2, dominant, angry, score) in last_faces:
            draw_face(overlay, x1, y1, x2, y2, dominant, angry, score)

        if not last_faces:
            cv2.putText(overlay, "No face detected",
                        (10, 50), FONT, 0.7, (100, 100, 255), 2, cv2.LINE_AA)

        gpu_label = (f"GPU: {torch.cuda.get_device_name(0)}"
                     if device.type == "cuda" else "CPU mode")
        cv2.putText(overlay, gpu_label,
                    (10, 24), FONT, 0.5, (180, 180, 180), 1, cv2.LINE_AA)

        cv2.imshow("Emotion Detector", overlay)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()
    reader.cap.release()
    print("[INFO] Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=RTSP_URL,
                        help="RTSP URL or webcam index (0, 1, ...)")
    args = parser.parse_args()
    src = args.source
    try:
        src = int(src)
    except ValueError:
        pass
    main(src)