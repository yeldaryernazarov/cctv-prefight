# 🚀 БЫСТРЫЙ СТАРТ - School Risk Detection (УЛУЧШЕННАЯ ВЕРСИЯ)

## ✅ Что исправлено в этой версии

1. **Камеры 0/1 → 1/1** - теперь правильно показывают статус
2. **Меньше алертов** - умная агрегация вместо спама
3. **Раннее предупреждение** - система предупреждает ДО драки
4. **Live View** - просмотр камер с YOLO детекцией в реальном времени

---

## 📦 Установка и запуск

### 1. Распакуйте архив
```bash
unzip school-risk-detection-mvp-IMPROVED.zip
cd school-risk-detection-mvp-fixed
```

### 2. Запустите систему
```bash
docker compose up -d
```

### 3. ⚡ ВАЖНО: Примените исправления
```bash
bash quick_fix.sh
```

Этот скрипт:
- Исправит статус камер (0/1 → 1/1)
- Настроит правильные пороги
- Уменьшит количество алертов
- Добавит новые типы событий

### 4. Откройте Dashboard
```
http://localhost
```

**Логин:**
- Username: `admin`
- Password: `admin123`

---

## 🎯 Что вы увидите после исправлений

### ДО:
```
Cameras: 0/1 Online ❌
Alerts: 94 (много повторений) ❌
```

### ПОСЛЕ:
```
Cameras: 1/1 Online ✅
Alerts: 10-15 (только важные) ✅
```

---

## 📊 Как работает система предупреждений

### Система НЕ создаст алерт для:
- ❌ Просто бег в коридоре (score ~3)
- ❌ Скопление 3-4 людей (score ~6)
- ❌ Быстрая ходьба (score ~2)

### Система создаст алерт HIGH для:
- ⚠️ Конфронтация (лицом к лицу) + агрессия (score ~18)
- ⚠️ Толпа + быстрые движения (score ~16)

### Система создаст алерт CRITICAL для:
- 🚨 Начинающаяся драка (score ~28)
- 🚨 Массовая потасовка (score ~35)

### 🕐 Временная шкала

```
0:00 - Ситуация начинается (бег, сближение)
0:30 - Конфронтация формируется
0:45 - ⚠️ АЛЕРТ! Score достиг 15+
       → Охранник получает предупреждение
1:00 - Охранник прибывает
       → ✅ Предотвращает драку!
```

**Ключевое:** Система предупреждает **ДО** эскалации, а не после.

---

## 📹 Live View камер (опционально)

Для просмотра камер с YOLO детекцией:

1. Откройте страницу "Cameras"
2. Нажмите "📹 View Live Stream" на камере
3. Увидите:
   - 🟩 Зеленые рамки вокруг людей
   - 🔢 Track ID каждого человека
   - 📊 Confidence score
   - ⏱️ Timestamp и индикатор LIVE
   - ⛶ Fullscreen режим

**Примечание:** Для полного функционала Live View нужен stream server. См. IMPROVEMENTS_GUIDE.md

---

## 🔧 Полезные команды

### Проверка статуса
```bash
docker compose ps
```

### Просмотр логов
```bash
docker compose logs -f risk-engine
docker compose logs -f deepstream-analytics
```

### Проверка камер в БД
```bash
docker compose exec postgres psql -U riskuser -d risk_detection -c "SELECT id, name, status, last_seen FROM cameras;"
```

### Проверка конфигурации
```bash
docker compose exec postgres psql -U riskuser -d risk_detection -c "SELECT key, value FROM system_config WHERE key LIKE '%threshold%' OR key LIKE '%cooldown%';"
```

### Перезапуск сервиса
```bash
docker compose restart risk-engine
docker compose restart deepstream-analytics
```

### Остановка системы
```bash
docker compose down
```

---

## ⚙️ Тонкая настройка (если нужно)

### Если алертов слишком МНОГО:
```sql
-- Войдите в БД
docker compose exec postgres psql -U riskuser -d risk_detection

-- Увеличьте порог
UPDATE system_config SET value = '20.0' WHERE key = 'risk_score_alert_threshold';

-- Увеличьте cooldown до 5 минут
UPDATE system_config SET value = '300' WHERE key = 'cooldown_seconds';

-- Выход
\q

-- Перезапустите
docker compose restart risk-engine
```

### Если алертов слишком МАЛО:
```sql
-- Уменьшите порог
UPDATE system_config SET value = '12.0' WHERE key = 'risk_score_alert_threshold';

-- Уменьшите cooldown
UPDATE system_config SET value = '120' WHERE key = 'cooldown_seconds';
```

---

## 📖 Подробная документация

- **IMPROVEMENTS_GUIDE.md** - Полное руководство по всем улучшениям
- **README.md** - Общая документация системы

---

## ❓ Частые вопросы

**В: Камеры все еще показывают 0/1?**
О: Запустите `bash quick_fix.sh` и перезагрузите браузер (Ctrl+Shift+R)

**В: Слишком много алертов?**
О: Проверьте, применен ли quick_fix.sh. Должны быть настройки:
- aggregation_window: 60 сек
- threshold: 15.0
- cooldown: 180 сек

**В: Когда система предупреждает охранника?**
О: Когда риск-скор достигает 15.0+, то есть ДО начала драки, когда еще есть время предотвратить конфликт.

**В: Как протестировать?**
О: Используйте скрипт в IMPROVEMENTS_GUIDE.md для создания тестового критического алерта.

---

## ✅ Чек-лист успешного запуска

- [ ] Система запущена: `docker compose up -d`
- [ ] Quick fix применен: `bash quick_fix.sh`
- [ ] Dashboard открывается на http://localhost
- [ ] Камеры показывают 1/1 Online
- [ ] Количество алертов разумное (~10-15, не 94)
- [ ] Браузер обновлен (Ctrl+Shift+R)

---

**Готово! Система настроена и готова к работе! 🎉**

Если есть проблемы - смотрите IMPROVEMENTS_GUIDE.md или логи:
```bash
docker compose logs -f
```
