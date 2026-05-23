"""Модуль для работы с SQLite базой данных."""
from __future__ import annotations

import aiosqlite
from config import DB_PATH


# ─────────────────────────── Инициализация ────────────────────────────────

async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id   INTEGER UNIQUE NOT NULL,
                username      TEXT,
                name          TEXT,
                phone         TEXT,
                email         TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cart (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, course_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id               INTEGER NOT NULL,
                status                TEXT    DEFAULT 'new',
                payment_link          TEXT,
                payment_screenshot_id TEXT,
                total_price           INTEGER,
                working_admin_id      INTEGER,
                created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id    INTEGER NOT NULL,
                course_id   INTEGER NOT NULL,
                course_name TEXT    NOT NULL,
                price       INTEGER NOT NULL,
                course_link TEXT,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_messages (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id      INTEGER NOT NULL,
                admin_chat_id INTEGER NOT NULL,
                message_id    INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS course_accesses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                course_id   INTEGER NOT NULL,
                course_name TEXT    NOT NULL,
                course_link TEXT    NOT NULL,
                order_id    INTEGER,
                granted_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


# ─────────────────────────── Пользователи ─────────────────────────────────

async def get_user(telegram_id: int) -> aiosqlite.Row | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        return await cur.fetchone()


async def create_user(
    telegram_id: int, username: str, name: str, phone: str, email: str
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (telegram_id, username, name, phone, email)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET
                 username = excluded.username,
                 name     = excluded.name,
                 phone    = excluded.phone,
                 email    = excluded.email""",
            (telegram_id, username, name, phone, email),
        )
        await db.commit()


async def get_user_by_id(user_id: int) -> aiosqlite.Row | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return await cur.fetchone()


# ─────────────────────────── Корзина ──────────────────────────────────────

async def get_cart(user_db_id: int) -> list[int]:
    """Возвращает список course_id из корзины пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT course_id FROM cart WHERE user_id = ?", (user_db_id,)
        )
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def add_to_cart(user_db_id: int, course_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO cart (user_id, course_id) VALUES (?, ?)",
                (user_db_id, course_id),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def remove_from_cart(user_db_id: int, course_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM cart WHERE user_id = ? AND course_id = ?",
            (user_db_id, course_id),
        )
        await db.commit()


async def clear_cart(user_db_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart WHERE user_id = ?", (user_db_id,))
        await db.commit()


# ─────────────────────────── Заказы ───────────────────────────────────────

async def create_order(user_db_id: int, total_price: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO orders (user_id, total_price) VALUES (?, ?)",
            (user_db_id, total_price),
        )
        await db.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def add_order_item(
    order_id: int, course_id: int, course_name: str, price: int, course_link: str
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO order_items
               (order_id, course_id, course_name, price, course_link)
               VALUES (?, ?, ?, ?, ?)""",
            (order_id, course_id, course_name, price, course_link),
        )
        await db.commit()


async def get_order(order_id: int) -> aiosqlite.Row | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        return await cur.fetchone()


async def get_order_items(order_id: int) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
        )
        return await cur.fetchall()


async def get_user_orders(user_db_id: int) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
            (user_db_id,),
        )
        return await cur.fetchall()


async def get_all_active_orders() -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT * FROM orders
               WHERE status NOT IN ('completed', 'cancelled')
               ORDER BY created_at DESC"""
        )
        return await cur.fetchall()


async def update_order_status(order_id: int, status: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET status = ? WHERE id = ?", (status, order_id)
        )
        await db.commit()


async def update_order_payment_link(order_id: int, payment_link: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET payment_link = ?, status = 'waiting_payment' WHERE id = ?",
            (payment_link, order_id),
        )
        await db.commit()


async def update_order_screenshot(order_id: int, screenshot_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE orders
               SET payment_screenshot_id = ?, status = 'payment_received'
               WHERE id = ?""",
            (screenshot_id, order_id),
        )
        await db.commit()


async def set_working_admin(order_id: int, admin_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET working_admin_id = ? WHERE id = ?",
            (admin_id, order_id),
        )
        await db.commit()


# ─────────────────────── Сообщения администраторов ────────────────────────

async def save_admin_message(
    order_id: int, admin_chat_id: int, message_id: int
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO admin_messages (order_id, admin_chat_id, message_id)
               VALUES (?, ?, ?)""",
            (order_id, admin_chat_id, message_id),
        )
        await db.commit()


async def get_admin_messages(order_id: int) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM admin_messages WHERE order_id = ?", (order_id,)
        )
        return await cur.fetchall()


async def delete_admin_messages(order_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM admin_messages WHERE order_id = ?", (order_id,)
        )
        await db.commit()


# ─────────────────────────── Доступы к курсам ─────────────────────────────

async def grant_access(
    user_db_id: int,
    course_id: int,
    course_name: str,
    course_link: str,
    order_id: int,
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO course_accesses
               (user_id, course_id, course_name, course_link, order_id)
               VALUES (?, ?, ?, ?, ?)""",
            (user_db_id, course_id, course_name, course_link, order_id),
        )
        await db.commit()


async def get_user_accesses(user_db_id: int) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT * FROM course_accesses
               WHERE user_id = ?
               ORDER BY granted_at DESC""",
            (user_db_id,),
        )
        return await cur.fetchall()
