# ATAG.py
import json
import re
from typing import Any, Dict, List, Optional, Annotated, Sequence, TypedDict
from langchain_core.messages import (
    HumanMessage, 
    AIMessage, 
    SystemMessage, 
    BaseMessage,
    messages_to_dict,
    messages_from_dict
)
from src.utils.logger import logger

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

PROMPT_1_INPUT_UNDERSTANDING = """
You are an Input Understanding Agent.

Analyze the user's natural language task request and decide:
- Is there enough information to execute the task immediately?
- Or are there missing/ambiguous inputs that must be collected first?

---

## DECISION LOGIC

Evaluate against THREE conditions:
1. GOAL IS CLEAR        — The desired outcome is unambiguous.
2. TARGET IS CLEAR      — The site, platform, URL, or app is known.
3. INPUTS ARE COMPLETE  — Every field the execution agent needs is already stated.

---

## OUTPUT RULES — STRICT

You must return ONLY ONE of two possible outputs. No explanation. No prose.
No extra text outside the output format.

**CRITICAL JSON FORMATTING REQUIREMENTS:**
- Return a VALID JSON object that starts with { and ends with }
- NO leading whitespace, quotes, or text before the opening brace
- NO markdown code blocks
- NO trailing text after the closing brace
- ALL keys must be quoted with double quotes
- ALL string values must be quoted with double quotes

**WARNING: DO NOT INCLUDE PROMPT INSTRUCTIONS IN YOUR OUTPUT**
- Do NOT include phrases like "and ending with", "starting with", or any other prompt text
- Do NOT include backticks or markdown formatting
- Do NOT include any explanatory text before or after the JSON
- Your output must be PURE JSON only

---

### OUTPUT A — When ALL three conditions are met (no questions needed)

Return this EXACT JSON format:
{
  "status": "READY",
  "task_summary": "<one clear sentence restating the confirmed task>"
}

---

### OUTPUT B — When ANY condition is not met (questions needed)

Return this EXACT JSON format:
{
  "status": "NEEDS_INPUT",
  "form": {
    "title": "<short form title, e.g. 'Book Movie Ticket'>",
    "description": "<one sentence explaining why this form is needed>",
    "sections": [
      {
        "section_title": "<themed section label, e.g. '🎬 Platform & Show'>",
        "fields": [
          {
            "id": "<snake_case_field_id>",
            "label": "<human readable label>",
            "type": "<field type — see allowed types below>",
            "placeholder": "<helpful hint text>",
            "required": true,
            "options": null,
            "note": null
          }
        ]
      }
    ],
    "security_note": "<only include if task involves login/payment/credentials, else null>"
  }
}

---

## ALLOWED FIELD TYPES
Use exactly one of these per field:
| type | When to use |
|---|---|
| text | Short free-text (name, city, address, URL) |
| textarea | Long free-text (notes, description) |
| email | Email address |
| number | Numeric values |
| date | Calendar date picker |
| time | Time picker |
| datetime | Combined date + time |
| dropdown | One selection from a known fixed list |
| radio | One selection from 2–4 short visible options |
| checkbox | Boolean yes/no toggle |
| multi_select| Multiple selections from a known list |
| phone | Phone number |

---

## YOUR INPUT
Analyze this user request and return the correct JSON output:
{user_request}
"""

PROMPT_2_EXECUTION_GENERATOR = """
You are an expert Execution Prompt Generator for an autonomous web agent.

Your goal is to take a user's request and confirmed inputs, and turn them into a high-precision, multi-step execution plan that the agent MUST follow to completion.

## STRATEGIC GUIDELINES
- **TOOL SELECTION:** 
    - Use `tavily_search` ONLY for general web searching, finding URLs, or gathering information from multiple sources.
    - Use `browser_` tools (Playwright) for ALL web interactions, including form filling, button clicking, ticket booking, address availability checks, and data aggregation from a specific site.
- **NO PREMATURE STOPPING:** The agent must not stop after just navigating. It must interact, fill forms, click buttons, and extract final results.
- **INTERACTION FOCUS:** If the task involves a form (booking, checking availability, signing up), explicitly instruct the agent to find the fields, type the data, and click the submit button using browser tools.
- **EXPLORATION:** If an expected element is not immediately visible, the agent MUST use `browser_get_elements` or `browser_click` on parent containers to find the correct interaction points.
- **STRICT ADHERENCE:** Tell the agent: "Do not ask the user for help. Use your tools to solve the problem."

## OUTPUT FORMAT
Generate the execution prompt using EXACTLY this structure. Return as plain text.

TASK: [One-line summary of the final goal]

1. Agent Role & Tools
You are a high-precision web automation agent. You have access to browser tools. Your job is to EXECUTE, not to chat. Do not report status; perform actions.

2. Target
Full confirmed URL(s) or exact search topic.

3. Confirmed Inputs
All collected values as labeled key-value pairs.

4. Execution Steps
Numbered steps. Each step must be actionable:
- Step 1 - Navigate: Go to the target URL.
- Step 2 - Interaction: [Specific instructions on what to find, what to type, and what to click. If the element is not found, search for it using text or generic selectors.]
- Step 3 - Verification: [How to know if the action was successful. Look for confirmation text or new page elements.]
- Step 4 - Completion: [Extract the final data or confirmation message and return it as your final answer.]

COMMAND: Start now by navigating to the target and proceeding through all steps without further input.
"""

# ============================================================
# LANGGRAPH STATE DEFINITIONS
# ============================================================

class AgentState(TypedDict):
    messages: List[BaseMessage]
    atag_phase: str               # "AWAITING_DETAILS", "READY_FOR_PROMPT", "COMPLETED"
    atag_form: Optional[dict]
    atag_prompt: Optional[str]
    execution_result: Optional[str]
    user_id: str
    chat_id: str
    retry_count: int              # Track retries for execution
    last_error: Optional[str]     # Store last error for critic analysis


PROMPT_3_CRITIC = """
You are an Execution Critic.

Analyze why the execution failed and produce a CONCISE, REVISED execution prompt.

## RULES
- Keep the revised prompt under 1000 tokens.
- Focus ONLY on the step that failed.
- If an element was missing, suggest using text-based selectors or generic tags.
- DO NOT repeat the entire original prompt if not necessary.

## OUTPUT FORMAT
Return ONLY the revised execution prompt as plain text.

User request: {user_request}
Failed prompt: {failed_prompt}
Error: {error_msg}
"""

class ATAGProcessor:
    """Processes user requests using a decoupled two-step pipeline.

    Step 1: Input Understanding (Identify if information is missing).
    Step 2: Execution Prompt Generation (Assemble final instructions).
    Step 3: Critic (Analyze failures and revise prompts).
    """
    def __init__(self, llm):
        self.llm = llm

    def _parse_json_safely(self, text: str) -> Dict[str, Any]:
        """Robust JSON extraction from LLM responses with fallback strategies."""
        try:
            cleaned = re.sub(r"```json\s*|\s*```", "", text).strip()
            start = cleaned.find('{')
            end = cleaned.rfind('}')
            if start != -1 and end != -1 and end > start:
                return json.loads(cleaned[start:end+1])
            return json.loads(cleaned)
        except Exception as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return {"status": "ERROR", "message": "Invalid JSON format"}

    async def run_input_understanding(self, original_request: str) -> Dict[str, Any]:
        """Runs Agent 1 to check completeness and generate form schema if needed."""
        system_prefix = (
            "You are a JSON output engine. Your ONLY job is to return valid JSON. "
            "Your ENTIRE response must be a valid JSON object. No markdown. No explanations.\n\n"
        )
        formatted_prompt = system_prefix + PROMPT_1_INPUT_UNDERSTANDING.replace("{user_request}", original_request)
        response = await self.llm.ainvoke([SystemMessage(content=formatted_prompt)])
        return self._parse_json_safely(response.content)

    async def run_execution_generation(self, original_request: str, confirmed_inputs: str) -> str:
        """Runs Agent 2 to build the downstream markdown execution prompt."""
        formatted_prompt = PROMPT_2_EXECUTION_GENERATOR.replace(
            "{user_request}", original_request
        ).replace(
            "{confirmed_inputs}", confirmed_inputs
        )
        response = await self.llm.ainvoke([SystemMessage(content=formatted_prompt)])
        return response.content

    async def run_critic(self, original_request: str, failed_prompt: str, error_msg: str) -> str:
        """Runs Agent 4 (Critic) to analyze failure and revise the prompt."""
        formatted_prompt = PROMPT_3_CRITIC.replace(
            "{user_request}", original_request
        ).replace(
            "{failed_prompt}", failed_prompt
        ).replace(
            "{error_msg}", error_msg
        )
        response = await self.llm.ainvoke([SystemMessage(content=formatted_prompt)])
        return response.content
        response = await self.llm.ainvoke([SystemMessage(content=formatted_prompt)])
        return self._parse_json_safely(response.content)

    async def run_execution_generation(self, original_request: str, confirmed_inputs: str) -> str:
        """Runs Agent 2 to build the downstream markdown execution prompt."""
        formatted_prompt = PROMPT_2_EXECUTION_GENERATOR.replace(
            "{user_request}", original_request
        ).replace(
            "{confirmed_inputs}", confirmed_inputs
        )
        response = await self.llm.ainvoke([SystemMessage(content=formatted_prompt)])
        return response.content