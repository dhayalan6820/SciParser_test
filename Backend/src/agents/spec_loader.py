"""
AgentSpecLoader — parses `*.agent.md` files (YAML frontmatter + markdown body)
into `AgentSpec` objects and turns them into either:
  - a CrewAI `Agent` (for agents that reason without a live tool-calling loop,
    e.g. Planner, Coder), or
  - a flat system-prompt string (for the Browser agent, which plugs into the
    existing LangGraph ReAct tool-calling loop in brain.py).

No agent role/goal/backstory/playbook/tool-list is hardcoded in Python.
Editing a `.md` file changes agent behavior immediately (specs are cached but
`reload=True` forces a re-read) — no code change or redeploy needed.

Tool selection is dynamic, never hardcoded: `tool_filter` in the frontmatter
is a glob pattern (or comma-separated list of patterns) matched against the
NAMES of tools discovered live via MCP (`MCPToolManager.get_tools()`). This
means:
  - Agents never enumerate specific tool names in Python.
  - Adding a new MCP server (see mcp_agent.load_extra_mcp_servers) makes its
    tools show up in `get_tools()` automatically; any agent whose
    `tool_filter` matches the new tool names (or uses `tool_filter: "*"`)
    picks them up on the next request with zero code changes.
"""
import os
import re
import glob
import fnmatch
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

from src import config

logger = logging.getLogger(__name__)

SPECS_DIR = os.path.join(os.path.dirname(__file__), "specs")


@dataclass
class AgentSpec:
    name: str
    role: str
    goal: str
    backstory: str
    sections: Dict[str, str] = field(default_factory=dict)
    tool_filter: str = "*"
    model: Optional[str] = None
    temperature: float = 0.2
    source_path: str = ""


def _parse_agent_md(path: str) -> AgentSpec:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not match:
        raise ValueError(f"{path}: expected a '---' YAML frontmatter block at the top of the file.")

    frontmatter_raw, body = match.group(1), match.group(2)
    frontmatter = yaml.safe_load(frontmatter_raw) or {}

    missing = [k for k in ("name", "role", "goal") if k not in frontmatter]
    if missing:
        raise ValueError(f"{path}: missing required frontmatter field(s): {missing}")

    # Split the body into H2 (`## Title`) sections so any section name can be
    # added later (Backstory, Playbook, Recovery Protocol, Output Format, ...)
    # without touching this parser.
    sections: Dict[str, str] = {}
    current_title: Optional[str] = None
    buffer: List[str] = []
    for line in body.splitlines():
        header = re.match(r"^##\s+(.*)", line)
        if header:
            if current_title is not None:
                sections[current_title] = "\n".join(buffer).strip()
            current_title = header.group(1).strip()
            buffer = []
        else:
            buffer.append(line)
    if current_title is not None:
        sections[current_title] = "\n".join(buffer).strip()

    return AgentSpec(
        name=frontmatter["name"],
        role=frontmatter["role"],
        goal=frontmatter["goal"],
        backstory=sections.get("Backstory", "").strip(),
        sections=sections,
        tool_filter=str(frontmatter.get("tool_filter", "*")),
        model=frontmatter.get("model"),
        temperature=float(frontmatter.get("temperature", 0.2)),
        source_path=path,
    )


_SPEC_CACHE: Dict[str, AgentSpec] = {}


def load_spec(agent_name: str, reload: bool = False) -> AgentSpec:
    """Loads `<agent_name>.agent.md` from `Backend/src/agents/specs/`."""
    if not reload and agent_name in _SPEC_CACHE:
        return _SPEC_CACHE[agent_name]
    path = os.path.join(SPECS_DIR, f"{agent_name}.agent.md")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No agent spec found at {path}. Available specs: {list_specs()}"
        )
    spec = _parse_agent_md(path)
    _SPEC_CACHE[agent_name] = spec
    return spec


def list_specs() -> List[str]:
    return sorted(
        os.path.basename(p)[: -len(".agent.md")]
        for p in glob.glob(os.path.join(SPECS_DIR, "*.agent.md"))
    )


def filter_tools(tools: List[Any], pattern: str) -> List[Any]:
    """
    Filters a live, MCP-discovered tool list by glob pattern(s) matched
    against each tool's `.name`.

    `pattern` may be:
      - "*" or "all"  -> every discovered tool (default)
      - "none"        -> no tools (pure-reasoning agent)
      - "browser_*,tavily_search" -> comma-separated glob patterns

    Because this always operates on the live tool list passed in (never a
    hardcoded list), tools from any newly added MCP server are automatically
    included whenever their names satisfy the pattern.
    """
    normalized = (pattern or "*").strip()
    if normalized.lower() in ("*", "all"):
        return list(tools)
    if normalized.lower() == "none":
        return []
    patterns = [p.strip() for p in normalized.split(",") if p.strip()]
    return [
        t for t in tools
        if any(fnmatch.fnmatch(getattr(t, "name", ""), p) for p in patterns)
    ]


# Maps each Observe -> Plan -> Execute -> Verify -> Recover -> Complete stage
# (see Backend/src/agents/workflows.json) to the browser.agent.md section
# titles that are actually relevant to it. `build_system_prompt(spec,
# stage=...)` uses this to send only the sections a given LLM call needs
# instead of the full ~2KB spec on every single call — e.g. the Critic
# (Recover stage) never needs Stealth Behavior or Form Handling, and the
# per-turn Planner call doesn't need the Recovery Protocol text at all
# unless a failure actually occurred. Sections not listed under any stage
# (e.g. "Backstory") are considered stage-agnostic and always included.
_STAGE_AGNOSTIC_SECTIONS = {"Backstory"}
_STAGE_SECTION_MAP: Dict[str, List[str]] = {
    "plan": [
        "Reasoning Format",
        "Completion Rules",
        "Failure Rules",
        "Safety Rules",
    ],
    "observe": [
        "Observation Rules",
        "Overlay & Popup Handling (mandatory priority)",
    ],
    "execute": [
        "Stealth Behavior (mandatory on every mission)",
        "Form Handling",
        "Safety Rules",
    ],
    "verify": [
        "Observation Rules",
        "Completion Rules",
    ],
    "recover": [
        "Error Recovery & Retry Policy",
        "Recovery Protocol (used by the Critic on failure)",
        "Page Analysis (Diagnostic Mode)",
    ],
    "complete": [
        "Completion Rules",
        "Failure Rules",
    ],
}


def build_system_prompt(
    spec: AgentSpec,
    extra_sections: Optional[Dict[str, str]] = None,
    stage: Optional[str] = None,
) -> str:
    """
    Assembles a flat system-prompt string from an AgentSpec's sections. Used
    by agents that plug directly into a LangChain/LangGraph tool-calling loop
    (currently: the Browser agent) rather than running as a full CrewAI Agent.

    `stage` restricts the assembled prompt to the sections relevant to one
    step of the Observe/Plan/Execute/Verify/Recover/Complete loop (see
    `_STAGE_SECTION_MAP` and `Backend/src/agents/workflows.json`), instead of
    always sending the agent's full spec regardless of what the call is
    actually for. Pass `stage=None` (the default) to get the full prompt —
    this preserves existing behavior for any caller that hasn't opted into
    stage-based loading yet.
    """
    parts = [f"# {spec.role}", f"## Goal\n{spec.goal}"]
    if spec.backstory:
        parts.append(f"## Backstory\n{spec.backstory}")

    allowed_titles: Optional[set] = None
    if stage:
        normalized_stage = stage.strip().lower()
        stage_titles = _STAGE_SECTION_MAP.get(normalized_stage)
        if stage_titles is None:
            logger.warning(
                f"[spec_loader] Unknown stage '{stage}' — falling back to the full spec. "
                f"Known stages: {sorted(_STAGE_SECTION_MAP)}"
            )
        else:
            allowed_titles = _STAGE_AGNOSTIC_SECTIONS | set(stage_titles)

    for title, content in spec.sections.items():
        if title == "Backstory" or not content.strip():
            continue
        if allowed_titles is not None and title not in allowed_titles:
            continue
        parts.append(f"## {title}\n{content}")
    if extra_sections:
        for title, content in extra_sections.items():
            if content and content.strip():
                parts.append(f"## {title}\n{content}")
    return "\n\n---\n\n".join(parts)


def build_llm(spec: AgentSpec):
    """Builds a CrewAI LLM object for the given spec, defaulting to the same
    OpenRouter model/credentials used everywhere else in the backend."""
    from crewai import LLM
    model = spec.model or f"openrouter/{config.OPENROUTER_MODEL}"
    return LLM(
        model=model,
        temperature=spec.temperature,
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
    )


def build_crewai_agent(agent_name: str, tools: Optional[List[Any]] = None, reload: bool = False):
    """
    Builds a `crewai.Agent` from `<agent_name>.agent.md`.

    `tools` should be the LIVE tool list discovered via
    `MCPToolManager.get_tools()` for this session — never a hardcoded list.
    It is filtered through `spec.tool_filter` before being wrapped for CrewAI.
    Pass `tools=None` for pure-reasoning agents (Planner, Coder).
    """
    from crewai import Agent as CrewAgent
    from crewai.tools import BaseTool as CrewBaseTool

    spec = load_spec(agent_name, reload=reload)
    resolved = filter_tools(tools or [], spec.tool_filter)

    crew_tools = []
    for t in resolved:
        try:
            crew_tools.append(CrewBaseTool.from_langchain(t))
        except Exception as e:
            logger.warning(
                f"[spec_loader] Skipping tool '{getattr(t, 'name', '?')}' for agent "
                f"'{agent_name}' — could not adapt for CrewAI (likely async-only, "
                f"which CrewAI's sync tool runner can't call directly): {e}"
            )

    return CrewAgent(
        role=spec.role,
        goal=spec.goal,
        backstory=spec.backstory or spec.goal,
        tools=crew_tools,
        llm=build_llm(spec),
        verbose=False,
        allow_delegation=False,
    )
