# database.py
# Работа с SQLite. Все функции асинхронные.

import os
import aiosqlite
from datetime import datetime

from config import DB_PATH

# Создаём папку data/, если её нет
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


async def init_db() -> None:
    """Создаёт таблицы items и orders, если их ещё нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Товары
        await db.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                description TEXT NOT NULL,
                price       TEXT NOT NULL,
                photo_url   TEXT
            )
        """)
        # Заявки
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id      INTEGER NOT NULL,
                client_name  TEXT NOT NULL,
                client_phone TEXT NOT NULL,
                created_at   TIMESTAMP NOT NULL
            )
        """)
        await db.commit()


# ---------- Товары ----------
async def add_item(name: str, description: str, price: str, photo_url: str | None) -> int:
    """Добавляет товар. Возвращает его ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO items (name, description, price, photo_url) VALUES (?, ?, ?, ?)",
            (name, description, price, photo_url),
        )
        await db.commit()
        return cur.lastrowid


async def get_all_items() -> list[tuple]:
    """Все товары: список кортежей (id, name, description, price, photo_url)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, name, description, price, photo_url FROM items ORDER BY id"
        )
        return await cur.fetchall()


async def get_item(item_id: int) -> tuple | None:
    """Один товар по ID или None."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, name, description, price, photo_url FROM items WHERE id = ?",
            (item_id,),
        )
        return await cur.fetchone()


async def delete_item(item_id: int) -> bool:
    """Удаляет товар. Возвращает True, если был найден."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM items WHERE id = ?", (item_id,))
        await db.commit()
        return cur.rowcount > 0


# ---------- Заявки ----------
async def add_order(item_id: int, client_name: str, client_phone: str) -> int:
    """Создаёт заявку. Возвращает её ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO orders (item_id, client_name, client_phone, created_at) "
            "VALUES (?, ?, ?, ?)",
            (item_id, client_name, client_phone,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        await db.commit()
        return cur.lastrowid