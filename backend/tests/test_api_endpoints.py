"""Tests for the FastAPI API endpoints (inline test app, mocked RAGSystem)."""

import pytest


class TestQueryEndpoint:
    def test_query_with_session_id(self, client, mock_rag_system):
        resp = client.post("/api/query", json={"query": "what is mcp", "session_id": "abc"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "answer text"
        assert data["session_id"] == "abc"
        assert data["sources"][0]["text"] == "MCP Course - Lesson 1"
        assert data["sources"][0]["link"] == "http://example.com/lesson1"
        mock_rag_system.query.assert_called_once_with("what is mcp", "abc")
        mock_rag_system.session_manager.create_session.assert_not_called()

    def test_query_without_session_id_creates_session(self, client, mock_rag_system):
        resp = client.post("/api/query", json={"query": "hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "s1"
        mock_rag_system.session_manager.create_session.assert_called_once()
        mock_rag_system.query.assert_called_once_with("hello", "s1")

    def test_query_missing_query_field_is_422(self, client):
        resp = client.post("/api/query", json={})
        assert resp.status_code == 422

    def test_query_propagates_error_as_500(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("boom")
        resp = client.post("/api/query", json={"query": "x"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "boom"


class TestCoursesEndpoint:
    def test_get_courses(self, client):
        resp = client.get("/api/courses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_courses"] == 2
        assert data["course_titles"] == ["MCP Course", "Chroma Course"]

    def test_courses_error_as_500(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("db down")
        resp = client.get("/api/courses")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "db down"


class TestSessionEndpoint:
    def test_clear_session(self, client, mock_rag_system):
        resp = client.delete("/api/session/abc")
        assert resp.status_code == 200
        assert resp.json() == {"status": "cleared", "session_id": "abc"}
        mock_rag_system.session_manager.clear_session.assert_called_once_with("abc")

    def test_clear_session_error_as_500(self, client, mock_rag_system):
        mock_rag_system.session_manager.clear_session.side_effect = RuntimeError("nope")
        resp = client.delete("/api/session/abc")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "nope"
