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
Ingestion Layer (to be implemented)
↓
SQLite Storage
↓
Analysis Layer (to be implemented)
↓
Vector Database and RAG Layer (future)

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
