import json
import os
import re
import asyncio
from typing import Any, Dict, List, Optional, Annotated, Sequence, TypedDict
from src import config as app_config
from src.agents import spec_loader
from langchain_core.messages import (
    HumanMessage,
    SystemMessage, 
    BaseMessage,
    messages_to_dict,
    messages_from_dict
)
import logging
logger = logging.getLogger(__name__)

try:
    from tavily import TavilyClient as _TavilyClient
except ImportError:
    _TavilyClient = None

# ============================================================
# SERIALIZATION HELPERS
# ============================================================

def serialize_state(state: dict) -> str:
    """Serializes the state dictionary, converting LangChain message objects to dicts."""
    serializable_state = state.copy()
    if "messages" in serializable_state:
        serializable_state["messages"] = messages_to_dict(serializable_state["messages"])
    return json.dumps(serializable_state)

def deserialize_state(state_str: str) -> dict:
    """Deserializes the state JSON string, converting message dicts back to LangChain objects."""
    if not state_str:
        return {}
    try:
        state = json.loads(state_str)
        if "messages" in state:
            state["messages"] = messages_from_dict(state["messages"])
        return state
    except Exception as e:
        logger.error(f"Error deserializing state: {e}")
        return {}

# ============================================================
# SYSTEM PROMPTS
# ============================================================

PROMPT_5_MCP_FALLBACK = """
You are an MCP Recovery Specialist. The autonomous native agent has FAILED to complete the task. 

Your job is to take the high-level mission and break it down into EXPLICIT tool calls for the MCP system (click, type, scroll, etc.) to bypass whatever blocked the native agent.

## MISSION TO RECOVER
{mission_objective}

## FAILURE REASON
{failure_reason}

## RECOVERY PLAN
[Provide a step-by-step manual override plan using MCP tools]
"""

from langgraph.graph.message import add_messages

# ... existing code ...

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    atag_phase: str               # "AWAITING_DETAILS", "READY_FOR_PROMPT", "COMPLETED"
    atag_form: Optional[dict]
    atag_prompt: Optional[str]
    execution_result: Optional[str]
    user_id: str
    chat_id: str
    retry_count: int              # Track retries for execution
    last_error: Optional[str]     # Store last error for critic analysis
    browser_session_id: Optional[str] # New field to store browser session ID
    execution_history: List[Dict[str, Any]] # Memory of tool successes/failures


PROMPT_6_CONTEXT_SUMMARIZER = """
You are a Context Compression Agent. Your job is to summarize a long browser execution history into a concise, logic-preserving summary.

## GOAL
Reduce the token count while keeping:
1. The original user intent.
2. Key milestones achieved (e.g., "Successfully logged in", "Reached the checkout page").
3. Critical failures and their causes.
4. Current page state summary.

## OUTPUT
Provide a structured summary that an automation agent can use to continue the task without needing the full raw logs.
"""

class ATAGProcessor:
    """Processes user requests using a decoupled multi-step pipeline.

    Step 1: Input Understanding.
    Step 2: Initial Strategy.
    Step 3: Page Analysis (Thinking).
    Step 4: Critic (Self-healing).
    """
    def __init__(self, llm, tavily_api_key: Optional[str] = None):
        self.llm = llm
        self.tavily_api_key = tavily_api_key or app_config.TAVILY_API_KEY
        self._planner_agent = None
        self._coder_agent = None

    def _get_planner_agent(self):
        """Lazily builds the CrewAI Planner agent from planner.agent.md.

        Pure-reasoning agent (tools=None) — the Planner never touches the
        browser or MCP tools directly, it only produces the plan/mission
        text that the Browser agent then executes.
        """
        if self._planner_agent is None:
            self._planner_agent = spec_loader.build_crewai_agent("planner", tools=None)
        return self._planner_agent

    def _get_coder_agent(self):
        """Lazily builds the CrewAI Coder agent from coder.agent.md (pure-reasoning, no tools)."""
        if self._coder_agent is None:
            self._coder_agent = spec_loader.build_crewai_agent("coder", tools=None)
        return self._coder_agent

    async def _run_crew_task(self, agent, description: str, expected_output: str) -> str:
        """Runs a single-task CrewAI crew off the event loop (crewai's kickoff() is sync)."""
        from crewai import Task, Crew

        def _kickoff():
            task = Task(description=description, expected_output=expected_output, agent=agent)
            crew = Crew(agents=[agent], tasks=[task], verbose=False)
            return str(crew.kickoff())

        return await asyncio.to_thread(_kickoff)

    def _build_coder_system_prompt(self, framework: str) -> str:
        """Assembles the Coder's system prompt from coder.agent.md — no framework
        instructions are hardcoded in Python, only section lookups by name."""
        spec = spec_loader.load_spec("coder")
        framework_key = {
            "playwright": "Framework: playwright",
            "tavily": "Framework: tavily",
        }.get(framework, "Framework: browser-use")

        parts = [f"You are {spec.role}.", f"GOAL: {spec.goal}"]
        if spec.backstory:
            parts.append(spec.backstory)
        output_rules = spec.sections.get("Output Rules (absolute, all frameworks)", "")
        if output_rules:
            parts.append("OUTPUT RULES (ABSOLUTE)\n" + output_rules)
        framework_section = spec.sections.get(framework_key, "")
        if framework_section:
            parts.append(framework_section)
        if framework != "tavily":
            tavily_runtime = spec.sections.get("Optional Tavily runtime search (any framework)", "")
            if tavily_runtime:
                parts.append(tavily_runtime)
        self_validation = spec.sections.get("Self-Validation", "")
        if self_validation:
            parts.append(self_validation)
        return "\n\n".join(parts)

    def _parse_json_safely(self, text: str) -> Dict[str, Any]:
        """Robust JSON extraction from LLM responses with fallback strategies."""
        try:
            cleaned = re.sub(r"```json\s*|\s*```", "", text).strip()
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(cleaned[start:end+1])
            return json.loads(cleaned)
        except Exception as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return {"status": "ERROR", "message": "Invalid JSON format"}

    async def run_input_understanding(
        self,
        original_request: str,
        history_context: str = "",
        override_intent: bool = False,
    ) -> Dict[str, Any]:
        """Runs the CrewAI Planner agent (planner.agent.md) to check completeness
        and generate a form schema if needed. No prompt text is hardcoded here —
        the decision logic and output format come entirely from the spec file.

        ``override_intent`` is set by the caller when the current message looks
        like the user is deliberately swapping an account/credential (e.g. "use
        a different account", "try another email"). When True, a stronger
        directive is added telling the model to disregard any credential-like
        values found only in history and prefer/ask-for values from the current
        message instead — this prevents stale saved credentials from silently
        overriding a user's explicit new instruction.
        """
        spec = spec_loader.load_spec("planner")
        decision_logic = spec.sections.get("Input Understanding — Decision Logic", "")
        output_format = spec.sections.get("Output Format — Input Understanding", "")

        context_prompt = ""
        if history_context:
            context_prompt = (
                f"\n\nRECENT CHAT HISTORY:\n{history_context}\n\n"
                "Use this history only to fill in details the CURRENT USER REQUEST "
                "does not mention. PRECEDENCE RULE: if the current request supplies "
                "a value (account, email, username, password, or any other input) "
                "that conflicts with a value found in the history, the current "
                "request's value ALWAYS wins for this turn — never silently reuse "
                "an older value the user has just replaced or moved away from."
            )
            if override_intent:
                context_prompt += (
                    "\n\nIMPORTANT: The current request indicates the user wants to "
                    "switch to a different account/credential than what was used "
                    "before. Do NOT reuse any account/email/username/password found "
                    "in the chat history above for this turn. Use only what the "
                    "current request explicitly provides; if it is missing a "
                    "required credential, output NEEDS_INPUT and ask for it rather "
                    "than falling back to the old value."
                )

        description = (
            "You are a JSON output engine. Your ENTIRE response must be a single valid JSON "
            "object. No markdown. No explanations. No text outside the JSON object.\n\n"
            f"{decision_logic}\n\n{output_format}\n\n"
            f"USER REQUEST:\n{original_request}{context_prompt}"
        )
        result = await self._run_crew_task(
            self._get_planner_agent(),
            description,
            "A single valid JSON object matching one of the two schemas in the Output Format section, and nothing else.",
        )
        return self._parse_json_safely(result)

    async def run_execution_generation(self, user_request: str, task_summary: str, confirmed_inputs: Dict[str, Any], discovery_strategy: str, prior_context: str = "") -> str:
        """Runs the CrewAI Planner agent to build the high-level mission objective
        for the Browser agent, using planner.agent.md's Mission Design Principles."""
        spec = spec_loader.load_spec("planner")
        design_principles = spec.sections.get("Mission Design Principles", "")
        output_format = spec.sections.get("Output Format — Mission Generation", "")

        confirmed_inputs_list = "\n".join(
            [f"- {k.replace('_', ' ').title()}: {v}" for k, v in confirmed_inputs.items()]
        ) if confirmed_inputs else "None"
        target_info = f"https://{confirmed_inputs.get('website', app_config.DEFAULT_TARGET_DOMAIN)}"

        description = (
            f"{design_principles}\n\n{output_format}\n\n"
            f"TASK: {task_summary}\n\n"
            f"TARGET: {target_info}\n\n"
            f"DISCOVERY STRATEGY: {discovery_strategy}\n\n"
            f"CRITICAL CONSTRAINTS (must appear in the Mission Objective):\n{confirmed_inputs_list}\n\n"
            f"{prior_context}\n\n"
            "COMMAND: Execute the mission objective autonomously. If you encounter a "
            "persistent blocker, report the exact error."
        )
        return await self._run_crew_task(
            self._get_planner_agent(),
            description,
            "Text containing exactly the REASONING, PLAN, and MISSION OBJECTIVE sections described in the Output Format above.",
        )

    async def run_mcp_fallback_generation(self, mission_objective: str, failure_reason: str) -> str:
        """Generates a detailed MCP-based recovery plan when the native agent fails."""
        formatted_prompt = PROMPT_5_MCP_FALLBACK.replace(
            "{mission_objective}", mission_objective
        ).replace(
            "{failure_reason}", failure_reason
        )
        response = await self.llm.ainvoke([SystemMessage(content=formatted_prompt)])
        return response.content

    async def run_page_analysis(self, goal: str, page_content: str, last_error: Optional[str] = None) -> str:
        """Diagnoses the gap between the current page and the goal, using the
        'Page Analysis (Diagnostic Mode)' section of browser.agent.md."""
        spec = spec_loader.load_spec("browser")
        section = spec.sections.get("Page Analysis (Diagnostic Mode)", "")
        formatted_prompt = (
            f"{section}\n\n"
            f"GOAL: {goal}\n\n"
            f"CURRENT PAGE CONTENT (truncated):\n{page_content[:15000]}\n\n"
            f"LAST ERROR: {last_error or 'None'}"
        )
        response = await self.llm.ainvoke([SystemMessage(content=formatted_prompt)])
        return response.content

    async def run_critic(self, user_request: str, failed_prompt: str, error_msg: str) -> str:
        """Analyzes an execution failure and produces a structured, classified
        revision, per browser.agent.md's Recovery Protocol section. The
        FAILURE_TYPE line lets brain.py's retry loop branch behavior
        (retry vs. re-plan vs. ask user vs. give up) instead of blindly
        retrying the same instructions every time."""
        spec = spec_loader.load_spec("browser")
        recovery_protocol = spec.sections.get("Recovery Protocol (used by the Critic on failure)", "")
        formatted_prompt = (
            f"{recovery_protocol}\n\n"
            f"ORIGINAL USER REQUEST:\n{user_request}\n\n"
            f"FAILED INSTRUCTION:\n{failed_prompt}\n\n"
            f"ERROR / OBSERVED STATE:\n{error_msg}"
        )
        response = await self.llm.ainvoke([SystemMessage(content=formatted_prompt)])
        return response.content

    async def summarize_context(self, history: List[Dict[str, Any]], current_page: str) -> str:
        """Summarizes the execution history and page state when tokens are near limit."""
        history_str = json.dumps(history, indent=2)
        formatted_prompt = PROMPT_6_CONTEXT_SUMMARIZER + f"\n\nRAW HISTORY:\n{history_str}\n\nCURRENT PAGE (TRUNCATED):\n{current_page[:5000]}"
        # Gemini requires a HumanMessage if SystemMessage is used in some contexts
        response = await self.llm.ainvoke([
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content=formatted_prompt)
        ])
        return response.content

    def _estimate_tokens(self, text: str) -> int:
        """Rough estimation of token count (4 chars per token)."""
        return len(text) // 4

    def _self_check_code(self, code: str) -> tuple[bool, str]:
        """Validates Python syntax of the generated code."""
        try:
            compile(code, "<string>", "exec")
            return True, ""
        except Exception as e:
            return False, str(e)

    async def _tavily_enrich(self, task_summary: str) -> str:
        """
        Runs a targeted Tavily web search on the task summary and returns a
        formatted block of real-world context (URLs, selectors, current data)
        that the code-generation LLM can reference directly.

        Returns an empty string when Tavily is unavailable or the search fails
        so callers never need to guard against exceptions here.
        """
        if not self.tavily_api_key or _TavilyClient is None:
            return ""
        try:
            client = _TavilyClient(api_key=self.tavily_api_key)
            result = client.search(
                query=task_summary,
                search_depth="basic",
                max_results=3,
                include_answer=True,
            )
            lines = []
            if result.get("answer"):
                lines.append(f"  SUMMARY: {result['answer']}")
            for i, r in enumerate(result.get("results", []), 1):
                title = r.get("title", "")
                url   = r.get("url", "")
                snip  = (r.get("content") or "")[:300].replace("\n", " ")
                lines.append(f"  [{i}] {title}\n      URL: {url}\n      {snip}")
            if not lines:
                return ""
            header = (
                "\nWEB RESEARCH (live Tavily results — use these real URLs, page titles, "
                "and content snippets as ground-truth when writing the script):\n"
            )
            return header + "\n".join(lines) + "\n"
        except Exception as e:
            logger.warning(f"Tavily pre-generation search failed (non-fatal): {e}")
            return ""

    async def run_script_generation(
        self,
        task_summary: str,
        execution_history: List[Dict[str, Any]],
        framework: str = "playwright",
        tool_context: Optional[List[Dict[str, Any]]] = None,
        user_goal: str = "",
        plan_context: str = "",
    ) -> str:
        """
        Generates a production-ready automation script from the execution history.

        Two-layer enrichment:
          1. Pre-generation Tavily search  → real URLs / current page structure
             injected into the LLM prompt so the script targets live endpoints.
          2. Tool-context log              → verified output from successful tool
             runs (supplied by frontend) so the LLM can replicate real values.
          3. user_goal / plan_context      → user's original request and agent
             plan injected so the LLM understands the intent behind the tool calls.

        The system prompt also instructs the LLM that it MAY embed a Tavily
        search step inside the generated script itself for tasks that require
        dynamic URL discovery at runtime.
        """

        # System prompt is assembled entirely from coder.agent.md — role,
        # output rules, and the framework-specific playbook all live in the
        # spec file, not in this Python module.
        SYSTEM_PROMPT = self._build_coder_system_prompt(framework)

        # ── 1. Pre-generation Tavily enrichment ──────────────────────────────
        web_research_section = await self._tavily_enrich(task_summary)
        if web_research_section:
            logger.info(f"Tavily pre-generation enrichment applied ({len(web_research_section)} chars)")

        # ── 2. Tool-context block (success-only, truncated by frontend) ───────
        tool_context_section = ""
        if tool_context:
            tool_context_lines = []
            for i, item in enumerate(tool_context, 1):
                tool_name = item.get("tool_name", "unknown_tool")
                output    = item.get("output") or "(no output)"
                tool_context_lines.append(f"  [{i}] {tool_name}:\n      {output}")
            tool_context_section = (
                "\nTOOL EXECUTION LOG (real outputs from successful tools — "
                "use these URL patterns, selectors, and data values directly in the script):\n"
                + "\n".join(tool_context_lines) + "\n"
            )

        # ── 3. Assemble prompt ────────────────────────────────────────────────
        history_str = json.dumps(execution_history, indent=2)

        # Build enrichment block from saved schedule context
        user_context_section = ""
        if user_goal:
            user_context_section += f"\nORIGINAL USER REQUEST: {user_goal}\n"
        if plan_context:
            try:
                plan_tasks = json.loads(plan_context) if isinstance(plan_context, str) else plan_context
                user_context_section += "\nAGENT EXECUTION PLAN:\n"
                for i, task in enumerate(plan_tasks, 1):
                    user_context_section += f"  {i}. {task.get('title', str(task))}\n"
            except Exception:
                user_context_section += f"\nAGENT PLAN: {plan_context[:600]}\n"

        if framework == "tavily":
            USER_PROMPT = f"""
USER INTENT: {task_summary}
{user_context_section}{tool_context_section}
SEARCH EXECUTION LOG (original Tavily tool calls):
{history_str}

Generate the complete Tavily search script that reproduces this workflow.
Rules: every quote paired, 4-space indentation, no browser imports.
Derive the search query directly from the USER INTENT and the tool execution log above.
"""
        else:
            USER_PROMPT = f"""
USER INTENT: {task_summary}
{user_context_section}{web_research_section}{tool_context_section}
EXECUTION TRACE (Tool Calls):
{history_str}

Generate the complete {framework} script.
Rules: every quote paired, 4-space indentation, correct browser lifecycle management.
If the web research above provides a direct URL for the target service, use it — do NOT
hardcode placeholder URLs like "https://example.com".
"""

        # ── 4. Initial LLM generation ─────────────────────────────────────────
        response = await self.llm.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=USER_PROMPT),
        ])
        content = response.content.strip()
        content = re.sub(r"```(?:python)?\n?(.*?)\n?```", r"\1", content, flags=re.DOTALL)

        # ── 5. Self-validation loop (up to 2 fix passes) ─────────────────────
        for _ in range(2):
            is_valid, error_msg = self._self_check_code(content)
            if is_valid:
                break
            fix_prompt = (
                f"The previous code had a syntax error: {error_msg}\n\n"
                f"Previous code:\n{content}\n\n"
                "Please fix it and return the complete corrected code only."
            )
            response = await self.llm.ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=fix_prompt),
            ])
            content = response.content.strip()
            content = re.sub(r"```(?:python)?\n?(.*?)\n?```", r"\1", content, flags=re.DOTALL)

        return content

