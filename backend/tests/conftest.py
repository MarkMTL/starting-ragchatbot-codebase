"""Shared pytest fixtures for backend tests.

Everything here is mocked — no ChromaDB, no network, no Anthropic API. Tests run
with ``backend/`` on the path (see ``pythonpath`` in pyproject.toml), so bare
module imports like ``from vector_store import SearchResults`` resolve.
"""

from types import SimpleNamespace
from typing import List, Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from vector_store import SearchResults

# --------------------------------------------------------------------------- #
# Search / vector store fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def search_results_factory():
    """Build a real SearchResults so tool formatting runs against true objects."""

    def _make(documents=None, metadata=None, distances=None, error=None):
        if error is not None:
            return SearchResults(documents=[], metadata=[], distances=[], error=error)
        documents = documents or []
        metadata = metadata or []
        distances = distances if distances is not None else [0.1] * len(documents)
        return SearchResults(
            documents=documents,
            metadata=metadata,
            distances=distances,
        )

    return _make


@pytest.fixture
def mock_vector_store(search_results_factory):
    """MagicMock shaped like VectorStore with sensible link/resolve stubs."""
    store = MagicMock()
    store.search.return_value = search_results_factory(
        documents=["Chunk about MCP servers."],
        metadata=[{"course_title": "MCP Course", "lesson_number": 1}],
    )
    store.get_lesson_link.return_value = "http://example.com/lesson1"
    store.get_course_link.return_value = "http://example.com/course"
    store._resolve_course_name.return_value = "MCP Course"
    store.course_catalog.get.return_value = {
        "metadatas": [
            {
                "course_link": "http://example.com/course",
                "lessons_json": '[{"lesson_number": 0, "lesson_title": "Intro"},'
                ' {"lesson_number": 1, "lesson_title": "Servers"}]',
            }
        ]
    }
    return store


# --------------------------------------------------------------------------- #
# Anthropic response fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def mock_anthropic_response_factory():
    """Build fake Anthropic message responses (text or tool_use)."""

    def _text(text="Final answer."):
        block = SimpleNamespace(type="text", text=text)
        return SimpleNamespace(stop_reason="end_turn", content=[block])

    def _tool_use(name="search_course_content", tool_input=None, tool_id="tu_1"):
        block = SimpleNamespace(
            type="tool_use",
            name=name,
            input=tool_input or {"query": "mcp"},
            id=tool_id,
        )
        return SimpleNamespace(stop_reason="tool_use", content=[block])

    return SimpleNamespace(text=_text, tool_use=_tool_use)


# --------------------------------------------------------------------------- #
# RAG system + API app fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def mock_rag_system():
    """MagicMock RAGSystem with query/analytics/session behaviour."""
    rag = MagicMock()
    rag.query.return_value = (
        "answer text",
        [{"text": "MCP Course - Lesson 1", "link": "http://example.com/lesson1"}],
    )
    rag.session_manager.create_session.return_value = "s1"
    rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["MCP Course", "Chroma Course"],
    }
    return rag


@pytest.fixture
def test_app(mock_rag_system):
    """Inline FastAPI app mirroring app.py's 3 API endpoints, no static mount."""

    app = FastAPI()

    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class SourceItem(BaseModel):
        text: str
        link: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[SourceItem]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()
            answer, sources = mock_rag_system.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/session/{session_id}")
    async def clear_session(session_id: str):
        try:
            mock_rag_system.session_manager.clear_session(session_id)
            return {"status": "cleared", "session_id": session_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


@pytest.fixture
def client(test_app):
    """TestClient for the inline test app."""
    return TestClient(test_app)
