import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
import bcrypt
from datetime import datetime

DATABASE_URL = "postgresql+asyncpg://riskuser:riskpass123@postgres:5432/risk_detection"


async def create_admin_user():
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        # Удаляем старого админа
        await session.execute(text("DELETE FROM users WHERE username = 'admin'"))
        await session.commit()

        # Создаём хеш пароля через bcrypt напрямую
        password = "admin123"
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
        print(f"Password hash created: {password_hash[:50]}...")

        # Вставляем нового пользователя
        await session.execute(
            text("""
                INSERT INTO users (username, password_hash, role, full_name, email, active, created_at) 
                VALUES (:u, :p, :r, :n, :e, :a, :c)
            """),
            {
                "u": "admin", 
                "p": password_hash, 
                "r": "admin", 
                "n": "Administrator",
                "e": "admin@school.com",
                "a": True,
                "c": datetime.utcnow()
            }
        )
        await session.commit()

        # Проверяем
        result = await session.execute(text("SELECT id, username, role, active FROM users WHERE username = 'admin'"))
        user = result.first()

        if user:
            print(f"✅ Admin created successfully!")
            print(f"   ID: {user[0]}")
            print(f"   Username: {user[1]}")
            print(f"   Role: {user[2]}")
            print(f"   Active: {user[3]}")
            print(f"\n🔑 Login credentials:")
            print(f"   Username: admin")
            print(f"   Password: admin123")
        else:
            print("❌ Failed to create admin")

    await engine.dispose()


if __name__ == "__main__":
    print("Creating admin user...")
    asyncio.run(create_admin_user())