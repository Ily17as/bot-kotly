from app.database.database import get_db
from datetime import datetime

async def save_request(user_id: int, username: str, description: str, location: str, media_id: str, media_type: str):
    db = await get_db()
    await db.execute(
        """
        INSERT INTO requests (user_id, username, description, location, media_id, media_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, username, description, location, media_id, media_type, datetime.utcnow())
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

async def add_master(telegram_id: int, username: str):
    """Зарегистрировать нового мастера (или обновить существующего)."""
    db = await get_db()
    await db.execute(
        """
        INSERT INTO masters (telegram_id, username)
        VALUES (?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username, is_active=1
        """,
        (telegram_id, username)
    )
    await db.commit()
    await db.close()

async def list_active_masters():
    """Вернуть список telegram_id всех активных мастеров."""
    db = await get_db()
    async with db.execute(
        "SELECT telegram_id FROM masters WHERE is_active = 1"
    ) as cursor:
        rows = await cursor.fetchall()
    await db.close()
    return [r[0] for r in rows]

async def deactivate_master(telegram_id: int):
    """Заблокировать мастера (не присылать ему заявки)."""
    db = await get_db()
    await db.execute(
        "UPDATE masters SET is_active = 0 WHERE telegram_id = ?",
        (telegram_id,)
    )
    await db.commit()
    await db.close()


async def list_available_masters():
    db = await get_db()
    async with db.execute(
        "SELECT telegram_id FROM masters "
        "WHERE is_active=1 AND active_orders<2 AND has_debt=0"
    ) as cursor:
        rows = await cursor.fetchall()
    await db.close()
    return [r[0] for r in rows]

async def take_request(request_id: int, master_id: int):
    db = await get_db()
    # пометить заявку «в работе»
    await db.execute(
        "UPDATE requests SET status='in_progress', master_id=? "
        "WHERE id=? AND status='open'",
        (master_id, request_id)
    )
    # увеличить счётчик активных заказов мастера
    await db.execute(
        "UPDATE masters SET active_orders=active_orders+1 "
        "WHERE telegram_id=?",
        (master_id,)
    )
    await db.commit()
    await db.close()

async def decline_request(request_id: int, master_id: int):
    db = await get_db()
    await db.execute(
        "UPDATE requests SET status='open', master_id=NULL "
        "WHERE id=? AND master_id=?",
        (request_id, master_id)
    )
    await db.commit()
    await db.close()

async def complete_request(request_id: int, master_id: int):
    db = await get_db()
    await db.execute(
        "UPDATE requests SET status='done' WHERE id=? AND master_id=?",
        (request_id, master_id)
    )
    await db.execute(
        "UPDATE masters SET active_orders=active_orders-1, has_debt=1 "
        "WHERE telegram_id=?",
        (master_id,)
    )
    await db.commit()
    await db.close()

async def pay_commission(master_id: int):
    db = await get_db()
    await db.execute(
        "UPDATE masters SET has_debt=0 WHERE telegram_id=?",
        (master_id,)
    )
    await db.commit()
    await db.close()
