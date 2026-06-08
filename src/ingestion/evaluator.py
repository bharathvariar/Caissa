import io
import shutil
import time
import psutil
import chess
import chess.engine
import chess.pgn

from src.db.connection import get_connection
from src.db.schema import init_db

_stockfish_bin = shutil.which("stockfish")
if _stockfish_bin is None:
    raise EnvironmentError("stockfish binary not found on PATH — install it with: brew install stockfish")

DEPTH = 15
_CP_THRESHOLDS = {"blunder": 200, "mistake": 100, "inaccuracy": 50}

_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_RESET = "\033[0m"

INSERT_MOVE = """
INSERT OR IGNORE INTO move_evaluations
    (game_uuid, move_number, side, uci, cp_score, best_uci, classification)
VALUES
    (:game_uuid, :move_number, :side, :uci, :cp_score, :best_uci, :classification)
"""

INSERT_GAME_EVAL = """
INSERT OR REPLACE INTO game_evaluations
    (game_uuid, username, blunders, mistakes, inaccuracies, avg_centipawn_loss, sharpest_cp_swing)
VALUES
    (:game_uuid, :username, :blunders, :mistakes, :inaccuracies, :avg_centipawn_loss, :sharpest_cp_swing)
"""


def _cpu_indicator() -> str:
    cpu = psutil.cpu_percent(interval=0.1)
    if cpu < 50:
        color = _GREEN
    elif cpu < 80:
        color = _YELLOW
    else:
        color = _RED
    return f"{color}CPU {cpu:.0f}%{_RESET}"


def _fmt_duration(seconds: float, precise: bool = False) -> str:
    if precise:
        h, remainder = divmod(seconds, 3600)
        m, s = divmod(remainder, 60)
        ms = (seconds % 1) * 1000
        if h:
            return f"{int(h)}h {int(m):02d}m {int(s):02d}.{int(ms):03d}s"
        if m:
            return f"{int(m)}m {int(s):02d}.{int(ms):03d}s"
        return f"{int(s)}.{int(ms):03d}s"
    whole = int(seconds)
    h, remainder = divmod(whole, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def _classify(cp_loss: int) -> str:
    """
    Map a centipawn loss to a move quality label.

    Args:
        cp_loss (int): Absolute centipawn drop caused by a move.

    Returns:
        str: One of 'blunder', 'mistake', 'inaccuracy', or 'good'.
    """
    if cp_loss >= _CP_THRESHOLDS["blunder"]:
        return "blunder"
    if cp_loss >= _CP_THRESHOLDS["mistake"]:
        return "mistake"
    if cp_loss >= _CP_THRESHOLDS["inaccuracy"]:
        return "inaccuracy"
    return "good"


def _score_to_cp(score: chess.engine.PovScore) -> int:
    """
    Convert an engine PovScore to a centipawn integer from white's perspective.

    Caps mate scores at ±10000 so arithmetic stays bounded.

    Args:
        score (chess.engine.PovScore): Raw score returned by Stockfish.

    Returns:
        int: Centipawn value from white's perspective.
    """
    white_score = score.white()
    if white_score.is_mate():
        return 10000 if white_score.mate() > 0 else -10000
    return white_score.score()


def _evaluate_game(
    engine: chess.engine.SimpleEngine,
    game_uuid: str,
    pgn_text: str,
    username: str,
) -> tuple[list[dict], dict]:
    """
    Run Stockfish on every position in a game and return per-move and per-game rows.

    Uses a two-pass approach: pass 1 collects cp_before for every position;
    pass 2 computes cp_loss for the player's moves using consecutive evaluations.

    Args:
        engine (chess.engine.SimpleEngine): Running Stockfish engine instance.
        game_uuid (str): UUID of the game from the games table.
        pgn_text (str): Full PGN string for the game.
        username (str): Player whose moves are classified.

    Returns:
        tuple[list[dict], dict]: (move_rows for move_evaluations, row for game_evaluations).
            Returns ([], {}) if the PGN cannot be parsed.
    """
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return [], {}

    white_name = game.headers.get("White", "")
    player_side = chess.WHITE if white_name.lower() == username.lower() else chess.BLACK
    player_color_str = "white" if player_side == chess.WHITE else "black"

    # Pass 1: evaluate every position before the move is played.
    board = game.board()
    raw: list[dict] = []
    for node in game.mainline():
        move = node.move
        info = engine.analyse(board, chess.engine.Limit(depth=DEPTH))
        pv_move = info.get("pv", [None])[0]
        raw.append({
            "move_number": board.fullmove_number,
            "side": "white" if board.turn == chess.WHITE else "black",
            "uci": move.uci(),
            "cp_before": _score_to_cp(info["score"]),
            "best_uci": pv_move.uci() if pv_move else None,
        })
        board.push(move)

    # Pass 2: compute cp_loss for the player's moves.
    # cp_loss = how much worse the position became vs the best available move.
    # For white: loss = cp_before[i] - cp_before[i+1]  (white wants high cp)
    # For black: loss = cp_before[i+1] - cp_before[i]  (black wants low cp)
    move_rows: list[dict] = []
    blunders = mistakes = inaccuracies = 0
    cp_losses: list[int] = []
    cp_swings: list[int] = []

    for i, ev in enumerate(raw):
        cp_loss = 0
        classification = "good"

        if ev["side"] == player_color_str and i + 1 < len(raw):
            cp_before = ev["cp_before"]
            cp_after = raw[i + 1]["cp_before"]
            swing = abs(cp_after - cp_before)
            cp_swings.append(swing)

            if player_side == chess.WHITE:
                cp_loss = max(0, cp_before - cp_after)
            else:
                cp_loss = max(0, cp_after - cp_before)

            classification = _classify(cp_loss)
            cp_losses.append(cp_loss)
            if classification == "blunder":
                blunders += 1
            elif classification == "mistake":
                mistakes += 1
            elif classification == "inaccuracy":
                inaccuracies += 1

        move_rows.append({
            "game_uuid": game_uuid,
            "move_number": ev["move_number"],
            "side": ev["side"],
            "uci": ev["uci"],
            "cp_score": ev["cp_before"],
            "best_uci": ev["best_uci"],
            "classification": classification,
        })

    avg_loss = round(sum(cp_losses) / len(cp_losses), 1) if cp_losses else None
    sharpest = max(cp_swings) if cp_swings else None

    game_eval = {
        "game_uuid": game_uuid,
        "username": username,
        "blunders": blunders,
        "mistakes": mistakes,
        "inaccuracies": inaccuracies,
        "avg_centipawn_loss": avg_loss,
        "sharpest_cp_swing": sharpest,
    }
    return move_rows, game_eval


def evaluate_user(username: str, limit: int | None = None) -> None:
    """
    Run Stockfish evaluation on all un-evaluated games for a user.

    Reads PGNs from the games table, skips games already in game_evaluations,
    and writes results to move_evaluations and game_evaluations.

    Args:
        username (str): Chess.com username to evaluate.
        limit (int | None): Cap the number of games to process. None means all.

    Returns:
        None
    """
    init_db()

    with get_connection() as conn:
        already_done = {
            r["game_uuid"]
            for r in conn.execute(
                "SELECT game_uuid FROM game_evaluations WHERE username = ?", (username,)
            ).fetchall()
        }
        all_rows = conn.execute(
            """
            SELECT uuid, pgn FROM games
            WHERE white_username = ? OR black_username = ?
            ORDER BY end_time DESC
            """,
            (username, username),
        ).fetchall()

    games_to_eval = [r for r in all_rows if r["uuid"] not in already_done]
    if limit is not None:
        games_to_eval = games_to_eval[:limit]

    total = len(games_to_eval)
    if total == 0:
        print("[INFO] No new games to evaluate.")
        return

    print(f"[INFO] Evaluating {total} games for {username} at depth {DEPTH}\n")

    start = time.monotonic()
    with chess.engine.SimpleEngine.popen_uci(_stockfish_bin) as engine:
        with get_connection() as conn:
            for i, row in enumerate(games_to_eval, 1):
                game_start = time.monotonic()
                move_rows, game_eval = _evaluate_game(engine, row["uuid"], row["pgn"], username)
                if not game_eval:
                    continue
                conn.executemany(INSERT_MOVE, move_rows)
                conn.execute(INSERT_GAME_EVAL, game_eval)

                elapsed = time.monotonic() - start
                game_time = time.monotonic() - game_start
                eta = (elapsed / i) * (total - i)

                blunders_str = f"{_RED}{game_eval['blunders']}B{_RESET}"
                mistakes_str = f"{_YELLOW}{game_eval['mistakes']}M{_RESET}"
                inaccuracies_str = f"{_GREEN}{game_eval['inaccuracies']}I{_RESET}"
                avg_loss = game_eval["avg_centipawn_loss"] or 0

                print(
                    f"[{i:>5}/{total}] {round(i / total * 100):>3}% | "
                    f"{blunders_str} {mistakes_str} {inaccuracies_str} | "
                    f"avg_loss={avg_loss:.1f} | "
                    f"{game_time:.1f}s/game | "
                    f"elapsed {_fmt_duration(elapsed)} | "
                    f"ETA {_fmt_duration(eta)} | "
                    f"{_cpu_indicator()}"
                )

    total_elapsed = time.monotonic() - start
    print(f"\n[DONE] {total} games in {_fmt_duration(total_elapsed)}")


if __name__ == "__main__":
    import sys

    username = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    evaluate_user(username, limit=limit)
