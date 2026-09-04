"""Tests for AIGenerator.generate_response — the sequential tool-use loop."""

from unittest.mock import MagicMock

import pytest
from ai_generator import AIGenerator


@pytest.fixture
def generator():
    gen = AIGenerator(api_key="test", model="test-model")
    gen.client = MagicMock()
    return gen


class TestGenerateResponse:
    def test_no_tools_single_plain_call(
        self, generator, mock_anthropic_response_factory
    ):
        generator.client.messages.create.return_value = (
            mock_anthropic_response_factory.text("hi")
        )
        out = generator.generate_response(query="general q")
        assert out == "hi"
        assert generator.client.messages.create.call_count == 1
        # plain path never attaches tools
        assert "tools" not in generator.client.messages.create.call_args.kwargs

    def test_one_tool_round_then_text(self, generator, mock_anthropic_response_factory):
        tool_mgr = MagicMock()
        tool_mgr.execute_tool.return_value = "search result"
        generator.client.messages.create.side_effect = [
            mock_anthropic_response_factory.tool_use(tool_input={"query": "mcp"}),
            mock_anthropic_response_factory.text("synthesized"),
        ]
        out = generator.generate_response(
            query="course q",
            tools=[{"name": "search_course_content"}],
            tool_manager=tool_mgr,
        )
        assert out == "synthesized"
        tool_mgr.execute_tool.assert_called_once_with(
            "search_course_content", query="mcp"
        )
        assert generator.client.messages.create.call_count == 2

    def test_rounds_exhausted_forces_tools_stripped_final(
        self, generator, mock_anthropic_response_factory
    ):
        tool_mgr = MagicMock()
        tool_mgr.execute_tool.return_value = "r"
        # two tool_use rounds, then a forced final call
        generator.client.messages.create.side_effect = [
            mock_anthropic_response_factory.tool_use(),
            mock_anthropic_response_factory.tool_use(),
            mock_anthropic_response_factory.text("final"),
        ]
        out = generator.generate_response(
            query="q",
            tools=[{"name": "search_course_content"}],
            tool_manager=tool_mgr,
        )
        assert out == "final"
        assert generator.client.messages.create.call_count == 3
        # final call must not carry tools
        assert "tools" not in generator.client.messages.create.call_args.kwargs

    def test_tool_error_breaks_to_final(
        self, generator, mock_anthropic_response_factory
    ):
        tool_mgr = MagicMock()
        tool_mgr.execute_tool.side_effect = RuntimeError("tool blew up")
        generator.client.messages.create.side_effect = [
            mock_anthropic_response_factory.tool_use(),
            mock_anthropic_response_factory.text("recovered"),
        ]
        out = generator.generate_response(
            query="q",
            tools=[{"name": "search_course_content"}],
            tool_manager=tool_mgr,
        )
        assert out == "recovered"
        # first tool round + final call = 2, loop broke on error
        assert generator.client.messages.create.call_count == 2

    def test_history_injected_into_system(
        self, generator, mock_anthropic_response_factory
    ):
        generator.client.messages.create.return_value = (
            mock_anthropic_response_factory.text("ok")
        )
        generator.generate_response(
            query="q", conversation_history="User: hi\nAssistant: yo"
        )
        system = generator.client.messages.create.call_args.kwargs["system"]
        assert "Previous conversation:" in system
        assert "User: hi" in system
