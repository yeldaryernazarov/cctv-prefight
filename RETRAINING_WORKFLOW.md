# Retraining Workflow (Human-in-the-Loop)

This project now supports a feedback loop based on guard decisions on alerts.

## What is implemented

- Labeled dataset export from `alerts` + `alert_decisions`.
- Automatic threshold recomputation for event confidence.
- Threshold overrides that are automatically applied by `analytics_service`.

## API endpoints

- `POST /api/retraining/dataset/export`
  - Body: `{"include_without_clip": false}`
  - Exports dataset into `RETRAINING_DATASET_PATH` (default `./retraining-data`).
  - Generates:
    - `manifest.jsonl`
    - `positive/*.mp4` (confirmed/escalated)
    - `negative/*.mp4` (false_positive)

- `POST /api/retraining/thresholds/recompute`
  - Body example:
    - `{"event_type":"VIOLENCE_POSE_RISK","min_samples":20,"step":0.01}`
  - Computes best threshold using operator labels and saves JSON file to:
    - `RETRAINING_THRESHOLDS_PATH` (default `./retraining-data/threshold_overrides.json`)

- `GET /api/retraining/thresholds`
  - Returns currently saved threshold overrides JSON.

## How analytics uses new thresholds

`deepstream-analytics/analytics_service.py` reads `THRESHOLD_OVERRIDES_PATH`.

- Default path: `deepstream-analytics/config/threshold_overrides.json`
- If the file contains:
  - `{"VIOLENCE_POSE_RISK": {"threshold": 0.92, ...}}`
- Then this value overrides `violence_detection.video_alert_threshold`.

## Suggested production flow

1. Operators mark alerts (`confirmed` / `false_positive` / `escalated`).
2. Periodically run threshold recomputation (daily/weekly).
3. Deploy generated threshold file to analytics service.
4. Restart analytics service to apply new threshold.

This is the safest first step before full model fine-tuning.
