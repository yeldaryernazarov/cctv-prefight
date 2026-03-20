# 🚨 БЫСТРОЕ РЕШЕНИЕ 401 ОШИБКИ

## Проблема
Вы видите: `❌ Login failed! {"detail":"Incorrect username or password"}`

## ✅ Решение (30 секунд):

```bash
bash fix_admin_now.sh
```

**Этот скрипт:**
1. Генерирует правильный bcrypt хеш
2. Создает admin пользователя в базе
3. Тестирует логин
4. Всё!

---

## 🔄 Альтернативное решение - Пересборка

Если `fix_admin_now.sh` не сработал, пересоберите контейнер:

```bash
# Остановите
docker-compose down

# Пересоберите risk-engine
docker-compose build risk-engine

# Запустите всё
docker-compose up -d

# Подождите 30 секунд
sleep 30

# Admin создастся автоматически!
```

Проверьте логи:
```bash
docker logs risk-engine | grep -i "admin user"
```

Должно быть:
```
✅ Admin user created successfully! Username: admin, Password: admin123
```

---

## 🛠️ Ручное решение (если скрипты не работают)

### Способ 1: Через Python в контейнере

```bash
docker exec -it risk-engine python3 << 'PYTHON'
import bcrypt
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text

async def create_admin():
    engine = create_async_engine(
        "postgresql+asyncpg://riskuser:riskpass123@postgres:5432/risk_detection"
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession)
    
    # Generate hash
    password_hash = bcrypt.hashpw(b'admin123', bcrypt.gensalt(rounds=12)).decode('utf-8')
    print(f"Hash: {password_hash[:30]}...")
    
    async with async_session() as session:
        # Delete old
        await session.execute(text("DELETE FROM users WHERE username = 'admin'"))
        
        # Create new
        await session.execute(
            text("""
                INSERT INTO users (username, password_hash, role, full_name, email, active, created_at)
                VALUES (:u, :p, :r, :n, :e, :a, NOW())
            """),
            {"u": "admin", "p": password_hash, "r": "admin", "n": "Administrator", "e": "admin@school.com", "a": True}
        )
        await session.commit()
        print("✅ Admin created!")
    
    await engine.dispose()

asyncio.run(create_admin())
PYTHON
```

### Способ 2: Прямо в базу данных с готовым хешем

```bash
docker exec -it risk-postgres psql -U riskuser -d risk_detection
```

Затем выполните:
```sql
DELETE FROM users WHERE username = 'admin';

-- Этот хеш = пароль "admin123"
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
SELECT username, role, active, substring(password_hash, 1, 20) FROM users WHERE username = 'admin';

\q
```

---

## 🧪 Проверка что работает

```bash
curl -X POST "http://localhost:8001/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```

Должно вернуть:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user_id": "...",
  "username": "admin",
  "role": "admin"
}
```

Если видите `access_token` - всё работает! ✅

---

## 📝 Теперь войдите

Откройте: **http://localhost**

```
Username: admin
Password: admin123
```

Должны увидеть Dashboard! 🎉

---

## 🔍 Почему была проблема?

Старая версия `create_admin.py` использовала библиотеку `passlib`, которая создавала несовместимый хеш.

Новая версия использует чистый `bcrypt` - совместимо с `auth.py` в backend.

Решение: либо пересобрать контейнер, либо запустить `fix_admin_now.sh`.

---

## ✅ Готово!

После любого из этих решений вы сможете войти в систему.
