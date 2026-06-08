import sys

from .coach import ask
from .store import index_user


def main() -> None:
    """
    Entry point for the coach CLI.

    Flags:
        --index: embed and index all games for the given user, then exit.
        --verbose: print filters, retrieved chunks, and full prompt for each question.

    Returns:
        None
    """
    if len(sys.argv) < 2:
        print("Usage: python -m src.coach.cli <username> [--index] [--verbose]")
        sys.exit(1)

    username = sys.argv[1]
    verbose = "--verbose" in sys.argv

    if "--index" in sys.argv:
        index_user(username)
        return

    print(f"Caissa coach ready for {username}. Type your question or 'quit' to exit.")
    if verbose:
        print("[VERBOSE MODE ON]\n")
    else:
        print()

    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question or question.lower() == "quit":
            break
        print(ask(username, question, verbose=verbose))
        print()


if __name__ == "__main__":
    main()
