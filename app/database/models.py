from app.database.database import get_db
from datetime import datetime

async def save_request(user_id: int, description: str, location: str, media_id: str, media_type: str):
    db = await get_db()
    await db.execute(
        """
        INSERT INTO requests (user_id, description, location, media_id, media_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, description, location, media_id, media_type, datetime.utcnow())
    )
    await db.commit()
    await db.close()


async def get_user_requests(user_id: int):
    db = await get_db()
    async with db.execute(
        "SELECT * FROM requests WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ) as cursor:
        rows = await cursor.fetchall()
    await db.close()
    return rows


async def add_user(telegram_id: int, username: str):
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)",
        (telegram_id, username)
    )
    await db.commit()
    await db.close()


async def list_users():
    db = await get_db()
    async with db.execute("SELECT telegram_id, username FROM users") as cursor:
        rows = await cursor.fetchall()
    await db.close()
    return rows
