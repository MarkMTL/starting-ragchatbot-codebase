# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A Retrieval-Augmented Generation (RAG) system that answers questions about course materials. FastAPI backend, vanilla-JS frontend, ChromaDB for vector storage, and Anthropic Claude for generation. Claude answers via **tool use**: it decides whether to call a semantic-search tool rather than having context stuffed into the prompt.

## Commands

Setup (requires Python 3.13+ and `uv`):

```bash
uv sync                                    # install dependencies
echo "ANTHROPIC_API_KEY=your-key" > .env   # required; app fails to generate without it
```

Run:

```bash
./run.sh                                                   # from repo root
cd backend && uv run uvicorn app:app --reload --port 8000  # equivalent manual start
```

- Web UI: `http://localhost:8000`
- API docs (Swagger): `http://localhost:8000/docs`

Always use `uv` to run the server and manage dependencies — never invoke `pip` directly. Run Python files with `uv run python <file>`, never bare `python`.

There is no test suite, linter, or build step configured. `main.py` at the root is an unused placeholder — the real entry point is `backend/app.py`.

## Architecture

Request flow for a query (`POST /api/query`):

```
frontend/script.js  →  backend/app.py  →  RAGSystem.query()  →  AIGenerator.generate_response()
                                                                        │
                                                    (Claude decides: tool_use?)
                                                                        │
                                              ToolManager → CourseSearchTool → VectorStore (ChromaDB)
                                                                        │
                                              second Claude call synthesizes final answer
```

`RAGSystem` (`backend/rag_system.py`) is the orchestrator wiring together every component; it is instantiated once in `app.py` at module load.

### Two-call tool pattern (`ai_generator.py`)

`generate_response` makes a **first** Claude call with `tool_choice: auto`. If `stop_reason == "tool_use"`, `_handle_tool_execution` runs the tool(s), appends results to the message list, then makes a **second** call **with tools stripped** so Claude synthesizes a text answer instead of looping into another search. The system prompt enforces **one search per query max**. General-knowledge questions skip the tool entirely and return the first call's text.

### Vector storage: two collections (`vector_store.py`)

ChromaDB holds two separate collections, both embedded with `all-MiniLM-L6-v2`:

- **`course_catalog`** — one entry per course; document is the title, metadata carries instructor, links, and lessons serialized as a `lessons_json` string (ChromaDB metadata can't hold nested objects). The course **title is the primary key** (used as the ChromaDB `id`).
- **`course_content`** — the chunked lesson text that actual searches run against.

Search is a two-step resolve-then-filter (`VectorStore.search`): a fuzzy `course_name` is first resolved to an exact title via semantic search against `course_catalog`, then that title plus optional `lesson_number` become a metadata `where` filter on `course_content`.

### Document ingestion (`document_processor.py`)

On startup `app.py` calls `add_course_folder("../docs")`, which **skips courses whose title already exists** in the catalog (dedup by title) — it does not re-index or update changed files. To force a rebuild, call `add_course_folder(..., clear_existing=True)` or delete `backend/chroma_db/`.

Expected document format (`docs/*.txt`):

```
Course Title: ...
Course Link: ...
Course Instructor: ...

Lesson 0: Introduction
Lesson Link: ...
<lesson content>
Lesson 1: ...
```

Chunking is sentence-based (regex split, abbreviation-aware) targeting `CHUNK_SIZE` chars with `CHUNK_OVERLAP` overlap, per-lesson. Chunks get a lesson/course context prefix prepended before embedding.

### Sources & sessions

- `CourseSearchTool` stashes the sources of its last search on `self.last_sources`; `RAGSystem.query` reads them via `ToolManager.get_last_sources()` **then calls `reset_sources()`** — sources are per-query mutable state, not returned inline.
- `SessionManager` keeps the last `MAX_HISTORY` exchanges per session; history is injected into the **system prompt** as plain text, not as prior message turns.

## Configuration

All tunables live in `backend/config.py` (`Config` dataclass): `ANTHROPIC_MODEL` (`claude-sonnet-4-20250514`), `EMBEDDING_MODEL`, `CHUNK_SIZE` (800), `CHUNK_OVERLAP` (100), `MAX_RESULTS` (5), `MAX_HISTORY` (2), `CHROMA_PATH` (`./chroma_db`, relative to `backend/`).

## Conventions

Backend modules import each other by bare module name (`from vector_store import ...`), so backend code only runs correctly with `backend/` as the working directory — which is why `run.sh` does `cd backend` first.
