# 📹 Исправление Live View камер

## Проблема
Ошибка: `GET http://localhost:8003/stream/... net::ERR_CONNECTION_REFUSED`

Это означает что **stream-server** не запущен.

---

## ✅ Быстрое решение (Option 1 - Рекомендуется)

Live view с YOLO детекцией требует дополнительную настройку. 

**Пока его нет, отключим кнопку:**

### Временно отключить Live View

Замените файл `web-ui/src/pages/CamerasPage.js`:

Закомментируйте кнопку "View Live Stream" (строка 83-110):

```javascript
{/* ВРЕМЕННО ОТКЛЮЧЕНО - Live View
<div style={{ marginTop: '15px', paddingTop: '15px', borderTop: '1px solid #eee' }}>
  <button ... >
    📹 View Live Stream
  </button>
</div>
*/}
```

Затем:
```bash
docker-compose restart web-ui
```

---

## ✅ Полное решение (Option 2 - Включить Live View)

### Шаг 1: Проверьте что stream-server в docker-compose.yml

Откройте `docker-compose.yml` и убедитесь что есть:

```yaml
stream-server:
  build:
    context: ./deepstream-analytics
    dockerfile: Dockerfile.stream
  container_name: stream-server
  ports:
    - "8003:8003"
  environment:
    - FLASK_ENV=production
  networks:
    - risk-net
  restart: unless-stopped
```

### Шаг 2: Создайте Dockerfile.stream

```bash
cat > deepstream-analytics/Dockerfile.stream << 'DOCKERFILE'
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    flask==2.3.0 \
    opencv-python-headless==4.8.0.74 \
    numpy==1.24.3

COPY stream_server.py .

EXPOSE 8003

CMD ["python", "stream_server.py"]
DOCKERFILE
```

### Шаг 3: Упрощенный stream_server.py

Создайте `deepstream-analytics/stream_server.py`:

```python
from flask import Flask, Response
import cv2
import numpy as np
import time

app = Flask(__name__)

# Placeholder frame generator
def generate_placeholder():
    """Generate placeholder frame when no camera feed available"""
    while True:
        # Create a simple placeholder image
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Add text
        cv2.putText(
            frame,
            "Camera Feed Not Available",
            (100, 240),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2
        )
        
        cv2.putText(
            frame,
            "Configure RTSP stream in analytics service",
            (50, 280),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 200, 200),
            1
        )
        
        # Encode as JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(0.1)  # 10 FPS

@app.route('/stream/<camera_id>')
def video_feed(camera_id):
    """MJPEG stream endpoint"""
    return Response(
        generate_placeholder(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/health')
def health():
    """Health check"""
    return {'status': 'ok', 'service': 'stream-server'}

if __name__ == '__main__':
    print("Starting Stream Server on port 8003...")
    app.run(host='0.0.0.0', port=8003, threaded=True)
```

### Шаг 4: Запустите stream-server

```bash
# Пересоберите и запустите
docker-compose up -d --build stream-server

# Проверьте что работает
curl http://localhost:8003/health
```

Должно вернуть:
```json
{"service":"stream-server","status":"ok"}
```

### Шаг 5: Проверьте Live View

Теперь зайдите в **Cameras** и нажмите **View Live Stream**.

Должны увидеть placeholder с текстом "Camera Feed Not Available".

---

## 🎯 Для реального Live View с YOLO

Для полноценного live view нужно:

1. **Интеграция с analytics service** - передавать frames с детекциями
2. **RTSP декодирование** - читать видео с камер
3. **Draw detections** - рисовать bounding boxes
4. **MJPEG encoding** - кодировать для браузера

Это требует:
- Доступ к реальным RTSP камерам
- Настройку `configs/cameras.yaml`
- Интеграцию stream_server с analytics_service

Полное руководство в: **LIVE_VIEW_GUIDE.md** (из предыдущих файлов)

---

## 💡 Быстрый вариант - Просто убрать кнопку

Если live view не критичен сейчас, просто уберите кнопку из интерфейса:

В `web-ui/src/pages/CamerasPage.js` удалите секцию с кнопкой (строки 82-111).

Или замените на:

```javascript
<div style={{ marginTop: '15px', paddingTop: '15px', borderTop: '1px solid #eee' }}>
  <p style={{ fontSize: '14px', color: '#666', textAlign: 'center' }}>
    💡 Live view coming soon
  </p>
</div>
```

Пересоберите:
```bash
docker-compose up -d --build web-ui
```

---

## ✅ Рекомендация

Для MVP **уберите live view кнопку** пока не настроите реальные камеры.

Система работает и без live view:
- ✅ Alerts создаются
- ✅ Dashboard работает  
- ✅ Settings работают
- ✅ История событий сохраняется

Live view - это nice to have, но не обязательно для тестирования системы.
