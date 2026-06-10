from datetime import datetime, timezone

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from src.db.connection import get_connection
from .embedder import embed

COLLECTION = "games"
VECTOR_SIZE = 768
QDRANT_PATH = "data/qdrant"

_DRAW_RESULTS = {"agreed", "stalemate", "insufficient", "repetition", "50move", "timevsinsufficient"}


def _get_client() -> QdrantClient:
    """
    Create a Qdrant client backed by local disk storage.

    Returns:
        QdrantClient: Client connected to data/qdrant.
    """
    return QdrantClient(path=QDRANT_PATH)


def _compute_outcome(result: str) -> str:
    """
    Normalise a Chess.com result string into win / draw / loss.

    Args:
        result (str): Raw result value from the games table (e.g. 'resigned', 'win').

    Returns:
        str: One of 'win', 'draw', or 'loss'.
    """
    if result == "win":
        return "win"
    if result in _DRAW_RESULTS:
        return "draw"
    return "loss"


def _game_to_text(game: dict, username: str) -> str:
    """
    Convert a game row into a plain English sentence for embedding.

    Describes the date, sides, ratings, result, opening, time class,
    accuracy (if available), and Stockfish evaluation (if available).

    Args:
        game (dict): Row from games LEFT JOIN game_evaluations as a dict.
        username (str): The player whose perspective to use.

    Returns:
        str: Plain English description of the game.
    """
    date = datetime.fromtimestamp(game["end_time"], tz=timezone.utc).strftime("%Y-%m-%d")
    side = "white" if game["white_username"].lower() == username.lower() else "black"
    opponent = game["black_username"] if side == "white" else game["white_username"]
    user_rating = game["white_rating"] if side == "white" else game["black_rating"]
    opp_rating = game["black_rating"] if side == "white" else game["white_rating"]
    result = game["white_result"] if side == "white" else game["black_result"]
    user_acc = game["white_accuracy"] if side == "white" else game["black_accuracy"]
    opp_acc = game["black_accuracy"] if side == "white" else game["white_accuracy"]
    eco = (
        game["eco_url"].rstrip("/").split("/")[-1].replace("-", " ")
        if game["eco_url"]
        else "Unknown opening"
    )

    parts = [
        f"Date: {date}.",
        f"{username} played {side} (rating {user_rating}) against {opponent} (rating {opp_rating}).",
        f"Result: {result}.",
        f"Opening: {eco}.",
        f"Time class: {game['time_class']}, {game['time_control']}s.",
    ]
    if user_acc is not None:
        parts.append(f"Accuracy: {username} {user_acc:.1f}%, opponent {opp_acc:.1f}%.")
    if game.get("avg_centipawn_loss") is not None:
        parts.append(
            f"Stockfish: {game['blunders']} blunders, {game['mistakes']} mistakes, "
            f"{game['inaccuracies']} inaccuracies, avg centipawn loss {game['avg_centipawn_loss']:.1f}."
        )

    return " ".join(parts)


_GAMES_WITH_EVALS = """
    SELECT
        g.*,
        ge.blunders, ge.mistakes, ge.inaccuracies,
        ge.avg_centipawn_loss, ge.sharpest_cp_swing
    FROM games g
    LEFT JOIN game_evaluations ge ON g.uuid = ge.game_uuid AND ge.username = ?
    WHERE {where}
"""


def _ensure_collection(client: QdrantClient) -> None:
    if not client.collection_exists(COLLECTION):
        print(f"[SETUP] Creating Qdrant collection '{COLLECTION}'")
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def _rows_to_points(rows: list, username: str) -> list[PointStruct]:
    points = []
    for row in rows:
        game = dict(row)
        side = "white" if game["white_username"].lower() == username.lower() else "black"
        result = game["white_result"] if side == "white" else game["black_result"]
        text = _game_to_text(game, username)
        vector = embed(text)
        points.append(
            PointStruct(
                id=game["uuid"],
                vector=vector,
                payload={
                    "text": text,
                    "username": username,
                    "outcome": _compute_outcome(result),
                    "time_class": game["time_class"],
                    "side": side,
                },
            )
        )
    return points


def index_user(username: str) -> None:
    """
    Embed all games for a user and upsert them into Qdrant.

    Creates the collection if it does not exist. Safe to re-run —
    existing points are overwritten with updated payloads (idempotent).
    Includes Stockfish evaluation data if available.

    Args:
        username (str): Chess.com username whose games to index.

    Returns:
        None
    """
    client = _get_client()
    _ensure_collection(client)

    with get_connection() as conn:
        rows = conn.execute(
            _GAMES_WITH_EVALS.format(where="g.white_username = ? OR g.black_username = ?"),
            (username, username, username),
        ).fetchall()

    total = len(rows)
    print(f"[INFO] {total} games to index for {username}")

    points = []
    for i, row in enumerate(rows, 1):
        points.extend(_rows_to_points([row], username))
        if i % 50 == 0 or i == total:
            print(f"[PROGRESS] {i}/{total} ({round(i / total * 100)}%) games embedded", flush=True)

    print("[INFO] Upserting to Qdrant...", flush=True)
    client.upsert(collection_name=COLLECTION, points=points)
    print(f"[DONE] Indexed {len(points)} games into Qdrant")


def index_games(username: str, uuids: list[str]) -> None:
    """
    Embed a specific list of games and upsert them into Qdrant.

    Used by the pipeline to index each evaluated batch immediately after
    Stockfish finishes it. Includes Stockfish data from game_evaluations.

    Args:
        username (str): Chess.com username the games belong to.
        uuids (list[str]): Game UUIDs to embed and upsert.

    Returns:
        None
    """
    if not uuids:
        return

    client = _get_client()
    _ensure_collection(client)

    placeholders = ",".join("?" * len(uuids))
    with get_connection() as conn:
        rows = conn.execute(
            _GAMES_WITH_EVALS.format(where=f"g.uuid IN ({placeholders})"),
            (username, *uuids),
        ).fetchall()

    points = _rows_to_points(rows, username)
    client.upsert(collection_name=COLLECTION, points=points)
    print(f"[INDEX ] {len(points)} games upserted to Qdrant", flush=True)


def search(username: str, query: str, top_k: int = 20, filters: dict | None = None, verbose: bool = False) -> list[str]:
    """
    Find the most semantically similar game descriptions to a query.

    Always filters by username. Additional filters (outcome, time_class, side)
    are applied as Qdrant must-match conditions before scoring by similarity.

    Args:
        username (str): Chess.com username to restrict results to.
        query (str): Natural language question or topic to search for.
        top_k (int): Number of results to return. Defaults to 20.
        filters (dict | None): Optional key-value pairs to filter on, e.g.
            {"outcome": "loss", "time_class": "rapid"}.
        verbose (bool): If True, print filter and result details. Defaults to False.

    Returns:
        list[str]: Plain text game descriptions ordered by relevance.
    """
    client = _get_client()

    conditions = [FieldCondition(key="username", match=MatchValue(value=username))]
    for key, value in (filters or {}).items():
        conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))

    if verbose:
        active = {k: v for k, v in (filters or {}).items()}
        print(f"[VERBOSE] Filters applied: username={username}" + (f", {active}" if active else ""))
        print("[VERBOSE] Embedding query...", flush=True)

    vector = embed(query)

    if verbose:
        print(f"[VERBOSE] Searching top {top_k} in Qdrant...", flush=True)

    results = client.query_points(
        collection_name=COLLECTION,
        query=vector,
        query_filter=Filter(must=conditions),
        limit=top_k,
    )
    chunks = [r.payload["text"] for r in results.points]

    if verbose:
        print(f"[VERBOSE] Retrieved {len(chunks)} chunks")
        for j, chunk in enumerate(chunks, 1):
            print(f"[VERBOSE]   {j}. {chunk}")

    return chunks
