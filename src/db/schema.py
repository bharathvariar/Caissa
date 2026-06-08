from .connection import get_connection

CREATE_GAMES = """
CREATE TABLE IF NOT EXISTS games (
    uuid            TEXT PRIMARY KEY,
    url             TEXT NOT NULL,
    end_time        INTEGER NOT NULL,
    time_class      TEXT NOT NULL,
    time_control    TEXT NOT NULL,
    rated           INTEGER NOT NULL,
    white_username  TEXT NOT NULL,
    white_rating    INTEGER NOT NULL,
    white_result    TEXT NOT NULL,
    black_username  TEXT NOT NULL,
    black_rating    INTEGER NOT NULL,
    black_result    TEXT NOT NULL,
    white_accuracy  REAL,
    black_accuracy  REAL,
    eco_url         TEXT,
    pgn             TEXT NOT NULL
);
"""


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(CREATE_GAMES)
