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

CREATE_MOVE_EVALUATIONS = """
CREATE TABLE IF NOT EXISTS move_evaluations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_uuid       TEXT NOT NULL REFERENCES games(uuid),
    move_number     INTEGER NOT NULL,
    side            TEXT NOT NULL,
    uci             TEXT NOT NULL,
    cp_score        INTEGER,
    best_uci        TEXT,
    classification  TEXT NOT NULL
);
"""

CREATE_GAME_EVALUATIONS = """
CREATE TABLE IF NOT EXISTS game_evaluations (
    game_uuid           TEXT PRIMARY KEY REFERENCES games(uuid),
    username            TEXT NOT NULL,
    blunders            INTEGER NOT NULL DEFAULT 0,
    mistakes            INTEGER NOT NULL DEFAULT 0,
    inaccuracies        INTEGER NOT NULL DEFAULT 0,
    avg_centipawn_loss  REAL,
    sharpest_cp_swing   INTEGER
);
"""


def init_db() -> None:
    """
    Create database tables if they do not already exist.

    Safe to call on every application startup — uses CREATE TABLE IF NOT EXISTS.

    Returns:
        None
    """
    with get_connection() as conn:
        conn.execute(CREATE_GAMES)
        conn.execute(CREATE_MOVE_EVALUATIONS)
        conn.execute(CREATE_GAME_EVALUATIONS)
