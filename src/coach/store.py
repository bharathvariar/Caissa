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
    and accuracy (if available) from the perspective of username.

    Args:
        game (dict): Row from the games table as a dict.
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

    return " ".join(parts)


def index_user(username: str) -> None:
    """
    Embed all games for a user and upsert them into Qdrant.

    Creates the collection if it does not exist. Safe to re-run —
    existing points are overwritten with updated payloads (idempotent).

    Args:
        username (str): Chess.com username whose games to index.

    Returns:
        None
    """
    client = _get_client()

    if not client.collection_exists(COLLECTION):
        print(f"[SETUP] Creating Qdrant collection '{COLLECTION}'")
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
    else:
        print(f"[SETUP] Collection '{COLLECTION}' already exists — upserting")

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM games WHERE white_username = ? OR black_username = ?",
            (username, username),
        ).fetchall()

    total = len(rows)
    print(f"[INFO] {total} games to index for {username}")

    points = []
    for i, row in enumerate(rows):
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
        completed = i + 1
        if completed % 50 == 0 or completed == total:
            pct = completed / total * 100
            print(f"[PROGRESS] {completed}/{total} ({pct:.0f}%) games embedded", flush=True)

    print("[INFO] Upserting to Qdrant...", flush=True)
    client.upsert(collection_name=COLLECTION, points=points)
    print(f"[DONE] Indexed {len(points)} games into Qdrant")


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
        print(f"[VERBOSE] Embedding query...", flush=True)

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
