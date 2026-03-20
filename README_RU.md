# 🎓 School Risk Detection MVP - Руководство по запуску

## 📋 Требования

- Docker Desktop (Windows/Mac) или Docker + Docker Compose (Linux)
- Минимум 4GB RAM
- Свободное место: 2GB

## 🚀 Быстрый старт (3 шага)

### Шаг 1: Запустите Docker контейнеры

```bash
docker-compose up -d
```

**Что происходит:** Запускаются все сервисы (база данных, backend API, frontend, analytics)

**Ожидаемое время:** 2-3 минуты при первом запуске

**Проверка:** Выполните `docker ps` - должно быть 5-6 запущенных контейнеров

### Шаг 2: Подождите 30 секунд

Подождите пока все сервисы полностью запустятся и база данных будет готова.

```bash
# Можно проверить логи
docker logs risk-engine --tail 20
```

Ищите строку: `Application startup complete`

### Шаг 3: Выполните начальную настройку

```bash
bash quick_setup.sh
```

**Что делает скрипт:**
- ✅ Создает пользователя admin
- ✅ Настраивает пороги риска
- ✅ Активирует камеры
- ✅ Добавляет типы событий

**Ожидаемый вывод:**
```
✅ Setup Complete!
📝 Login Credentials:
   URL:      http://localhost
   Username: admin
   Password: admin123
```

---

## 🌐 Вход в систему

1. Откройте браузер
2. Перейдите на: **http://localhost**
3. Введите:
   - **Username:** `admin`
   - **Password:** `admin123`

---

## ❌ Решение проблем

### Проблема 1: "Login error: 401 Unauthorized"

**Причина:** Пользователь admin не создан

**Решение:**
```bash
# Пересоздайте пользователя вручную
bash init_admin.sh
```

### Проблема 2: "Cannot connect to database"

**Причина:** База данных еще не готова

**Решение:**
```bash
# Подождите 30 секунд и повторите
docker logs risk-postgres

# Должно быть:
# "database system is ready to accept connections"
```

### Проблема 3: "Page not loading"

**Причина:** Frontend контейнер не запустился

**Решение:**
```bash
# Проверьте статус
docker ps | grep web-ui

# Если не запущен, пересоберите
docker-compose up -d --build web-ui
```

### Проблема 4: Камеры показывают 0/1

**Решение:**
```bash
# Обновите статус камер
docker exec risk-postgres psql -U riskuser -d risk_detection -c "UPDATE cameras SET status = 'online', last_seen = NOW();"
```

### Проблема 5: Слишком много алертов

**Решение:**
1. Зайдите в **Settings**
2. Выберите preset **"Low Sensitivity"**
3. Или увеличьте вручную:
   - Alert Threshold → 20.0
   - Cooldown Period → 300 seconds

---

## 🔧 Настройка системы

### Через Web UI (рекомендуется)

1. Зайдите в **Settings**
2. Используйте **Quick Presets** или настройте вручную
3. Нажмите **Save**

### Через базу данных

```bash
docker exec risk-postgres psql -U riskuser -d risk_detection

# Показать текущие настройки
SELECT key, value FROM system_config;

# Изменить порог
UPDATE system_config SET value = '20.0' WHERE key = 'risk_score_alert_threshold';

\q
```

---

## 📊 Структура системы

```
┌─────────────────┐
│   Web UI        │  ← Интерфейс охранника
│  (React)        │
└────────┬────────┘
         │
┌────────▼────────┐
│  Risk Engine    │  ← Backend API + Агрегация рисков
│  (FastAPI)      │
└────────┬────────┘
         │
┌────────▼────────┐
│   PostgreSQL    │  ← База данных
│                 │
└─────────────────┘
         ▲
         │
┌────────┴────────┐
│  Analytics      │  ← AI детекция событий
│  (DeepStream)   │
└─────────────────┘
```

---

## 📖 Как работает система

1. **AI камеры** анализируют видео и детектируют события:
   - Драка (вес: 10.0)
   - Скопление людей (вес: 5.0)
   - Бег (вес: 3.0)
   - И другие...

2. **События накапливаются** в окне агрегации (60 сек)

3. **Рассчитывается Risk Score:**
   ```
   Risk Score = Σ (вес × confidence × duration_factor)
   ```

4. **Если Score ≥ Threshold** → создается Alert

5. **Охранник видит алерт** и может:
   - ✅ Подтвердить и отреагировать
   - ❌ Отметить как ложное срабатывание
   - ⬆️ Эскалировать руководству

---

## ⚙️ Настройка порогов

### Quick Presets

| Preset | Alert Threshold | Critical | Cooldown | Описание |
|--------|----------------|----------|----------|----------|
| 🔴 High Sensitivity | 10.0 | 15.0 | 60s | Максимум алертов |
| ⚖️ Balanced | 15.0 | 20.0 | 180s | **Рекомендуется** |
| 🟢 Low Sensitivity | 20.0 | 30.0 | 300s | Только критические |

### Когда использовать:

- **High Sensitivity:** Первые дни для калибровки
- **Balanced:** Стандартная работа
- **Low Sensitivity:** Много ложных срабатываний

---

## 🎯 Примеры сценариев

### Сценарий 1: Начинается драка

```
События за 60 секунд:
- face_to_face (6.0 × 0.85) = 5.1
- aggressive_posture (4.0 × 0.90) = 3.6
- fight_detected (10.0 × 0.92) = 9.2
- crowd_detected (5.0 × 0.80) = 4.0

ИТОГО: 21.9 → 🚨 CRITICAL ALERT!
```

**Действие охранника:** Немедленно идти на место

### Сценарий 2: Скопление на перемене

```
События:
- crowd_detected (5.0 × 0.75) = 3.75
- loitering_detected (2.0 × 0.70) = 1.4

ИТОГО: 5.15 → ✅ Нет алерта (< 15.0)
```

**Действие:** Система игнорирует нормальное поведение

### Сценарий 3: Ранее предупреждение

```
События (ДО драки):
- aggressive_posture (4.0 × 0.88) = 3.52
- face_to_face (6.0 × 0.82) = 4.92
- raised_voice (3.5 × 0.75) = 2.63
- sudden_movement (3.5 × 0.85) = 2.98

ИТОГО: 14.05 → ⚠️ Близко к порогу!
```

Если добавится еще одно событие → алерт → охранник предотвращает драку!

---

## 📞 Команды для управления

### Старт/Стоп

```bash
# Запустить
docker-compose up -d

# Остановить
docker-compose down

# Перезапустить
docker-compose restart

# Пересобрать
docker-compose up -d --build
```

### Логи

```bash
# Все сервисы
docker-compose logs -f

# Только backend
docker logs -f risk-engine

# Только база данных
docker logs -f risk-postgres
```

### База данных

```bash
# Подключиться к PostgreSQL
docker exec -it risk-postgres psql -U riskuser -d risk_detection

# Полезные запросы
SELECT COUNT(*) FROM alerts;
SELECT COUNT(*) FROM users;
SELECT * FROM system_config;

\q  # выход
```

---

## 🆘 Полный сброс

Если что-то сломалось и нужно начать заново:

```bash
# 1. Остановить и удалить все
docker-compose down -v

# 2. Удалить образы (опционально)
docker system prune -a

# 3. Запустить заново
docker-compose up -d

# 4. Подождать 30 секунд

# 5. Выполнить setup
bash quick_setup.sh
```

---

## 📚 Дополнительные материалы

- **UPGRADE_NOTES.md** - Что нового в этой версии
- **LIVE_VIEW_GUIDE.md** - Как добавить live просмотр камер
- **quick_setup.sh** - Скрипт начальной настройки
- **init_admin.sh** - Создание admin пользователя

---

## 🎉 Готово!

Теперь система полностью настроена и готова к работе.

**Проверьте:**
- ✅ Можете войти на http://localhost
- ✅ Видите Dashboard со статистикой
- ✅ Камеры показывают статус (Online/Offline)
- ✅ Можете открыть Settings и изменить пороги

**Следующие шаги:**
1. Настройте пороги под вашу школу
2. Добавьте реальные RTSP камеры (configs/cameras.yaml)
3. Мониторьте алерты первые дни
4. Скорректируйте настройки если нужно

Удачи! 🚀
