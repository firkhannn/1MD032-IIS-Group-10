import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torchvision import transforms, models
from typing import Dict, Any, Optional
import time
import threading
from flask import Flask, jsonify
from collections import deque

# =========================
# 1) Load your trained ResNet50 model
# =========================

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

model = models.resnet50()
num_features = model.fc.in_features
model.fc = torch.nn.Linear(num_features, 7)

checkpoint = torch.load("emotion_cnn_resnet50_best.pth", map_location=device)
model.load_state_dict(checkpoint)
model = model.to(device)
model.eval()

CLASSES = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']

transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225])
])

print(f"[emotion_server] Model loaded on {device}")
print(f"[emotion_server] Emotion classes: {CLASSES}")

# =========================
# 2) Face detection (Haar cascade)
# =========================

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)

# =========================
# 3) Emotion prediction
# =========================

def detect_face(frame_bgr: np.ndarray) -> Optional[np.ndarray]:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(100, 100)
    )

    if len(faces) == 0:
        return None

    x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
    padding = int(0.2 * w)

    x = max(0, x - padding)
    y = max(0, y - padding)
    w = min(frame_bgr.shape[1] - x, w + 2 * padding)
    h = min(frame_bgr.shape[0] - y, h + 2 * padding)

    return frame_bgr[y:y + h, x:x + w]

def predict_emotion_from_frame(frame_bgr: np.ndarray) -> Dict[str, Any]:
    face = detect_face(frame_bgr)

    if face is None:
        return {"emotion": "neutral", "confidence": 0.0}

    frame_rgb = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
    input_tensor = transform(frame_rgb).unsqueeze(0).to(device)

    with torch.no_grad():
        logits = model(input_tensor)
        probs = F.softmax(logits, dim=1)[0].cpu().numpy()

    pred_idx = int(np.argmax(probs))
    conf = float(np.max(probs))
    pred_label = CLASSES[pred_idx]

    return {"emotion": pred_label, "confidence": conf}

# =========================
# 4) Rolling 5-second window
# =========================

emotion_window = deque(maxlen=5)

# =========================
# 5) Webcam loop + LIVE PREVIEW
# =========================

latest: Dict[str, Any] = {
    "emotion": "neutral",
    "confidence": 0.0,
    "timestamp": time.time()
}

stop_event = threading.Event()

def webcam_loop(cam_index: int = 0):
    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print("[emotion_server] ERROR: Cannot open webcam.")
        return

    print("[emotion_server] Webcam started. Press ESC to stop.")
    last_sample_time = time.time()

    try:
        while not stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05)
                continue

            out = predict_emotion_from_frame(frame)
            now = time.time()

            # update latest
            latest["emotion"] = out["emotion"]
            latest["confidence"] = out["confidence"]
            latest["timestamp"] = now

            # ---- sample once per second ----
            if now - last_sample_time >= 1.0:
                emotion_window.append({
                    "timestamp": now,
                    "emotion": out["emotion"],
                    "confidence": out["confidence"]
                })
                last_sample_time = now

            # ---- overlay ----
            cv2.putText(frame, f"Emotion: {latest['emotion']}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            cv2.putText(frame, f"Conf: {latest['confidence']:.2f}", (10, 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

            last5 = [e["emotion"] for e in emotion_window]
            cv2.putText(frame, f"Last 5s: {last5}", (10, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            cv2.imshow("Emotion Webcam", frame)

            if (cv2.waitKey(1) & 0xFF) == 27:
                stop_event.set()
                break

            time.sleep(0.01)

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[emotion_server] Webcam stopped.")

# =========================
# 6) Flask API
# =========================

app = Flask(__name__)

@app.get("/emotion_json")
def get_emotion_json():
    return jsonify(latest)

@app.get("/emotion")
def get_emotion_window():
    return jsonify({
        "window_size": len(emotion_window),
        "data": list(emotion_window)
    })

@app.get("/window")
def get_window():
    return jsonify(list(emotion_window))

# =========================
# 7) Main
# =========================

if __name__ == "__main__":
    t = threading.Thread(target=webcam_loop, daemon=True)
    t.start()

    print("[emotion_server] Running at http://127.0.0.1:5000/emotion")
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
