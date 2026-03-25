import cv2
from ultralytics import YOLO

RTSP_URL = "rtsp://192.168.1.168:8080/h264_ulaw.sdp"
MODEL_PATH = "best-weapon.pt"

def main():
    model = YOLO(MODEL_PATH)

    cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        raise RuntimeError(f"Не удалось открыть RTSP: {RTSP_URL}")

    win = "best-weapon (Q to quit)"
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        results = model.predict(frame, conf=0.25, verbose=False)[0]

        if results.boxes is not None and len(results.boxes) > 0:
            names = results.names  # id -> class name
            for b in results.boxes:
                x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())
                conf = float(b.conf[0])
                cls_id = int(b.cls[0]) if b.cls is not None else -1
                label = names.get(cls_id, str(cls_id))

                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
                cv2.putText(
                    frame,
                    f"{label} {conf:.2f}",
                    (x1, max(0, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 220, 0),
                    2,
                    cv2.LINE_AA,
                )

        cv2.imshow(win, frame)
        if (cv2.waitKey(1) & 0xFF) == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()