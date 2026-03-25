import cv2

# Configure TensorFlow to use GPU (if available) before DeepFace initializes.
try:
    import tensorflow as tf

    gpus = tf.config.list_physical_devices("GPU")
    if gpus:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
except Exception:
    # If TensorFlow/GPU isn't available, DeepFace will fall back to CPU.
    pass

from deepface import DeepFace

# Ensure TensorFlow is the backend (GPU-capable) when available.
try:
    DeepFace.set_backend("tensorflow")
except Exception:
    pass

# Load face cascade classifier
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# RTSP stream URL
RTSP_URL = "rtsp://192.168.1.168:8080/h264_ulaw.sdp"

# Start capturing video from RTSP
# Note: OpenCV needs an FFmpeg-enabled build to read RTSP reliably.
cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)

# Reduce buffering to keep latency lower (if the backend supports it).
try:
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
except Exception:
    pass

while True:
    # Capture frame-by-frame
    ret, frame = cap.read()
    if not ret:
        # Stream may temporarily fail; avoid hard-crashing and try again.
        continue

    # Convert frame to grayscale
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Convert grayscale frame to RGB format
    rgb_frame = cv2.cvtColor(gray_frame, cv2.COLOR_GRAY2RGB)

    # Detect faces in the frame
    faces = face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

    for (x, y, w, h) in faces:
        # Extract the face ROI (Region of Interest)
        face_roi = rgb_frame[y:y + h, x:x + w]

        
        # Perform emotion analysis on the face ROI
        # DeepFace will use GPU automatically when TensorFlow sees a GPU.
        result = DeepFace.analyze(
            face_roi,
            actions=["emotion"],
            enforce_detection=False,
            detector_backend="opencv",
            prog_bar=False,
        )

        # Determine the dominant emotion
        emotion = result[0]['dominant_emotion']

        # Draw rectangle around face and label with predicted emotion
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
        cv2.putText(frame, emotion, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

    # Display the resulting frame
    cv2.imshow('Real-time Emotion Detection', frame)

    # Press 'q' to exit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release the capture and close all windows
cap.release()
cv2.destroyAllWindows()

