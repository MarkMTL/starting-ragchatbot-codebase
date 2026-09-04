"""Tests for RAGSystem.query orchestration (all components patched, no I/O)."""

from unittest.mock import MagicMock, patch

import pytest
import rag_system as rag_mod
from rag_system import RAGSystem


@pytest.fixture
def rag(monkeypatch):
    """RAGSystem with every component class patched to a MagicMock instance."""
    cfg = MagicMock()
    cfg.CHUNK_SIZE = 800
    cfg.CHUNK_OVERLAP = 100
    cfg.CHROMA_PATH = "./x"
    cfg.EMBEDDING_MODEL = "m"
    cfg.MAX_RESULTS = 5
    cfg.ANTHROPIC_API_KEY = "k"
    cfg.ANTHROPIC_MODEL = "model"
    cfg.MAX_HISTORY = 2

    with (
        patch.object(rag_mod, "DocumentProcessor"),
        patch.object(rag_mod, "VectorStore"),
        patch.object(rag_mod, "AIGenerator"),
        patch.object(rag_mod, "SessionManager"),
        patch.object(rag_mod, "CourseSearchTool"),
        patch.object(rag_mod, "CourseOutlineTool"),
        patch.object(rag_mod, "ToolManager"),
    ):
        system = RAGSystem(cfg)
        yield system


class TestQuery:
    def test_returns_response_and_sources(self, rag):
        rag.ai_generator.generate_response.return_value = "the answer"
        rag.tool_manager.get_last_sources.return_value = [{"text": "MCP", "link": None}]
        answer, sources = rag.query("what is mcp")
        assert answer == "the answer"
        assert sources == [{"text": "MCP", "link": None}]

    def test_sources_reset_after_read(self, rag):
        rag.ai_generator.generate_response.return_value = "a"
        rag.tool_manager.get_last_sources.return_value = []
        rag.query("q")
        rag.tool_manager.get_last_sources.assert_called_once()
        rag.tool_manager.reset_sources.assert_called_once()

    def test_history_updated_with_session(self, rag):
        rag.ai_generator.generate_response.return_value = "a"
        rag.tool_manager.get_last_sources.return_value = []
        rag.session_manager.get_conversation_history.return_value = "hist"
        rag.query("q", session_id="s1")
        rag.session_manager.get_conversation_history.assert_called_once_with("s1")
        rag.session_manager.add_exchange.assert_called_once_with("s1", "q", "a")

    def test_no_history_update_without_session(self, rag):
        rag.ai_generator.generate_response.return_value = "a"
        rag.tool_manager.get_last_sources.return_value = []
        rag.query("q")
        rag.session_manager.add_exchange.assert_not_called()

    def test_generate_called_with_tools(self, rag):
        rag.ai_generator.generate_response.return_value = "a"
        rag.tool_manager.get_last_sources.return_value = []
        rag.tool_manager.get_tool_definitions.return_value = [
            {"name": "search_course_content"}
        ]
        rag.query("q")
        kwargs = rag.ai_generator.generate_response.call_args.kwargs
        assert kwargs["tools"] == [{"name": "search_course_content"}]
        assert kwargs["tool_manager"] is rag.tool_manager
