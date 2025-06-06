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

async def add_master(telegram_id: int, username: str, full_name: str, phone: str):
    """
    Регистрирует или обновляет мастера с именем и телефоном.
    """
    db = await get_db()
    await db.execute("""
        INSERT INTO masters (telegram_id, username, full_name, phone)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            username   = excluded.username,
            full_name  = excluded.full_name,
            phone      = excluded.phone,
            is_active  = 1
    """, (telegram_id, username, full_name, phone))
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
        "WHERE is_active=1 AND active_orders<2"
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
    await db.execute(
        "UPDATE masters SET active_orders=active_orders-1 "
        "WHERE telegram_id=? AND active_orders>0",
        (master_id,)
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

async def force_close_request(request_id: int):
    """Закрыть заявку администратором без подтверждения клиента."""
    db = await get_db()
    async with db.execute(
        "SELECT master_id FROM requests WHERE id=?",
        (request_id,),
    ) as c:
        row = await c.fetchone()
    if row is None:
        await db.close()
        return None
    master_id = row[0]
    await db.execute(
        "UPDATE requests SET status='done' WHERE id=?",
        (request_id,),
    )
    if master_id is not None:
        await db.execute(
            "UPDATE masters SET active_orders=active_orders-1, has_debt=1 "
            "WHERE telegram_id=? AND active_orders>0",
            (master_id,),
        )
    await db.commit()
    await db.close()
    return master_id

async def pay_commission(master_id: int):
    db = await get_db()
    await db.execute(
        "UPDATE masters SET has_debt=0 WHERE telegram_id=?",
        (master_id,)
    )
    await db.commit()
    await db.close()


async def list_master_requests(master_id: int):
    """Вернуть все незакрытые заявки мастера."""
    db = await get_db()
    async with db.execute(
        "SELECT id, status, description, created_at "
        "FROM requests "
        "WHERE master_id=? AND status!='done' "
        "ORDER BY created_at DESC",
        (master_id,),
    ) as cursor:
        rows = await cursor.fetchall()
    await db.close()
    return rows


async def get_master_by_id(telegram_id: int):
    """
    Вернёт запись мастера:
    (id, telegram_id, username, active_orders, has_debt, is_active, created_at)
    или None, если нет такого.
    """
    db = await get_db()
    async with db.execute(
        "SELECT * FROM masters WHERE telegram_id = ?",
        (telegram_id,)
    ) as cursor:
        row = await cursor.fetchone()
    await db.close()
    return row

async def get_request_by_id(request_id: int):
    """
    Вернёт запись заявки (см. схему таблицы).
    """
    db = await get_db()
    async with db.execute(
        "SELECT * FROM requests WHERE id = ?",
        (request_id,)
    ) as cursor:
        row = await cursor.fetchone()
    await db.close()
    return row

async def wait_client_confirmation(request_id: int, master_id: int):
    """Помечаем заявку как ожидающую подтверждения клиента."""
    db = await get_db()
    await db.execute(
        "UPDATE requests SET status='await_client' "
        "WHERE id=? AND master_id=?",
        (request_id, master_id),
    )
    await db.commit()
    await db.close()


async def add_review(request_id: int, master_id: int, client_id: int,
                     rating: int, comment: str | None):
    db = await get_db()
    await db.execute(
        "INSERT INTO reviews (request_id, master_id, client_id, rating, comment) "
        "VALUES (?, ?, ?, ?, ?)",
        (request_id, master_id, client_id, rating, comment),
    )
    # при желании обновим средний рейтинг мастера
    await db.execute(
        "UPDATE masters "
        "SET rating = (SELECT AVG(rating) FROM reviews WHERE master_id = ?) "
        "WHERE telegram_id = ?",
        (master_id, master_id),
    )
    await db.commit()
    await db.close()


# ───── админы ─────────────────────────────────────────────
async def add_admin(telegram_id: int):
    db = await get_db()
    await db.execute("INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)",
                     (telegram_id,))
    await db.commit(); await db.close()

async def is_admin(telegram_id: int) -> bool:
    db = await get_db()
    async with db.execute("SELECT 1 FROM admins WHERE telegram_id=?", (telegram_id,)) as c:
        row = await c.fetchone()
    await db.close()
    return row is not None

async def list_admins() -> list[int]:
    db = await get_db()
    async with db.execute("SELECT telegram_id FROM admins") as c:
        rows = await c.fetchall()
    await db.close()
    return [r[0] for r in rows]

async def block_master(telegram_id: int):
    db = await get_db()
    await db.execute("UPDATE masters SET is_active = 0 WHERE telegram_id=?", (telegram_id,))
    await db.commit(); await db.close()

async def unblock_master(telegram_id: int):
    db = await get_db()
    await db.execute(
        "UPDATE masters SET is_active = 1 WHERE telegram_id=?",
        (telegram_id,),
    )
    await db.commit(); await db.close()

async def list_all_requests(limit: int = 30):
    db = await get_db()
    async with db.execute(
        "SELECT id, status, username, description, created_at "
        "FROM requests ORDER BY created_at DESC LIMIT ?", (limit,)
    ) as c:
        rows = await c.fetchall()
    await db.close()
    return rows


async def list_recent_reviews(limit: int = 10):
    """Вернуть последние отзывы с указанием мастера и заявки."""
    db = await get_db()
    async with db.execute(
        """
        SELECT reviews.request_id, reviews.rating, reviews.comment,
               COALESCE(masters.full_name, '')
        FROM reviews
        LEFT JOIN masters ON reviews.master_id = masters.telegram_id
        ORDER BY reviews.created_at DESC LIMIT ?
        """,
        (limit,),
    ) as c:
        rows = await c.fetchall()
    await db.close()
    return rows
