
"""
database.py - everything that talks to SQLite.

All SQL operations belong in this module.
Other modules should call these functions instead of writing SQL.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

from src import config


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    description TEXT NOT NULL CHECK (length(trim(description)) > 0),
    amount      REAL NOT NULL CHECK (amount > 0),
    type        TEXT NOT NULL CHECK (type IN ('income', 'expense')),
    category    TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_transactions_date
ON transactions (date);
"""


@contextmanager
def get_connection(db_path=None):
    """Open a SQLite connection and commit or roll back safely."""
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path=None):
    """
    Create the required tables and safely migrate older databases.

    Existing transactions receive a nullable user_id column.
    They are assigned to the first registered account when that
    account is created, not to every subsequently registered user.
    """
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        
        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(transactions)"
            ).fetchall()
        }

        if "user_id" not in columns:
            conn.execute(
                "ALTER TABLE transactions ADD COLUMN user_id INTEGER "
                "REFERENCES users(id)"
            )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_transactions_user_date
            ON transactions (user_id, date)
            """
        )


def create_user(name, email, password_hash, db_path=None):
    """
    Create a registered user.

    If this is the first account, assign existing unowned transactions
    to that account. Later accounts never receive those legacy rows.

    Returns the new user ID, or None if the email already exists.
    """
    name = str(name).strip()
    email = str(email).strip().lower()
    password_hash = str(password_hash)

    if not name or not email or not password_hash:
        raise ValueError("Name, email, and password hash are required.")

    with get_connection(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        if existing:
            return None

        user_count = conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        cursor = conn.execute(
            """
            INSERT INTO users (name, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (name, email, password_hash),
        )

        user_id = cursor.lastrowid

        if user_count == 0:
            conn.execute(
                "UPDATE transactions SET user_id = ? WHERE user_id IS NULL",
                (user_id,),
            )

        return user_id


def get_user_by_email(email, db_path=None):
    """Find a user by email; return a dictionary or None."""
    email = str(email).strip().lower()

    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, name, email, password_hash, created_at
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()

    if row is None:
        return None

    return dict(row) if isinstance(row, sqlite3.Row) else {
        "id": row[0],
        "name": row[1],
        "email": row[2],
        "password_hash": row[3],
        "created_at": row[4],
    }


def get_user_by_id(user_id, db_path=None):
    """Find a user by ID; return a dictionary or None."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, name, email, created_at
            FROM users
            WHERE id = ?
            """,
            (int(user_id),),
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "name": row[1],
        "email": row[2],
        "created_at": row[3],
    }


def add_transaction(txn, db_path=None, user_id=None):
    """
    Save a validated transaction.

    Application code must supply the authenticated user's ID.
    user_id=None remains available for legacy tests and utilities.
    """
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO transactions
                (date, description, amount, type, category, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                txn["date"].isoformat(),
                txn["description"],
                round(float(txn["amount"]), 2),
                txn["type"],
                txn["category"],
                user_id,
            ),
        )

        return cursor.lastrowid


def add_transactions_batch(txns, db_path=None, user_id=None):
    """Insert a batch atomically, assigning every row to the supplied user."""
    if not txns:
        return 0

    rows = [
        (
            txn["date"].isoformat(),
            txn["description"],
            round(float(txn["amount"]), 2),
            txn["type"],
            txn["category"],
            user_id,
        )
        for txn in txns
    ]

    with get_connection(db_path) as conn:
        cursor = conn.executemany(
            """
            INSERT INTO transactions
                (date, description, amount, type, category, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

        return cursor.rowcount


def get_transactions(db_path=None, user_id=None):
    """
    Return transactions newest first.

    When user_id is supplied, return only that user's transactions.
    The unscoped form is retained for existing tests and maintenance
    utilities; application pages must always supply user_id.
    """
    with get_connection(db_path) as conn:
        if user_id is None:
            df = pd.read_sql_query(
                """
                SELECT id, date, description, amount, type, category
                FROM transactions
                ORDER BY date DESC, id DESC
                """,
                conn,
            )
        else:
            df = pd.read_sql_query(
                """
                SELECT id, date, description, amount, type, category
                FROM transactions
                WHERE user_id = ?
                ORDER BY date DESC, id DESC
                """,
                conn,
                params=(int(user_id),),
            )

    df["date"] = pd.to_datetime(df["date"])
    return df


def delete_transaction(transaction_id, db_path=None, user_id=None):
    """
    Delete a transaction.

    Supplying user_id ensures a user cannot delete another user's row.
    """
    with get_connection(db_path) as conn:
        if user_id is None:
            cursor = conn.execute(
                "DELETE FROM transactions WHERE id = ?",
                (int(transaction_id),),
            )
        else:
            cursor = conn.execute(
                """
                DELETE FROM transactions
                WHERE id = ? AND user_id = ?
                """,
                (int(transaction_id), int(user_id)),
            )

        return cursor.rowcount > 0


def delete_sample_transactions(db_path=None, user_id=None):
    """Delete sample transactions, optionally restricted to one user."""
    with get_connection(db_path) as conn:
        if user_id is None:
            cursor = conn.execute(
                """
                DELETE FROM transactions
                WHERE substr(description, 1, ?) = ?
                """,
                (len(config.SAMPLE_PREFIX), config.SAMPLE_PREFIX),
            )
        else:
            cursor = conn.execute(
                """
                DELETE FROM transactions
                WHERE substr(description, 1, ?) = ?
                  AND user_id = ?
                """,
                (
                    len(config.SAMPLE_PREFIX),
                    config.SAMPLE_PREFIX,
                    int(user_id),
                ),
            )

        return cursor.rowcount