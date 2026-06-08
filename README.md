# Caissa

Local-first Chess.com analytics and RAG-based chess coaching system.

## Goal

Caissa transforms raw chess games into structured insights and coaching output through a layered pipeline:
Chess.com Games
↓
Stockfish Analysis
↓
Analytics Layer (SQL)
↓
Vector Database (Qdrant)
↓
Local LLM Coach (Qwen3 via Ollama)

The LLM is used strictly for explanation and reasoning. It does not determine chess truth.

Chess truth is derived from:
- Stockfish evaluations
- Statistical analysis of games
- Historical game data

## Architecture (MVP)
Chess.com API
↓
Ingestion Layer
↓
SQLite Storage
↓
Analysis Layer
↓
Vector Database and RAG Layer (future)

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

### 3. Run analysis

```bash
python -m src.analysis.cli <username> <command>
```

| Command | Description |
| --- | --- |
| `win-rate` | Win rate by time class (bullet / blitz / rapid) |
| `rating` | Average rating per month |
| `openings` | Top 10 most played openings with win rate |

Example:

```bash
python -m src.analysis.cli costellof win-rate
```

## Technology Stack

- Python 3.14 (managed with uv)
- Chess.com Public API
- python-chess
- Stockfish engine
- SQLite (initial storage layer)
- Qdrant (future vector database)
- Ollama (local inference runtime)
  - Model: qwen3:8b

## Multi-user Design

The system is designed to support multiple users from the beginning.
data/
users/
costellof/
hikaru/
magnuscarlsen/

All database tables must include a user identifier field:

```sql
username TEXT NOT NULL
```
