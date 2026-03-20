## Как “подставить” модели без правок кода

Сервис `deepstream-analytics/analytics_service.py` по умолчанию ищет модели в папке:
`deepstream-analytics/models/`

### 1) Детекция людей (YOLO)

Можно положить файл с одним из имён:
- `person_yolo.pt` (предпочтительно)
- иначе будет использовано `yolov8n.pt` (может попытаться скачать)

Опционально можно переопределить путь через конфиг:
`violence_detection.person_detection` / `models.person_yolo_path` в `deepstream-analytics/config/analytics_config.yaml`.

### 2) Violence detection (модель из `violence_detection_pose_training.ipynb`)

1. Положите TorchScript:
- `pose_model_torchscript.pt`  (это имя из ноутбука)

2. Положите конфиг из ноутбука:
- `pose_config.json`

3. Положите YOLO pose веса:
- `pose_yolo.pt` (или достаточно, чтобы был доступен `yolov8n-pose.pt` — сервис попробует загрузить его по имени)

Если файл `pose_model_torchscript.pt` найден, violence-детектор включится автоматически.

### 3) Profanity / “мат” (распознавание слов)

По умолчанию сервис ищет файл:
- `profanity_keywords_ru.txt`

Формат: по одному слову/фразе на строку.

Если файл отсутствует — profanity-детектор будет выключен.
Если установлен `easyocr` и файл с ключевыми словами есть — включится OCR+ключевые слова.

### 4) Быстрый чек

После копирования моделей перезапустите сервис `deepstream-analytics` и `risk-engine`.
Новые типы событий автоматически создаются в БД как:
- `VIOLENCE_POSE_RISK`
- `PROFANITY_RISK`

