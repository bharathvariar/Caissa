import sqlite3
from pathlib import Path

DB_PATH = Path("data/caissa.db")


def get_connection() -> sqlite3.Connection:
    """
    Open a connection to the SQLite database.

    Creates data/caissa.db and its parent directory if they do not exist.
    Sets row_factory so columns can be accessed by name.

    Returns:
        sqlite3.Connection: Open database connection.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn
