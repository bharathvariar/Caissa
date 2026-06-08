import json
from pathlib import Path

from src.db.connection import get_connection
from src.db.schema import init_db

INSERT_GAME = """
INSERT OR IGNORE INTO games (
    uuid, url, end_time, time_class, time_control, rated,
    white_username, white_rating, white_result,
    black_username, black_rating, black_result,
    white_accuracy, black_accuracy, eco_url, pgn
) VALUES (
    :uuid, :url, :end_time, :time_class, :time_control, :rated,
    :white_username, :white_rating, :white_result,
    :black_username, :black_rating, :black_result,
    :white_accuracy, :black_accuracy, :eco_url, :pgn
)
"""


def _parse_game(game: dict) -> dict:
    """
    Extract and flatten fields from a raw Chess.com game object.

    Accuracies are optional — Chess.com omits them for some games.

    Args:
        game (dict): Raw game object from a Chess.com archive response.

    Returns:
        dict: Flat dict matching the games table column names.
    """
    accuracies = game.get("accuracies", {})
    return {
        "uuid": game["uuid"],
        "url": game["url"],
        "end_time": game["end_time"],
        "time_class": game["time_class"],
        "time_control": game["time_control"],
        "rated": int(game["rated"]),
        "white_username": game["white"]["username"],
        "white_rating": game["white"]["rating"],
        "white_result": game["white"]["result"],
        "black_username": game["black"]["username"],
        "black_rating": game["black"]["rating"],
        "black_result": game["black"]["result"],
        "white_accuracy": accuracies.get("white"),
        "black_accuracy": accuracies.get("black"),
        "eco_url": game.get("eco"),
        "pgn": game["pgn"],
    }


def normalize_user(username: str) -> None:
    """
    Parse all raw archives for a user and upsert games into SQLite.

    Reads every JSON file under data/users/{username}/raw/, parses each game,
    and inserts it using INSERT OR IGNORE — safe to re-run without duplicating rows.

    Args:
        username (str): Chess.com username whose raw archives to normalize.

    Returns:
        None
    """
    init_db()
    raw_dir = Path(f"data/users/{username}/raw")
    files = sorted(raw_dir.glob("*.json"))
    print(f"[INFO] Normalizing {len(files)} archive files for {username}")

    total_inserted = 0
    with get_connection() as conn:
        for path in files:
            data = json.loads(path.read_text())
            rows = [_parse_game(g) for g in data.get("games", [])]
            conn.executemany(INSERT_GAME, rows)
            total_inserted += len(rows)
            print(f"[OK] {path.name}: {len(rows)} games")

    print(f"[DONE] {total_inserted} games written to DB")


if __name__ == "__main__":
    import sys
    normalize_user(sys.argv[1])
