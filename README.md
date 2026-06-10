# Caissa

Local-first Chess.com analytics and RAG-based chess coaching system.

## Goal

Caissa transforms raw chess games into structured insights and coaching output through a layered pipeline:

```text
Chess.com Games
↓
Ingestion (download + normalize)
↓
Stockfish Analysis (move-level evaluation)
↓
Analytics Layer (SQL)
↓
Vector Database (Qdrant)
↓
Local LLM Coach (Qwen3 via Ollama)
```

The LLM is used strictly for explanation and reasoning. It does not determine chess truth.

Chess truth is derived from:

- Stockfish evaluations (centipawn loss, blunder/mistake/inaccuracy classification)
- Statistical analysis of games
- Historical game data

## Usage

### 1. Download raw archives

```bash
python -m src.ingestion.downloader <username>
```

Fetches all monthly game archives from Chess.com and saves them to `data/users/<username>/raw/`. Skips months already on disk.

### 2. Normalize into SQLite

```bash
python -m src.ingestion.normalizer <username>
```

Parses raw JSON archives and upserts games into `data/caissa.db`. Safe to re-run — duplicate games are ignored.

### 3. Run Stockfish evaluation pipeline

```bash
uv run caffeinate -i python -m src.ingestion.pipeline <username> --batch-size 200
```

Evaluates every game position with Stockfish (depth 15) and writes per-move classifications and per-game summaries to SQLite. Concurrently indexes each completed batch into Qdrant while the next batch is being evaluated. Safe to interrupt and resume — already-evaluated games are skipped.

Options:

- `--batch-size N` — games per batch (default: 100)
- `--limit N` — cap total games processed

### 4. Run analysis

```bash
python -m src.analysis.cli <username> <command>
```

| Command | Description |
| --- | --- |
| `win-rate` | Win rate by time class (bullet / blitz / rapid) |
| `rating` | Average rating per month |
| `openings` | Top 10 most played openings with win rate |

### 5. Ask the coach

```bash
# Index games into Qdrant (first time, or after new games)
python -m src.coach.cli <username> --index

# Start coaching session
python -m src.coach.cli <username>

# With verbose retrieval logs
python -m src.coach.cli <username> --verbose
```

## Technology Stack

- Python 3.14 (managed with uv)
- Chess.com Public API
- python-chess + Stockfish (local engine, install via `brew install stockfish`)
- SQLite (structured game storage)
- Qdrant (local vector database, no Docker required)
- Ollama (local inference runtime)
  - Embedding model: nomic-embed-text
  - Chat model: qwen3:4b

## Multi-user Design

All database tables include a username field so multiple players can be tracked simultaneously:

```text
data/
  users/
    costellof/
    hikaru/
    magnuscarlsen/
```
