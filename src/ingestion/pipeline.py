"""
Batch evaluation + indexing pipeline.

Evaluates games with Stockfish in batches, and indexes each completed batch
into Qdrant while the next batch is being evaluated — overlapping CPU-bound
evaluation with IO-bound embedding.

Usage:
    python -m src.ingestion.pipeline <username> [--batch-size N] [--limit N]
"""
import queue
import sys
import threading
import time

import chess.engine

from src.coach.store import index_games
from src.db.connection import get_connection
from src.db.schema import init_db
from src.ingestion.evaluator import (
    INSERT_GAME_EVAL,
    INSERT_MOVE,
    _evaluate_game,
    _fmt_duration,
    _cpu_indicator,
    _stockfish_bin,
)

_SENTINEL = None


def _eval_worker(
    username: str,
    batches: list[list],
    batch_queue: queue.Queue,
) -> None:
    """
    Evaluate each batch with Stockfish and push the completed UUID list to the queue.

    Args:
        username (str): Player being evaluated.
        batches (list[list]): List of batches, each a list of game rows.
        batch_queue (queue.Queue): Queue shared with the indexer thread.

    Returns:
        None
    """
    total_batches = len(batches)
    with chess.engine.SimpleEngine.popen_uci(_stockfish_bin) as engine:
        with get_connection() as conn:
            for b_idx, batch in enumerate(batches, 1):
                batch_size = len(batch)
                batch_start = time.monotonic()
                print(f"\n[EVAL   ] Batch {b_idx}/{total_batches} — {batch_size} games", flush=True)
                uuids = []
                for i, row in enumerate(batch, 1):
                    move_rows, game_eval = _evaluate_game(engine, row["uuid"], row["pgn"], username)
                    if not game_eval:
                        continue
                    conn.executemany(INSERT_MOVE, move_rows)
                    conn.execute(INSERT_GAME_EVAL, game_eval)
                    uuids.append(row["uuid"])

                    elapsed = time.monotonic() - batch_start
                    eta = (elapsed / i) * (batch_size - i)
                    filled = int(20 * i / batch_size)
                    bar = "█" * filled + "░" * (20 - filled)
                    print(
                        f"\r  [{bar}] {i}/{batch_size} | "
                        f"{elapsed / i:.1f}s/game | "
                        f"ETA {_fmt_duration(eta)} | "
                        f"{_cpu_indicator()}   ",
                        end="",
                        flush=True,
                    )

                elapsed = _fmt_duration(time.monotonic() - batch_start)
                print(f"\n[EVAL   ] Batch {b_idx}/{total_batches} done in {elapsed}", flush=True)
                batch_queue.put((b_idx, uuids))

    batch_queue.put(_SENTINEL)


def _index_worker(
    username: str,
    total_batches: int,
    batch_queue: queue.Queue,
) -> None:
    """
    Index each batch from the queue into Qdrant as soon as it is available.

    Args:
        username (str): Player being indexed.
        total_batches (int): Total number of batches, used for log labels.
        batch_queue (queue.Queue): Queue shared with the evaluator thread.

    Returns:
        None
    """
    while True:
        item = batch_queue.get()
        if item is _SENTINEL:
            break
        b_idx, uuids = item
        index_start = time.monotonic()
        print(f"\n[INDEX  ] Batch {b_idx}/{total_batches} — indexing {len(uuids)} games", flush=True)
        index_games(username, uuids)
        elapsed = _fmt_duration(time.monotonic() - index_start)
        print(f"[INDEX  ] Batch {b_idx}/{total_batches} done in {elapsed}", flush=True)


def run_pipeline(username: str, batch_size: int = 100, limit: int | None = None) -> None:
    """
    Run the full evaluation + indexing pipeline for a user.

    Stockfish evaluation and Qdrant indexing overlap: while batch N is being
    evaluated, batch N-1 is being indexed. Each batch is written to SQLite
    before being handed to the indexer, so progress survives interruption.

    Args:
        username (str): Chess.com username to process.
        batch_size (int): Number of games per batch. Defaults to 100.
        limit (int | None): Total games to process. None means all pending.

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

    pending = [r for r in all_rows if r["uuid"] not in already_done]
    if limit is not None:
        pending = pending[:limit]

    if not pending:
        print("[INFO] No new games to evaluate.")
        return

    batches = [pending[i : i + batch_size] for i in range(0, len(pending), batch_size)]
    total_batches = len(batches)

    print(
        f"[PIPELINE] {len(pending)} games | batch size {batch_size} | {total_batches} batches\n",
        flush=True,
    )

    batch_queue: queue.Queue = queue.Queue(maxsize=1)
    pipeline_start = time.perf_counter()

    eval_thread = threading.Thread(
        target=_eval_worker,
        args=(username, batches, batch_queue),
        daemon=False,
    )
    index_thread = threading.Thread(
        target=_index_worker,
        args=(username, total_batches, batch_queue),
        daemon=False,
    )

    eval_thread.start()
    index_thread.start()
    eval_thread.join()
    index_thread.join()

    total_elapsed = _fmt_duration(time.perf_counter() - pipeline_start, precise=True)
    print(f"\n[PIPELINE] Done — {len(pending)} games evaluated + indexed in {total_elapsed}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.ingestion.pipeline <username> [--batch-size N] [--limit N]")
        sys.exit(1)

    username = sys.argv[1]
    batch_size = 100
    limit = None

    args = sys.argv[2:]
    for i, arg in enumerate(args):
        if arg == "--batch-size" and i + 1 < len(args):
            batch_size = int(args[i + 1])
        elif arg == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])

    run_pipeline(username, batch_size=batch_size, limit=limit)
