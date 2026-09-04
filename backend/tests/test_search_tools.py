"""Tests for search_tools: CourseSearchTool, CourseOutlineTool, ToolManager."""

import pytest

from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager


class TestCourseSearchTool:
    def test_execute_success_formats_and_sets_sources(self, mock_vector_store):
        tool = CourseSearchTool(mock_vector_store)
        out = tool.execute(query="mcp")
        assert "[MCP Course - Lesson 1]" in out
        assert "Chunk about MCP servers." in out
        assert tool.last_sources == [
            {"text": "MCP Course - Lesson 1", "link": "http://example.com/lesson1"}
        ]

    def test_execute_course_link_when_no_lesson(self, mock_vector_store, search_results_factory):
        mock_vector_store.search.return_value = search_results_factory(
            documents=["Course-level chunk."],
            metadata=[{"course_title": "MCP Course"}],
        )
        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="mcp")
        assert tool.last_sources == [
            {"text": "MCP Course", "link": "http://example.com/course"}
        ]

    def test_execute_empty_reports_filters(self, mock_vector_store, search_results_factory):
        mock_vector_store.search.return_value = search_results_factory(documents=[], metadata=[])
        tool = CourseSearchTool(mock_vector_store)
        out = tool.execute(query="mcp", course_name="MCP", lesson_number=2)
        assert out == "No relevant content found in course 'MCP' in lesson 2."

    def test_execute_error_passthrough(self, mock_vector_store, search_results_factory):
        mock_vector_store.search.return_value = search_results_factory(error="bad filter")
        tool = CourseSearchTool(mock_vector_store)
        assert tool.execute(query="mcp") == "bad filter"

    def test_definition_shape(self, mock_vector_store):
        d = CourseSearchTool(mock_vector_store).get_tool_definition()
        assert d["name"] == "search_course_content"
        assert d["input_schema"]["required"] == ["query"]


class TestCourseOutlineTool:
    def test_execute_resolved_outline(self, mock_vector_store):
        tool = CourseOutlineTool(mock_vector_store)
        out = tool.execute(course_title="MCP")
        assert "Course: MCP Course" in out
        assert "Course Link: http://example.com/course" in out
        assert "Lesson 0: Intro" in out
        assert "Lesson 1: Servers" in out
        assert tool.last_sources == [
            {"text": "MCP Course", "link": "http://example.com/course"}
        ]

    def test_execute_unresolved(self, mock_vector_store):
        mock_vector_store._resolve_course_name.return_value = None
        tool = CourseOutlineTool(mock_vector_store)
        assert tool.execute(course_title="ghost") == "No course found matching 'ghost'"


class TestToolManager:
    def test_register_and_definitions(self, mock_vector_store):
        mgr = ToolManager()
        mgr.register_tool(CourseSearchTool(mock_vector_store))
        mgr.register_tool(CourseOutlineTool(mock_vector_store))
        names = {d["name"] for d in mgr.get_tool_definitions()}
        assert names == {"search_course_content", "get_course_outline"}

    def test_register_without_name_raises(self):
        class Nameless:
            def get_tool_definition(self):
                return {}

            def execute(self, **kwargs):
                return ""

        with pytest.raises(ValueError):
            ToolManager().register_tool(Nameless())

    def test_execute_tool_and_unknown(self, mock_vector_store):
        mgr = ToolManager()
        mgr.register_tool(CourseSearchTool(mock_vector_store))
        assert "[MCP Course" in mgr.execute_tool("search_course_content", query="mcp")
        assert mgr.execute_tool("nope") == "Tool 'nope' not found"

    def test_last_sources_and_reset(self, mock_vector_store):
        mgr = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        mgr.register_tool(tool)
        mgr.execute_tool("search_course_content", query="mcp")
        assert mgr.get_last_sources()[0]["text"] == "MCP Course - Lesson 1"
        mgr.reset_sources()
        assert mgr.get_last_sources() == []
