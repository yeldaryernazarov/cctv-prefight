# 🚀 START HERE - Быстрый старт

## Проблема с логином? (401 Error)

Если вы видите ошибку **401 Unauthorized** при попытке войти, выполните эти шаги:

---

## ✅ Решение в 3 шага:

### Шаг 1: Убедитесь что контейнеры запущены

```bash
docker-compose up -d
```

Подождите **30 секунд** пока всё запустится.

### Шаг 2: Выполните тестовый скрипт

```bash
bash test_login.sh
```

**Этот скрипт:**
- ✅ Проверит что контейнеры запущены
- ✅ Проверит что база данных готова
- ✅ Проверит есть ли пользователь admin
- ✅ Создаст admin если его нет
- ✅ Протестирует логин через API

### Шаг 3: Войдите в систему

Откройте браузер: **http://localhost**

```
Username: admin
Password: admin123
```

---

## 🔧 Альтернативные методы

### Метод 1: Через create_admin.py

```bash
docker exec risk-engine python create_admin.py
```

### Метод 2: Перезапуск с автосозданием

```bash
# Остановить
docker-compose down

# Запустить заново
docker-compose up -d

# Подождать 30 секунд (admin создастся автоматически)
sleep 30

# Проверить логи
docker logs risk-engine | grep -i admin
```

Вы должны увидеть:
```
✅ Admin user created successfully! Username: admin, Password: admin123
```

### Метод 3: Ручное создание через базу данных

```bash
# 1. Подключитесь к базе
docker exec -it risk-postgres psql -U riskuser -d risk_detection

# 2. Проверьте есть ли admin
SELECT username, role FROM users WHERE username = 'admin';

# 3. Если нет - создайте (скопируйте всё целиком)
DELETE FROM users WHERE username = 'admin';

-- Пароль: admin123 (хеш уже сгенерирован)
INSERT INTO users (username, password_hash, role, full_name, email, active, created_at)
VALUES (
    'admin', 
    '$2b$12$KIXqGfR.rR9YLNmZ3yqZduVvN8QlZYKxOJvRqYm4vLVxGQdvJPm7G',
    'admin',
    'Administrator',
    'admin@school.com',
    true,
    NOW()
);

-- Проверьте
SELECT username, role, active FROM users WHERE username = 'admin';

\q
```

---

## 📊 Проверка что всё работает

### Проверка 1: API отвечает

```bash
curl http://localhost:8001/health
```

Должно быть:
```json
{"status":"healthy","timestamp":"...","database":"connected"}
```

### Проверка 2: Логин работает

```bash
curl -X POST "http://localhost:8001/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```

Должно вернуть токен:
```json
{"access_token":"eyJ...","token_type":"bearer",...}
```

### Проверка 3: Frontend загружается

Откройте в браузере: http://localhost

Должна открыться страница логина.

---

## 🆘 Всё еще не работает?

### Полный сброс системы

```bash
# Остановить и удалить ВСЁ (включая данные)
docker-compose down -v

# Удалить старые образы
docker-compose down --rmi all

# Запустить с нуля
docker-compose up -d --build

# Подождать 1 минуту
sleep 60

# Проверить что admin создан
docker logs risk-engine | grep -i "admin user"

# Если видите "Admin user created successfully" - всё OK!
```

### Проверка логов

```bash
# Backend логи
docker logs risk-engine

# Database логи  
docker logs risk-postgres

# Frontend логи
docker logs web-ui
```

Ищите ошибки или строки с "admin".

---

## 📞 Частые вопросы

**Q: Пароль точно admin123?**  
A: Да! Всегда `admin123` (без пробелов)

**Q: Username чувствителен к регистру?**  
A: Нет, но используйте `admin` маленькими буквами

**Q: Сколько ждать после docker-compose up?**  
A: Минимум 30 секунд для первого запуска

**Q: Можно ли сменить пароль?**  
A: Да, в Settings после входа, или в БД напрямую

---

## ✅ Всё работает!

Если вы видите Dashboard после логина - **поздравляю, система запущена!** 🎉

Следующие шаги:
1. Зайдите в **Settings** и настройте пороги
2. Проверьте **Cameras** - статус камер
3. Посмотрите **Alerts** - тестовые алерты

**Документация:**
- `README_RU.md` - полное руководство
- `UPGRADE_NOTES.md` - что нового
- `quick_setup.sh` - полная настройка системы

Удачи! 🚀
