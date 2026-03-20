# School Risk Detection MVP - УЛУЧШЕННАЯ ВЕРСИЯ ✨

## 🎯 Последние улучшения

**Эта версия содержит критические исправления и улучшения:**

- ✅ **Исправлено:** Камеры теперь правильно показывают статус (1/1 вместо 0/1)
- ✅ **Улучшено:** Уменьшено количество повторяющихся алертов (умная агрегация)
- ✅ **Добавлено:** Раннее обнаружение конфликтов (предупреждение ДО драки)
- ✅ **Новое:** Live View камер с YOLO детекцией в реальном времени
- ✅ **Оптимизировано:** Более точные пороги и веса событий

📖 **Полное руководство:** См. [IMPROVEMENTS_GUIDE.md](IMPROVEMENTS_GUIDE.md)

---

## Описание
MVP система превентивного выявления риск-ситуаций в школе по видео (edge).
Система работает в режиме реального времени, анализирует видеопотоки, выявляет риск-события и предоставляет алерты охраннику для принятия решений.

**Ключевая особенность:** Система предупреждает охранника **ДО** эскалации конфликта, а не после того как драка уже началась.

## Архитектура

Система состоит из следующих компонентов:

1. **DeepStream Analytics** - видеоаналитика (детекция людей, трекинг, выявление риск-событий)
2. **Risk Engine** - бэкенд API (агрегация событий, расчет риск-скора, генерация алертов)
3. **Clip Service** - управление видеоклипами (ring buffer, сохранение фрагментов)
4. **PostgreSQL** - хранение данных
5. **Redis** - кэширование и очереди
6. **Web UI** - панель охранника
7. **Nginx** - reverse proxy

## Требования

### Железо
- **GPU**: NVIDIA RTX 3060/3070 или выше (для DeepStream)
- **CPU**: 8+ ядер
- **RAM**: 16GB+
- **Storage**: 500GB+ SSD (для хранения клипов)

### Программное обеспечение
- Ubuntu 22.04 LTS
- Docker 24.0+
- Docker Compose 2.20+
- NVIDIA Docker Runtime
- CUDA 12.0+

## 🚀 Быстрый старт (ОБНОВЛЕНО)

### 1. Подготовка системы

```bash
# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Установка Docker Compose
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Установка NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Проверка GPU
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

### 2. Клонирование и запуск

```bash
# Распаковать архив проекта
unzip school-risk-detection-mvp-IMPROVED.zip
cd school-risk-detection-mvp-fixed

# Запуск всех сервисов
docker compose up -d

# ⚡ ВАЖНО: Применить улучшения (исправляет камеры 0/1 → 1/1)
bash quick_fix.sh

# Проверка статуса
docker compose ps

# Просмотр логов
docker compose logs -f
```

**Что делает `quick_fix.sh`:**
- ✅ Исправляет статус камер (0/1 → 1/1)
- ✅ Уменьшает количество повторяющихся алертов
- ✅ Настраивает правильные пороги и cooldown
- ✅ Добавляет новые типы событий для раннего обнаружения

📖 **Подробнее:** См. [IMPROVEMENTS_GUIDE.md](IMPROVEMENTS_GUIDE.md)

### 3. Первоначальная настройка

#### Добавление камер

1. Откройте браузер: http://localhost:3000
2. Войдите с учетными данными:
   - **Username**: admin
   - **Password**: admin123
3. Перейдите в раздел "Cameras"
4. Добавьте камеры с RTSP URL

#### Конфигурация зон (ROI)

В разделе "Settings" можно настроить:
- Зоны мониторинга (полигоны на видео)
- Пороги для различных типов событий
- Расписания (тихое время / перемены)

## Конфигурация камер

Файл: `/configs/cameras.yaml`

```yaml
cameras:
  - id: "camera-1"
    name: "Main Entrance"
    rtsp_url: "rtsp://admin:password@192.168.1.100:554/stream1"
    rtsp_substream_url: "rtsp://admin:password@192.168.1.100:554/stream2"
    location: "Main Entrance"
    fps: 15
    zones:
      - id: "zone-1"
        name: "Entrance Area"
        polygon:
          - {x: 100, y: 100}
          - {x: 500, y: 100}
          - {x: 500, y: 400}
          - {x: 100, y: 400}
        zone_type: "entrance"
        schedule_profile: "default"
```

## Типы риск-событий (ОБНОВЛЕНО)

### 1. CONFRONTATION_RISK (Конфронтация) - ВЕС: 4.0 🆕
**Раннее обнаружение конфликта!**
Люди стоят лицом к лицу на близком расстоянии с напряженным языком тела. Система детектирует конфронтацию **ДО** того как начнется физическое столкновение.

**Параметры**:
- `distance_threshold`: максимальная дистанция (2.0 метра)
- `angle_threshold`: угол взаимной ориентации (45°)
- `duration_min_sec`: минимальная длительность (3 сек)

### 2. AGGRESSIVE_MOTION (Агрессивные движения) - ВЕС: 3.5 🆕
Резкие, рывковые движения или агрессивные жесты. Указывает на возможную физическую конфронтацию.

**Параметры**:
- `jerk_threshold`: порог резкости движений (8.0)
- `min_events`: минимум событий для алерта (2)

### 3. CROWD_RISK (Скопление людей) - ВЕС: 3.0
Обнаружение формирования толпы или высокой плотности людей. Часто сопровождает конфликты (зеваки).

**Параметры**:
- `min_count`: минимальное количество людей (по умолчанию: 5)
- `density_threshold`: порог плотности (0.3)
- `area_threshold`: минимальная площадь (100 пикселей)

### 4. KINETIC_RISK (Высокая кинетическая активность) - ВЕС: 2.5
Обнаружение резких ускорений и быстрых движений.

**Параметры**:
- `acceleration_threshold`: порог ускорения (5.0)
- `duration_min_sec`: минимальная длительность (1.5 сек)

### 5. PROXIMITY_RISK (Близкое сближение) - ВЕС: 2.0
Обнаружение резкого сближения между людьми или длительного нахождения на малом расстоянии.

**Параметры**:
- `distance_threshold`: порог расстояния (1.5 метра)
- `duration_min_sec`: минимальная длительность (2 сек)
- `rapid_approach_percent`: процент сокращения расстояния (50%)

---

### 📊 Как работает Risk Score

```
Risk Score = Σ (event_weight × confidence × duration_factor)
```

**Пример реальной ситуации:**

| Время | События | Score | Статус |
|-------|---------|-------|--------|
| 0:00 | Двое быстро идут навстречу (PROXIMITY_RISK) | 2.0 | 🟢 OK |
| 0:15 | Остановились лицом к лицу (CONFRONTATION_RISK) | 6.0 | 🟢 OK |
| 0:30 | Агрессивные жесты (AGGRESSIVE_MOTION) | 12.0 | 🟡 Monitor |
| 0:45 | Толпа собирается (CROWD_RISK) | **18.5** | ⚠️ **ALERT!** |
| 1:00 | 🚨 Охранник прибывает и предотвращает драку | - | ✅ Success |

**Без системы:** Охранник узнал бы только когда драка уже началась (1:30+)
**С системой:** Охранник приходит на 0:45 и предотвращает эскалацию
- `density_threshold`: порог плотности (по умолчанию: 0.3)

### 3. KINETIC_RISK (Высокая кинетическая активность)
Обнаружение резких движений, ускорений.

**Параметры**:
- `acceleration_threshold`: порог ускорения (по умолчанию: 5.0)
- `duration_min_sec`: минимальная длительность (по умолчанию: 1.5 сек)

## Панель охранника

### Главный экран
- Список активных алертов
- Статус камер (online/offline)
- Статистика за сегодня

### Карточка алерта
- **Видеоклип** события (10 сек до + 10 сек после)
- **Информация**: камера, время, риск-скор, тип события
- **Действия**:
  - ✅ **Confirm** - подтвердить инцидент
  - ❌ **False Positive** - ложное срабатывание
  - ⚠️ **Escalate** - эскалировать психологу/администратору
- **Комментарий** охранника

## Управление данными

### Retention Policy (Хранение клипов)

По умолчанию клипы хранятся 14 дней. Изменить можно в Settings:
```
clip_retention_days: 14
```

### Автоматическая очистка

Запускается ежедневно через cron. Ручной запуск:
```bash
docker exec -it risk-postgres psql -U riskuser -d risk_detection -c "SELECT cleanup_old_clips();"
```

## Мониторинг

### Health Check Endpoints

- Risk Engine: http://localhost:8001/health
- Clip Service: http://localhost:8002/health

### Метрики

Доступны в разделе "Dashboard":
- FPS по каждой камере
- Количество людей в кадре
- Латентность обработки
- GPU утилизация

### Логи

```bash
# Все логи
docker-compose logs -f

# Конкретный сервис
docker-compose logs -f risk-engine
docker-compose logs -f deepstream-analytics
docker-compose logs -f clip-service
```

## Устранение неполадок

### Камера не подключается

1. Проверьте RTSP URL:
   ```bash
   ffmpeg -i "rtsp://admin:password@192.168.1.100:554/stream1" -frames:v 1 test.jpg
   ```
2. Проверьте сетевую доступность:
   ```bash
   ping 192.168.1.100
   ```
3. Проверьте логи DeepStream:
   ```bash
   docker-compose logs -f deepstream-analytics
   ```

### Низкий FPS

1. Используйте substream (низкое разрешение) для аналитики
2. Уменьшите количество камер на одном сервере
3. Проверьте GPU утилизацию:
   ```bash
   nvidia-smi
   ```

### Много ложных срабатываний

1. Настройте зоны (ROI) - исключите области с постоянным движением
2. Настройте расписания (тихое время / перемены)
3. Увеличьте пороги в Settings:
   - `risk_score_alert_threshold`
   - Параметры конкретных типов событий

## Безопасность

### Смена паролей

**По умолчанию**:
- Admin: admin / admin123
- Guard: guard1 / admin123

**ВАЖНО**: Смените пароли сразу после установки!

### Audit Log

Все действия пользователей логируются в таблице `audit_log`:
- Просмотр клипов
- Принятие решений по алертам
- Изменение настроек

Доступ через SQL:
```sql
SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 100;
```

## API Documentation

API документация доступна по адресу: http://localhost:8001/docs

### Основные endpoints:

#### Аутентификация
```
POST /api/auth/login
GET /api/auth/me
```

#### Алерты
```
GET /api/alerts
GET /api/alerts/{alert_id}
POST /api/alerts/{alert_id}/decision
```

#### Камеры
```
GET /api/cameras
POST /api/cameras
GET /api/cameras/{camera_id}/stats
```

#### Конфигурация
```
GET /api/config
PUT /api/config/{key}
```

## Масштабирование

### Добавление камер

Один edge-сервер (RTX 3070) поддерживает ~4-8 камер (субстрим 720p, 15 FPS).

Для большего количества камер:
1. Установите дополнительные edge-серверы
2. Настройте централизованную БД (PostgreSQL cluster)
3. Используйте load balancer для Web UI

### Высокая доступность

Для production deployment рекомендуется:
1. PostgreSQL с репликацией
2. Redis cluster
3. Несколько инстансов Risk Engine за load balancer
4. Shared storage (NFS/S3) для клипов

## Поддержка и обратная связь

При возникновении проблем:
1. Проверьте логи: `docker-compose logs -f`
2. Проверьте health endpoints
3. Проверьте статус сервисов: `docker-compose ps`

## Лицензия

Proprietary - для использования в школе согласно ТЗ.

## Версия

MVP v1.0.0 (Февраль 2025)
