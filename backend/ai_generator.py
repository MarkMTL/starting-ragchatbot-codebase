import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Maximum sequential tool-use rounds per user query. Each round is a separate
    # API call that carries tools; after the cap a final tools-stripped call forces text.
    MAX_TOOL_ROUNDS = 2

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to tools for course information.

Available Tools:
- **search_course_content**: Search within course materials for specific content or detailed educational material.
- **get_course_outline**: Get a course's outline — its title, course link, and the complete list of lessons (each lesson's number and title). Use for questions about a course's structure, syllabus, or what lessons it covers.

Sequential Tool Use:
- You may call tools across up to TWO sequential rounds. After you see the results of a first tool call, you may make ONE more tool call if it is needed to fully answer — for example, call get_course_outline to find a lesson's title, then call search_course_content to retrieve content on that topic.
- Prefer a single tool call when it suffices; only chain a second call when the first result is insufficient on its own. Do not re-run the same search.
- After at most two rounds, answer using the information gathered; no further tool calls will be available.

Tool Usage:
- Use **search_course_content** for questions about specific content inside courses.
- Use **get_course_outline** for questions about a course's outline, structure, or lesson list. When answering outline queries, return the course title, the course link, and the number and title of each lesson.
- Synthesize tool results into accurate, fact-based responses
- If a tool yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course-specific questions**: Use the appropriate tool first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional sequential tool usage and conversation context.

        Claude may call tools across up to MAX_TOOL_ROUNDS sequential rounds — each a
        separate API request carrying tools, so it can reason over prior results before
        deciding on another tool call. After the cap (or on a tool failure) a final
        tools-stripped call forces a text answer.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        messages = [{"role": "user", "content": query}]

        # Backward-compatible path: without tools/manager, a single plain call.
        if not tools or not tool_manager:
            response = self.client.messages.create(
                **self._build_params(messages, system_content, tools, include_tools=False)
            )
            return self._extract_text(response)

        # Sequential tool-calling loop; every in-loop call carries tools.
        for _ in range(self.MAX_TOOL_ROUNDS):
            response = self.client.messages.create(
                **self._build_params(messages, system_content, tools, include_tools=True)
            )

            # (b) Claude answered directly — no tool use.
            if response.stop_reason != "tool_use":
                return self._extract_text(response)

            # Record Claude's tool-use turn, run the tools, append their results.
            messages.append({"role": "assistant", "content": response.content})
            tool_results, had_error = self._execute_tools(response, tool_manager)
            messages.append({"role": "user", "content": tool_results})

            # (c) a tool failed — stop looping, synthesize a final answer.
            if had_error:
                break

        # (a) rounds exhausted while still tool_use, or (c) error: one final
        # tools-stripped call guarantees a text answer.
        final_response = self.client.messages.create(
            **self._build_params(messages, system_content, tools, include_tools=False)
        )
        return self._extract_text(final_response)

    def _build_params(self, messages: List[Dict[str, Any]], system_content: str,
                      tools: Optional[List], include_tools: bool) -> Dict[str, Any]:
        """Assemble API params, attaching tools only when include_tools is set."""
        params = {
            **self.base_params,
            "messages": messages,
            "system": system_content,
        }
        if include_tools and tools:
            params["tools"] = tools
            params["tool_choice"] = {"type": "auto"}
        return params

    def _execute_tools(self, response, tool_manager):
        """
        Execute every tool_use block in a response.

        Returns (tool_result_blocks, had_error). A tool that raises is captured as an
        error tool_result (is_error=True) so Claude can recover into a text answer
        rather than crashing the request.
        """
        tool_result_blocks = []
        had_error = False
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                result = tool_manager.execute_tool(block.name, **block.input)
                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
            except Exception as e:
                had_error = True
                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": f"Tool execution failed: {e}",
                    "is_error": True,
                })
        return tool_result_blocks, had_error

    def _extract_text(self, response) -> str:
        """Return the first text block's text, falling back to the first block."""
        for block in response.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return response.content[0].text