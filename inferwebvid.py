"""
Fight Detection – Real-time webcam inference
Tested on MacBook M2 (Apple Silicon)

Install:
    pip install torch torchvision ultralytics opencv-python numpy

Usage:
    python inferwebvid.py --model C:\Users\User\Documents\Yeldar\school-risk-main\ckpt_epoch60.pth
    python inferwebvid.py --model /Users/yeldar/Desktop/cameras/XDVioDet-master/fight_detector.pt  # TorchScript
"""

import argparse
import collections
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn

# ── Device (MPS on M2, fallback to CPU) ─────────────────────────────────────
DEVICE = (
    torch.device("mps")
    if torch.backends.mps.is_available()
    else torch.device("cpu")
)
print(f"Device: {DEVICE}")

# ── Default config (must match training) ────────────────────────────────────
DEFAULT_CONFIG = {
    "SEQUENCE_LENGTH": 30,
    "FPS_SAMPLE": 3,          # how many frames/sec to sample from webcam
    "MAX_PERSONS": 2,
    "NUM_KEYPOINTS": 17,
    "KEYPOINT_DIM": 4,        # x, y, conf, velocity
    "POSE_CONFIDENCE_THRESHOLD": 0.3,
    "GCN_HIDDEN_DIM": 128,
    "LSTM_HIDDEN_DIM": 256,
    "LSTM_LAYERS": 2,
    "NUM_CLASSES": 2,
    "DROPOUT": 0.4,
    "VIOLENCE_THRESHOLD": 0.60,   # probability threshold to trigger alert
    "SMOOTH_WINDOW": 5,           # temporal smoothing (frames)
}

COCO_SKELETON = [
    [0,1],[0,2],[1,3],[2,4],[0,5],[0,6],[5,6],
    [5,7],[7,9],[6,8],[8,10],[5,11],[6,12],
    [11,12],[11,13],[13,15],[12,14],[14,16],
]

# ── Colours ─────────────────────────────────────────────────────────────────
C_GREEN  = (0, 220, 0)
C_RED    = (0, 0, 230)
C_YELLOW = (0, 200, 220)
C_WHITE  = (255, 255, 255)
C_DARK   = (30, 30, 30)


# ════════════════════════════════════════════════════════════════════════════
# Model definition (must match training)
# ════════════════════════════════════════════════════════════════════════════

class GraphConv(nn.Module):
    def __init__(self, in_f, out_f):
        super().__init__()
        self.W = nn.Parameter(torch.FloatTensor(in_f, out_f))
        self.b = nn.Parameter(torch.FloatTensor(out_f))
        nn.init.xavier_uniform_(self.W)
        nn.init.zeros_(self.b)

    def forward(self, x, adj):
        return torch.matmul(adj, torch.matmul(x, self.W)) + self.b


class STGCN(nn.Module):
    def __init__(self, in_channels, hidden_dim, n_kpts, max_persons):
        super().__init__()
        self.n_kpts = n_kpts
        self.M      = max_persons
        self.gc1 = GraphConv(in_channels, hidden_dim)
        self.gc2 = GraphConv(hidden_dim,  hidden_dim)
        self.gc3 = GraphConv(hidden_dim,  hidden_dim)
        self.ln  = nn.LayerNorm(hidden_dim)
        self.act = nn.GELU()
        self.drop = nn.Dropout(0.2)

    def forward(self, x, adj):
        B, T, N, C = x.shape
        outs = []
        for m in range(self.M):
            px = x[:, :, m*self.n_kpts:(m+1)*self.n_kpts, :]
            px = px.reshape(B*T, self.n_kpts, C)
            h = self.act(self.gc1(px, adj))
            h = self.drop(h)
            h = self.act(self.gc2(h, adj))
            h = self.drop(h)
            h = self.ln(self.gc3(h, adj))
            h = h.reshape(B, T, self.n_kpts, -1)
            outs.append(h)
        return torch.cat(outs, dim=2)


class FightDetector(nn.Module):
    def __init__(self, cfg, adj):
        super().__init__()
        self.register_buffer("adj", adj)
        K, M  = cfg["NUM_KEYPOINTS"], cfg["MAX_PERSONS"]
        GH    = cfg["GCN_HIDDEN_DIM"]
        LH    = cfg["LSTM_HIDDEN_DIM"]
        LL    = cfg["LSTM_LAYERS"]
        NC    = cfg["NUM_CLASSES"]
        D     = cfg["DROPOUT"]
        KD    = cfg["KEYPOINT_DIM"]

        self.stgcn = STGCN(KD, GH, K, M)
        self.lstm  = nn.LSTM(GH*K*M, LH, LL,
                             batch_first=True, bidirectional=True,
                             dropout=D if LL > 1 else 0)
        self.attn  = nn.Linear(LH*2, 1)
        self.fc    = nn.Sequential(
            nn.Linear(LH*2, LH), nn.GELU(), nn.Dropout(D), nn.Linear(LH, NC)
        )

    def forward(self, x):
        B, T, N, _ = x.shape
        h = self.stgcn(x, self.adj).reshape(B, T, -1)
        out, _ = self.lstm(h)
        a   = torch.softmax(self.attn(out), dim=1)
        ctx = (a * out).sum(dim=1)
        return self.fc(ctx)


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════

def get_adj(n=17):
    adj = np.zeros((n, n))
    for e in COCO_SKELETON:
        adj[e[0], e[1]] = adj[e[1], e[0]] = 1
    adj += np.eye(n)
    d = np.sum(adj, 1)
    di = np.power(d, -0.5); di[np.isinf(di)] = 0
    return torch.FloatTensor(np.diag(di) @ adj @ np.diag(di))


def load_model(model_path, cfg):
    """Load TorchScript (.pt) or regular checkpoint (.pth)."""
    p = Path(model_path)
    if p.suffix == ".pt":
        model = torch.jit.load(model_path, map_location=DEVICE)
        print("Loaded TorchScript model.")
    else:
        adj   = get_adj(cfg["NUM_KEYPOINTS"]).to(DEVICE)
        model = FightDetector(cfg, adj).to(DEVICE)
        ckpt  = torch.load(model_path, map_location=DEVICE)
        model.load_state_dict(ckpt["model_state_dict"])
        print(f"Loaded checkpoint (epoch {ckpt.get('epoch','?')}, "
              f"val_acc={ckpt.get('val_acc',0):.4f})")
    model.eval()
    return model


def extract_kpts_yolo(frame, yolo_model, cfg):
    """Extract keypoints only (bbox output discarded)."""
    M, K = cfg["MAX_PERSONS"], cfg["NUM_KEYPOINTS"]
    out  = np.zeros((M, K, 3), dtype=np.float32)
    res  = yolo_model(frame, verbose=False)
    if res[0].keypoints is None or len(res[0].keypoints) == 0:
        return out
    kpts = res[0].keypoints.data.cpu().numpy()
    h, w = frame.shape[:2]
    for i in range(min(len(kpts), M)):
        k = kpts[i].copy()
        k[:, 0] /= w
        k[:, 1] /= h
        out[i] = k
    return out


def draw_skeleton(frame, kpts_norm, color):
    """Draw one person's skeleton on frame."""
    h, w = frame.shape[:2]
    pts  = [(int(kpts_norm[j, 0]*w), int(kpts_norm[j, 1]*h)) for j in range(17)]
    for a, b in COCO_SKELETON:
        if kpts_norm[a, 2] > 0.2 and kpts_norm[b, 2] > 0.2:
            cv2.line(frame, pts[a], pts[b], color, 2)
    for j, (x, y) in enumerate(pts):
        if kpts_norm[j, 2] > 0.2:
            cv2.circle(frame, (x, y), 4, color, -1)


def draw_hud(frame, prob, label, fps, seq_fill):
    """Overlay HUD: probability bar, label, FPS."""
    h, w = frame.shape[:2]

    # Semi-transparent top bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 70), C_DARK, -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    # Probability bar
    bar_w = int((w - 40) * prob)
    bar_color = C_RED if label == "FIGHT" else C_GREEN
    cv2.rectangle(frame, (20, 45), (w-20, 62), (80, 80, 80), -1)
    cv2.rectangle(frame, (20, 45), (20+bar_w, 62), bar_color, -1)

    # Label
    text_color = C_RED if label == "FIGHT" else C_GREEN
    cv2.putText(frame, f"{label}  {prob:.0%}", (20, 36),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, text_color, 2)

    # FPS + buffer fill
    cv2.putText(frame, f"FPS:{fps:.0f}  buf:{seq_fill}",
                (w-200, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, C_WHITE, 1)

    # Alert flash border
    if label == "FIGHT":
        cv2.rectangle(frame, (0, 0), (w-1, h-1), C_RED, 6)


# ════════════════════════════════════════════════════════════════════════════
# Main inference loop
# ════════════════════════════════════════════════════════════════════════════

def run(args):
    cfg = DEFAULT_CONFIG.copy()

    # Optionally load config.json saved during training
    if args.config and Path(args.config).exists():
        with open(args.config) as f:
            saved = json.load(f)
        for k in ["SEQUENCE_LENGTH","FPS_SAMPLE","MAX_PERSONS","NUM_KEYPOINTS",
                  "GCN_HIDDEN_DIM","LSTM_HIDDEN_DIM","LSTM_LAYERS","DROPOUT"]:
            if k in saved:
                cfg[k] = int(saved[k]) if saved[k].isdigit() else float(saved[k])
        print("Loaded config.json")

    if args.threshold:
        cfg["VIOLENCE_THRESHOLD"] = args.threshold

    # Load pose model (YOLOv8m-pose)
    from ultralytics import YOLO
    yolo = YOLO("yolov8m-pose.pt")  # downloads on first run (~50 MB)

    # Load fight detector
    fight_model = load_model(args.model, cfg)

    # Webcam
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {args.camera}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    T    = cfg["SEQUENCE_LENGTH"]
    M, K = cfg["MAX_PERSONS"], cfg["NUM_KEYPOINTS"]
    fps_target = cfg["FPS_SAMPLE"]

    # Rolling buffers
    pose_buf   = collections.deque(maxlen=T)   # raw (M, K, 3) frames
    smooth_buf = collections.deque(maxlen=cfg["SMOOTH_WINDOW"])

    # Sampling timer
    sample_interval = 1.0 / fps_target
    last_sample_t   = time.time()

    prob  = 0.0
    label = "Collecting..."
    fps_disp = 0.0
    t_prev   = time.time()

    print("\n[SPACE] pause   [Q] quit\n")

    paused = False
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # FPS counter
        now = time.time()
        fps_disp = 0.9*fps_disp + 0.1*(1.0/(now - t_prev + 1e-6))
        t_prev = now

        if paused:
            cv2.putText(frame, "PAUSED", (20, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 2, C_YELLOW, 3)
            cv2.imshow("Fight Detector", frame)
            key = cv2.waitKey(30) & 0xFF
            if key == ord('q'): break
            if key == ord(' '): paused = False
            continue

        # ── Sample frame at target fps ────────────────────────────────────
        if (now - last_sample_t) >= sample_interval:
            last_sample_t = now
            kpts = extract_kpts_yolo(frame, yolo, cfg)  # (M, K, 3)
            pose_buf.append(kpts)

            # Draw skeletons
            colors = [C_GREEN, C_YELLOW]
            for m in range(M):
                if kpts[m, :, 2].max() > cfg["POSE_CONFIDENCE_THRESHOLD"]:
                    draw_skeleton(frame, kpts[m], colors[m])

        # ── Run classifier when buffer is full ────────────────────────────
        if len(pose_buf) == T:
            seq = np.array(pose_buf, dtype=np.float32)  # (T, M, K, 3)

            # Velocity channel
            vel = np.zeros((T, M, K, 1), dtype=np.float32)
            for t in range(1, T):
                dx = seq[t,:,:,0] - seq[t-1,:,:,0]
                dy = seq[t,:,:,1] - seq[t-1,:,:,1]
                vel[t,:,:,0] = np.sqrt(dx**2 + dy**2)
            seq4 = np.concatenate([seq, vel], axis=-1)  # (T, M, K, 4)

            x = torch.FloatTensor(seq4).reshape(1, T, M*K, 4).to(DEVICE)
            with torch.no_grad():
                logits = fight_model(x)
                probs  = torch.softmax(logits, dim=1)[0].cpu().numpy()
            raw_prob = float(probs[1])

            # Temporal smoothing
            smooth_buf.append(raw_prob)
            prob  = float(np.mean(smooth_buf))
            label = "FIGHT" if prob >= cfg["VIOLENCE_THRESHOLD"] else "Normal"

        # ── HUD ──────────────────────────────────────────────────────────
        draw_hud(frame, prob, label, fps_disp, len(pose_buf))
        cv2.imshow("Fight Detector", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'): break
        if key == ord(' '): paused = True

    cap.release()
    cv2.destroyAllWindows()


# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fight detector – webcam inference")
    parser.add_argument("--model",     required=True,
                        help="Path to best_model.pth or fight_detector.pt")
    parser.add_argument("--config",    default=None,
                        help="Path to config.json (optional)")
    parser.add_argument("--camera",    type=int, default=0,
                        help="Camera index (default 0 = built-in webcam)")
    parser.add_argument("--threshold", type=float, default=None,
                        help="Violence probability threshold (default 0.60)")
    args = parser.parse_args()
    run(args)