import json
import re
from typing import List, Any
from sqlalchemy import select, and_

from src.database.chat_db import AsyncSessionLocal, MemoryEpisodic
from src.utils.logger import logger
from langchain_core.messages import HumanMessage

CORE_TOOLS = {
    "browser_navigate",
    "browser_get_state",
    "browser_screenshot",
    "browser_wait",
    "browser_key_press",
}

async def get_historical_tools(user_id: str, domain: str) -> List[str]:
    """Retrieve the names of tools successfully used in previous runs on this domain."""
    if not domain or domain == "general":
        return []
    
    tools = set()
    try:
        async with AsyncSessionLocal() as db:
            ep_res = await db.execute(
                select(MemoryEpisodic)
                .where(and_(
                    MemoryEpisodic.user_id == user_id,
                    MemoryEpisodic.domain == domain,
                    MemoryEpisodic.outcome == "SUCCESS",
                    MemoryEpisodic.confidence_score > 0.1,
                ))
                .order_by(MemoryEpisodic.confidence_score.desc())
                .limit(5)
            )
            episodes = ep_res.scalars().all()
            for ep in episodes:
                if ep.key_steps:
                    try:
                        steps = json.loads(ep.key_steps)
                        for step in steps:
                            tool_name = step.get("tool")
                            if tool_name:
                                tools.add(tool_name)
                    except Exception as parse_err:
                        logger.warning(f"[ToolMemory] Error parsing key_steps in episodic memory {ep.id}: {parse_err}")
    except Exception as e:
        logger.error(f"[ToolMemory] Error retrieving historical tools: {e}")
    
    return list(tools)

async def classify_tools_semantically(
    tools: List[Any], 
    task_summary: str, 
    llm: Any
) -> List[str]:
    """Use a lightweight LLM call to classify which non-core tools are relevant to the current task."""
    if not tools:
        return []
        
    tool_info = []
    for t in tools:
        desc = getattr(t, "description", "")
        # Keep descriptions short to save tokens
        desc_short = desc.split(".")[0] if desc else ""
        tool_info.append({"name": t.name, "description": desc_short})
        
    prompt = (
        "You are a precise routing system. Given a task summary and a list of available tools, "
        "identify the subset of tools that are relevant or required to complete the task.\n\n"
        f"Task: \"{task_summary}\"\n\n"
        "Available Tools:\n"
        f"{json.dumps(tool_info, indent=2)}\n\n"
        "Return ONLY a JSON object containing the list of matching tool names, formatted exactly like this:\n"
        "{\"relevant_tools\": [\"tool_name_1\", \"tool_name_2\"]}\n"
        "If a tool is not explicitly relevant to the user request's functional steps, do NOT include it. "
        "Return absolutely nothing else, no markdown formatting (like ```json), no explanations, just the JSON string."
    )
    
    try:
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        content = resp.content.strip()
        m = re.search(r'\{.*\}', content, re.DOTALL)
        if m:
            data = json.loads(m.group())
            return data.get("relevant_tools", [])
    except Exception as e:
        logger.warning(f"[ToolMemory] LLM tool classification failed: {e}")
        
    return []

async def filter_tools_semantically(
    tools: List[Any],
    task_summary: str,
    user_id: str,
    domain: str,
    memory_service: Any,
    llm: Any
) -> List[Any]:
    """Filter tools dynamically based on core tools list, domain memory history, and semantic relevance."""
    if not tools:
        return []
        
    # 1. Identify core tools (always preserve these)
    core_filtered = [t for t in tools if t.name in CORE_TOOLS]
    non_core = [t for t in tools if t.name not in CORE_TOOLS]
    
    if not non_core:
        return core_filtered
        
    # 2. Get historically successful tools for this domain
    historical_names = await get_historical_tools(user_id, domain)
    logger.info(f"[ToolMemory] Historically successful tools for domain '{domain}': {historical_names}")
    
    # 3. Classify remaining tools semantically using the LLM
    classified_names = await classify_tools_semantically(non_core, task_summary, llm)
    logger.info(f"[ToolMemory] Semantically classified tools for task '{task_summary}': {classified_names}")
    
    # 4. Merge all selected tool names
    selected_names = set(historical_names + classified_names + list(CORE_TOOLS))
    
    # 5. Build final list of tool objects preserving order from input list
    final_tools = [t for t in tools if t.name in selected_names]
    
    # Fallback: if semantic filter left us with only core tools, but there were non-core tools available,
    # keep all tools as a fallback safety-net
    if len(final_tools) == len(core_filtered) and len(tools) > len(core_filtered):
        logger.info(f"[ToolMemory] Semantic filter selected only core tools. Keeping all tools as fallback.")
        return tools
        
    logger.info(f"[ToolMemory] Filtered tools: {[t.name for t in final_tools]} (from {len(tools)} down to {len(final_tools)})")
    return final_tools
