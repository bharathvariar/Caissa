import ollama

EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "qwen3:4b"


def embed(text: str) -> list[float]:
    """
    Convert a text string into a vector embedding.

    Uses nomic-embed-text running locally via Ollama.

    Args:
        text (str): Plain text to embed.

    Returns:
        list[float]: 768-dimensional embedding vector.
    """
    response = ollama.embeddings(model=EMBED_MODEL, prompt=text)
    return response["embedding"]


def chat(prompt: str) -> str:
    """
    Send a prompt to the local chat model and return the response.

    Uses qwen3:4b running locally via Ollama.

    Args:
        prompt (str): Full prompt string including any injected context.

    Returns:
        str: Model response text.
    """
    response = ollama.chat(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]
