from .embedder import chat
from .store import search

PROMPT_TEMPLATE = """You are a chess coach analyzing games for {username}.

Here are {n} relevant games from their history:

{context}

Question: {question}

Answer based only on the games above. Be specific, concise, and actionable."""

_LOSS_KEYWORDS = {"struggle", "lose", "loss", "worst", "bad", "weak", "fail", "failing", "losing", "lost"}
_TIME_CLASSES = {"rapid", "blitz", "bullet"}


def _extract_filters(question: str) -> dict:
    """
    Infer Qdrant filter conditions from keywords in the question.

    Detects loss intent, time class, and side (white/black) so that
    retrieval is scoped to the most relevant subset of games.

    Args:
        question (str): Raw question from the user.

    Returns:
        dict: Filter key-value pairs, e.g. {"outcome": "loss", "time_class": "rapid"}.
    """
    words = set(question.lower().split())
    filters: dict = {}

    if words & _LOSS_KEYWORDS:
        filters["outcome"] = "loss"

    for tc in _TIME_CLASSES:
        if tc in words:
            filters["time_class"] = tc
            break

    if "white" in words:
        filters["side"] = "white"
    elif "black" in words:
        filters["side"] = "black"

    return filters


def ask(username: str, question: str, top_k: int = 20, verbose: bool = False) -> str:
    """
    Answer a coaching question using RAG over the user's game history.

    Extracts intent filters from the question, retrieves the top_k most
    relevant games from Qdrant, injects them as context, and returns the
    model's response.

    Args:
        username (str): Chess.com username to coach.
        question (str): Natural language question about their games.
        top_k (int): Number of games to retrieve as context. Defaults to 20.
        verbose (bool): If True, print filters, retrieved chunks, and prompt. Defaults to False.

    Returns:
        str: Coaching response from the local LLM.
    """
    filters = _extract_filters(question)

    if verbose:
        print(f"[VERBOSE] Extracted filters: {filters if filters else 'none'}")

    chunks = search(username, question, top_k=top_k, filters=filters, verbose=verbose)
    context = "\n".join(f"- {chunk}" for chunk in chunks)
    prompt = PROMPT_TEMPLATE.format(
        username=username,
        n=len(chunks),
        context=context,
        question=question,
    )

    if verbose:
        print(f"[VERBOSE] Prompt ({len(prompt)} chars):\n{prompt}\n")

    print("[...] Thinking", flush=True)
    return chat(prompt)
