import json
import logging
import time
from collections import deque
from typing import Any, Deque, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


class PoseViolenceDetector:
    """
    Real-time violence detection from YOLO pose keypoints + TorchScript classifier.

    Expected TorchScript input shape:
      (B=1, T=SEQUENCE_LENGTH, M*K=MAX_PERSONS*NUM_KEYPOINTS, C=3)
    where C is (x_norm, y_norm, kpt_conf).
    """

    EVENT_TYPE = "VIOLENCE_POSE_RISK"

    def __init__(
        self,
        pose_yolo_model: Any,
        violence_torchscript_path: str,
        device: str = "cpu",
        *,
        sequence_length: int = 30,
        max_persons: int = 2,
        num_keypoints: int = 17,
        pose_confidence_threshold: float = 0.3,
        violence_class_index: int = 1,
        violence_threshold: float = 0.7,
        inference_every_sec: float = 1.0,
        event_cooldown_sec: float = 10.0,
    ):
        self.pose_model = pose_yolo_model
        self.device = device

        import torch  # local import for faster boot / optional usage

        self.torch = torch
        self.violence_model = torch.jit.load(violence_torchscript_path, map_location=device)
        self.violence_model.eval()

        self.sequence_length = int(sequence_length)
        self.max_persons = int(max_persons)
        self.num_keypoints = int(num_keypoints)
        self.pose_confidence_threshold = float(pose_confidence_threshold)

        self.violence_class_index = int(violence_class_index)
        self.violence_threshold = float(violence_threshold)

        # throttle expensive inference
        self.inference_every_sec = float(inference_every_sec)
        self.event_cooldown_sec = float(event_cooldown_sec)

        self.pose_window: Deque[np.ndarray] = deque(maxlen=self.sequence_length)
        self.last_infer_ts = 0.0
        self.last_event_ts = 0.0

    @classmethod
    def from_config_files(
        cls,
        *,
        pose_yolo_model: Any,
        violence_torchscript_path: str,
        pose_config_path: Optional[str],
        device: str,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Optional["PoseViolenceDetector"]:
        if not violence_torchscript_path:
            return None
        if overrides is None:
            overrides = {}

        # Use exported notebook config if it exists.
        cfg = {}
        if pose_config_path:
            try:
                with open(pose_config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f) or {}
            except Exception as e:
                logger.warning(f"Failed to load pose_config.json: {e}")

        return cls(
            pose_yolo_model=pose_yolo_model,
            violence_torchscript_path=violence_torchscript_path,
            device=device,
            sequence_length=int(overrides.get("sequence_length", cfg.get("SEQUENCE_LENGTH", 30))),
            max_persons=int(overrides.get("max_persons", cfg.get("MAX_PERSONS", 2))),
            num_keypoints=int(overrides.get("num_keypoints", cfg.get("NUM_KEYPOINTS", 17))),
            pose_confidence_threshold=float(
                overrides.get("pose_confidence_threshold", cfg.get("POSE_CONFIDENCE_THRESHOLD", 0.3))
            ),
            violence_class_index=int(overrides.get("violence_class_index", cfg.get("VIOLENCE_CLASS_INDEX", 1))),
            violence_threshold=float(overrides.get("violence_threshold", 0.7)),
            inference_every_sec=float(overrides.get("inference_every_sec", 1.0)),
            event_cooldown_sec=float(overrides.get("event_cooldown_sec", 10.0)),
        )

    def _extract_pose_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Returns (MAX_PERSONS, NUM_KEYPOINTS, 3) array:
          x_norm, y_norm, keypoint_conf
        """
        height, width = frame.shape[:2]
        out = np.zeros((self.max_persons, self.num_keypoints, 3), dtype=np.float32)

        if self.pose_model is None:
            return out

        # ultralytics YOLO-pose inference
        results = self.pose_model(frame, verbose=False, conf=self.pose_confidence_threshold, device=self.device)
        if not results:
            return out

        r0 = results[0]
        if r0.keypoints is None or r0.keypoints.data is None:
            return out

        # keypoints: (N, 17, 3) where last channel is (x, y, conf)
        kpts = r0.keypoints.data.cpu().numpy().astype(np.float32)

        # boxes used to keep a stable ordering of persons in the tensor
        boxes = None
        try:
            if r0.boxes is not None and r0.boxes.xyxy is not None:
                boxes = r0.boxes.xyxy.cpu().numpy().astype(np.float32)
        except Exception:
            boxes = None

        if boxes is not None and len(boxes) == len(kpts):
            centers_x = (boxes[:, 0] + boxes[:, 2]) / 2.0
        else:
            # fallback: order by average x of keypoints
            centers_x = kpts[:, :, 0].mean(axis=1) if kpts.size else np.array([])

        if centers_x.size == 0:
            return out

        order = np.argsort(centers_x)  # left -> right
        for i, person_idx in enumerate(order[: self.max_persons]):
            person_kpts = kpts[person_idx]  # (K, 3)
            # normalize to [0, 1]
            person_kpts[:, 0] = person_kpts[:, 0] / max(1.0, float(width))
            person_kpts[:, 1] = person_kpts[:, 1] / max(1.0, float(height))

            confs = person_kpts[:, 2]
            keep = confs >= self.pose_confidence_threshold

            person_kpts[:, 2] = np.where(keep, confs, 0.0)
            person_kpts[:, 0] = np.where(keep, person_kpts[:, 0], 0.0)
            person_kpts[:, 1] = np.where(keep, person_kpts[:, 1], 0.0)

            out[i] = person_kpts

        return out

    def update(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Push current frame keypoints into the window and run classification when ready.
        Returns an event dict compatible with risk-engine / EventData.events.
        """
        pose_frame = self._extract_pose_frame(frame)
        self.pose_window.append(pose_frame)

        if len(self.pose_window) < self.sequence_length:
            return None

        now = time.time()
        if (now - self.last_infer_ts) < self.inference_every_sec:
            return None

        # Build input tensor (B=1, T, M*K, 3)
        pose_seq = np.stack(self.pose_window, axis=0).astype(np.float32)  # (T, M, K, 3)
        pose_seq = pose_seq.reshape(self.sequence_length, self.max_persons * self.num_keypoints, 3)
        pose_seq = pose_seq.reshape(1, self.sequence_length, self.max_persons * self.num_keypoints, 3)

        input_tensor = self.torch.from_numpy(pose_seq).to(self.device)

        with self.torch.no_grad():
            logits = self.violence_model(input_tensor)

        # logits -> probability
        probs = self.torch.softmax(logits, dim=1).detach().cpu().numpy()[0]
        if self.violence_class_index >= len(probs):
            violence_prob = float(probs[-1]) if len(probs) else 0.0
        else:
            violence_prob = float(probs[self.violence_class_index])

        self.last_infer_ts = now

        if violence_prob < self.violence_threshold:
            return None

        if (now - self.last_event_ts) < self.event_cooldown_sec:
            return None

        self.last_event_ts = now
        return {
            "type": self.EVENT_TYPE,
            "confidence": violence_prob,
            "track_ids": [],
            "meta_data": {
                "violence_probability": violence_prob,
                "sequence_length": self.sequence_length,
            },
        }

