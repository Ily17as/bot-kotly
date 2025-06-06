import aiosqlite
from app.config import DB_PATH

async def get_db():
    return await aiosqlite.connect(DB_PATH)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT
            )
        """
        )

        # Таблица мастеров
        await db.execute("""
                    CREATE TABLE IF NOT EXISTS masters (
                        id               INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_id      INTEGER UNIQUE,
                        username         TEXT,
                        full_name        TEXT,
                        phone            TEXT,
                        active_orders    INTEGER DEFAULT 0,
                        has_debt         BOOLEAN DEFAULT 0,
                        is_active        BOOLEAN DEFAULT 1,
                        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        rating           REAL DEFAULT 0
                    )
                """)

        # Таблица заявок с расширенной схемой
        await db.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                description TEXT,
                settlement TEXT,
                location TEXT,
                latitude     REAL,
                longitude    REAL,
                media_id TEXT,
                media_type TEXT,
                status TEXT DEFAULT 'open',
                master_id INTEGER,
                commission_paid BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
                    CREATE TABLE IF NOT EXISTS reviews (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        request_id  INTEGER,          -- по какой заявке
                        master_id   INTEGER,
                        client_id   INTEGER,
                        rating      INTEGER,          -- 1-5
                        comment     TEXT,             -- NULL, если клиент пропустил
                        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

        await db.execute("""
                            CREATE TABLE IF NOT EXISTS admins(
                                telegram_id INTEGER PRIMARY KEY
                            )
                        """)

        await db.commit()

