import json
import re
from typing import Any, Dict, List, Optional, Annotated, Sequence, TypedDict
from langchain_core.messages import (
    HumanMessage,
    SystemMessage, 
    BaseMessage,
    messages_to_dict,
    messages_from_dict
)
# Assuming logger is available or will be provided
import logging
logger = logging.getLogger(__name__)

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
You are an Input Understanding Agent. Your ONLY job is to analyze user requests and output a JSON object.

Analyze the user\"s natural language task request and determine:
- The primary goal of the user.
- If there\"s enough information to execute the task directly.
- If there are missing or ambiguous inputs that require clarification or discovery.

---

## DECISION LOGIC

Evaluate against FOUR conditions:
1.  **GOAL IS CLEAR**        — The desired outcome is unambiguous (e.g., \"book a flight\", \"check address availability\").
2.  **TARGET IS CLEAR**      — The specific site, platform, URL, or app is known (e.g., \"frontier.com\", \"LinkedIn\"). If not, can it be *discovered* via search?
3.  **INPUTS ARE COMPLETE**  — Every critical piece of information needed for execution is provided (e.g., address, dates, names, quantities). If not, can it be *discovered* or *must* it be asked?
4.  **TASK TYPE**            — Categorize the task (e.g., \"Navigation\", \"Booking\", \"Data Extraction\", \"Search\", \"Automation\", \"Information Gathering\", \"Upload/Download\").

---

## OUTPUT RULES — STRICT JSON ONLY

You must return ONLY ONE of two possible JSON outputs. No explanation. No prose. No extra text outside the output object.

**CRITICAL JSON FORMATTING REQUIREMENTS:**
- Return a VALID JSON object that starts with `{` and ends with `}`.
- NO leading whitespace, quotes, or text before the opening brace.
- NO markdown code blocks (e.g., ```json).
- NO trailing text after the closing brace.
- ALL keys must be quoted with double quotes.
- ALL string values must be quoted with double quotes.

**WARNING: DO NOT INCLUDE PROMPT INSTRUCTIONS IN YOUR OUTPUT**
- Do NOT include phrases like \"and ending with\", \"starting with\", or any other prompt text.
- Do NOT include backticks or markdown formatting.
- Do NOT include any explanatory text before or after the JSON.
- Your output must be PURE JSON only.

---

### OUTPUT A — When ALL conditions are met OR can be autonomously discovered (no questions needed from user)

Return this EXACT JSON format:
{
  \"status\": \"READY\",
  \"task_type\": \"<inferred task type, e.g., \\\\'Address Check\\\\'>\",
  \"task_summary\": \"<one clear sentence restating the confirmed task>\",
  \"confirmed_inputs\": {
    \"<input_key_1>\": \"<value_1>\",
    \"<input_key_2>\": \"<value_2>\"
  },
  \"discovery_strategy\": \"<\\\\'direct_execution\\\\' if all info is present, \\\\'tavily_search_for_url\\\\' if target is missing, \\\\'tavily_search_for_details\\\\' if inputs are missing but discoverable>\"
}

Example for \"check address availability for 2005 Kentucky Ave, Poplar Bluff, MO 63901 on frontier.com\":
{
  \"status\": \"READY\",
  \"task_type\": \"Address Check\",
  \"task_summary\": \"Check internet service availability for 2005 Kentucky Ave, Poplar Bluff, MO 63901 on frontier.com.\",
  \"confirmed_inputs\": {
    \"address\": \"2005 Kentucky Ave, Poplar Bluff, MO 63901\",
    \"website\": \"frontier.com\"
  },
  \"discovery_strategy\": \"direct_execution\"
}

Example for \"book a ticket for karuppu movie\":
{
  \"status\": \"READY\",
  \"task_type\": \"Movie Booking\",
  \"task_summary\": \"Find showtimes and book a ticket for the movie Karuppu.\",
  \"confirmed_inputs\": {
    \"movie_title\": \"Karuppu\"
  },
  \"discovery_strategy\": \"tavily_search_for_details\" 
}

---

### OUTPUT B — When CRITICAL information is missing and CANNOT be autonomously discovered (questions needed from user)

Return this EXACT JSON format:
{
  \"status\": \"NEEDS_INPUT\",
  \"task_type\": \"<inferred task type, e.g., \\\\'Movie Booking\\\\'>\",
  \"task_summary\": \"<one clear sentence restating the partial task>\",
  \"form\": {
    \"title\": \"<short form title, e.g. \\\\'Book Movie Ticket\\\\'>\",
    \"description\": \"<one sentence explaining why this form is needed>\",
    \"sections\": [
      {
        \"section_title\": \"<themed section label, e.g. \\\\'🎬 Platform & Show\\\\'>\",
        \"fields\": [
          {
            \"id\": \"<snake_case_field_id>\",
            \"label\": \"<human readable label>\",
            \"type\": \"<field type — see allowed types below>\",
            \"placeholder\": \"<helpful hint text>\",
            \"required\": true,
            \"options\": null,
            \"note\": null
          }
        ]
      }
    ],
    \"security_note\": \"<only include if task involves login/payment/credentials, else null>\"
  }
}

Example for \"book a flight\":
{
  \"status\": \"NEEDS_INPUT\",
  \"task_type\": \"Flight Booking\",
  \"task_summary\": \"Book a flight.\",
  \"form\": {
    \"title\": \"Flight Booking Details\",
    \"description\": \"Please provide the necessary details to book your flight.\",
    \"sections\": [
      {
        \"section_title\": \"Travel Information\",
        \"fields\": [
          {\"id\": \"origin\", \"label\": \"Origin City/Airport\", \"type\": \"text\", \"placeholder\": \"e.g., New York\", \"required\": true, \"options\": null, \"note\": null},
          {\"id\": \"destination\", \"label\": \"Destination City/Airport\", \"type\": \"text\", \"placeholder\": \"e.g., London\", \"required\": true, \"options\": null, \"note\": null},
          {\"id\": \"departure_date\", \"label\": \"Departure Date\", \"type\": \"date\", \"placeholder\": \"\", \"required\": true, \"options\": null, \"note\": null},
          {\"id\": \"return_date\", \"label\": \"Return Date (optional)\", \"type\": \"date\", \"placeholder\": \"\", \"required\": false, \"options\": null, \"note\": null},
          {\"id\": \"passengers\", \"label\": \"Number of Passengers\", \"type\": \"number\", \"placeholder\": \"1\", \"required\": true, \"options\": null, \"note\": null}
        ]
      }
    ],
    \"security_note\": null
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
You are an expert Browser Mission Architect. Your goal is to translate a user's request into a high-level, robust "Mission Objective" for an autonomous browser agent.

## MISSION DESIGN PRINCIPLES
1. **Goal-Oriented**: Focus on the final outcome (e.g., "Extract the price and shipping date") rather than individual clicks.
2. **Direct Navigation**: If the user provides a specific URL (e.g., "go to google.com"), the mission is strictly to navigate to that URL and wait for further instructions. Do NOT perform a search or click anything unless explicitly asked.
3. **Expert Playbooks**: Incorporate these strategies into the mission description:
    - **Address Autocomplete**: "Type the address slowly and MUST click the matching suggestion from the dropdown to activate the form."
    - **Anti-Bot**: "Interact with the page like a human. If a captcha appears, wait or try to solve it."
    - **Data Extraction**: "Extract all relevant fields into a structured format. If there are multiple pages, navigate through all of them."
4. **Constraint-Aware**: Mention specific inputs that MUST be used.
5. **No Redundant Loops**: Explicitly instruct the agent to STOP once the result page is reached and data is extracted. Do NOT re-navigate to the start URL once interaction has begun.

## OUTPUT FORMAT
TASK: {task_summary}

REASONING:
[Provide a brief explanation of the strategy chosen for this task. If it's a direct navigation, explain that you are only navigating.]

PLAN:
[Provide a JSON array of tasks for the UI. Each task should have: id, title, description, status ('pending'), priority, level, dependencies (ids), and subtasks (array of {id, title, description, status: 'pending', priority}).]

MISSION OBJECTIVE:
[Provide a detailed, numbered set of instructions that the autonomous agent will follow. Include the target URL and all confirmed inputs.]

CRITICAL CONSTRAINTS:
- {confirmed_inputs_list}

COMMAND: Execute the mission objective autonomously. If you encounter a persistent blocker, report the exact error.
"""

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

PROMPT_3_CRITIC = """
You are an Execution Critic & Problem Solver.

Analyze the failure below and provide a REVISED instruction for the specific failed step.

## FAILURE ANALYSIS
1. **Root Cause:** Why did the last tool call fail? (e.g., "The address input was covered by a privacy banner").
2. **Visual Clues:** Based on the page state, where is the element actually located?
3. **Recovery Strategy:** What is the exact sequence to fix this? (e.g., "1. Click the 'Close' button on the banner. 2. Re-type the address. 3. Wait for the dropdown.")

## OUTPUT FORMAT
Return your response in two parts:

THINKING: [Your analysis of the failure and the fix]

REVISED PROMPT:
[The complete, updated execution prompt for the agent, focusing on the recovery strategy.]
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


PROMPT_4_PAGE_ANALYZER = """
You are a Web Interaction Diagnostic Expert.

Your goal is to analyze the "Gap" between the current page state and the user's goal.

## DYNAMIC DIAGNOSTIC CHECKLIST
1. **Interactivity Check:** Is the primary action button (e.g., "Submit", "Check", "Continue") disabled or hidden?
2. **Root Cause Analysis:** If a button is disabled, WHY? 
    - Is there a required field that looks empty?
    - Did the agent type text but fail to select a "suggestion" from a dropdown?
    - Is there a validation error message (usually in red text) visible?
    - Is there a transparent overlay or popup blocking the click?
3. **Visual Search:** If the agent says "I can't find X", look for synonyms or parent containers that might hold the element.

## OUTPUT FORMAT
REASONING:
[Perform a diagnostic. Example: "The 'Check Availability' button is disabled. I see the address is typed, but the site requires a selection from the 'pac-container' dropdown to validate the form. I need to re-click the input and select the first suggestion."]

REFINED PROMPT:
[A precise instruction to fix the specific diagnostic issue. Focus on UNBLOCKING the UI first.]
"""

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
    def __init__(self, llm):
        self.llm = llm

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

    async def run_input_understanding(self, original_request: str, history_context: str = "") -> Dict[str, Any]:
        """Runs Agent 1 to check completeness and generate form schema if needed."""
        system_prefix = (
            "You are a JSON output engine. Your ONLY job is to return valid JSON. "
            "Your ENTIRE response must be a valid JSON object. No markdown. No explanations.\n\n"
        )
        
        context_prompt = ""
        if history_context:
            context_prompt = f"\n\nRECENT CHAT HISTORY:\n{history_context}\n\nUse this history to understand the user's current request."

        formatted_prompt = system_prefix + PROMPT_1_INPUT_UNDERSTANDING.replace("{user_request}", original_request) + context_prompt
        response = await self.llm.ainvoke([SystemMessage(content=formatted_prompt)])
        return self._parse_json_safely(response.content)

    async def run_execution_generation(self, user_request: str, task_summary: str, confirmed_inputs: Dict[str, Any], discovery_strategy: str) -> str:
        """Runs Agent 2 to build the high-level mission objective for the native agent."""
        # Format confirmed_inputs for display in the prompt
        confirmed_inputs_list = "\n".join(
            [f"- {k.replace('_', ' ').title()}: {v}" for k, v in confirmed_inputs.items()]
        ) if confirmed_inputs else "None"

        formatted_prompt = PROMPT_2_EXECUTION_GENERATOR.replace(
            "{task_summary}", task_summary
        ).replace(
            "{confirmed_inputs_list}", confirmed_inputs_list
        ).replace(
            "{target_info}", f"https://{confirmed_inputs.get('website', 'google.com')}"
        )
        response = await self.llm.ainvoke([SystemMessage(content=formatted_prompt)])
        return response.content

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
        """Runs Agent 3 (Analyzer) to think about the page state and refine the prompt."""
        formatted_prompt = PROMPT_4_PAGE_ANALYZER.replace(
            "{user_goal}", goal
        ).replace(
            "{page_content}", page_content[:15000] # Truncate to avoid context limits
        ).replace(
            "{last_error}", last_error or "None"
        )
        response = await self.llm.ainvoke([SystemMessage(content=formatted_prompt)])
        return response.content

    async def run_critic(self, user_request: str, failed_prompt: str, error_msg: str) -> str:
        """Runs Agent 4 (Critic) to analyze failure and revise the prompt."""
        formatted_prompt = PROMPT_3_CRITIC.replace(
            "{user_request}", user_request
        ).replace(
            "{failed_prompt}", failed_prompt
        ).replace(
            "{error_msg}", error_msg
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

    async def run_script_generation(self, task_summary: str, execution_history: List[Dict[str, Any]], framework: str = "playwright") -> str:
        """Generates a production-ready script based on the execution history using the specified framework."""
        
        if framework == "playwright":
            SYSTEM_PROMPT = """
            You are a Senior Python Automation Engineer specializing in Playwright.

            TASK:
            Convert browser execution traces into a COMPLETE, EXECUTABLE, PRODUCTION-READY Python Playwright script.

            OUTPUT RULES (ABSOLUTE)
            * Return ONLY raw Python code.
            * Do NOT use markdown.
            * Do NOT use ```python blocks.
            * Do NOT provide explanations or notes.
            * Script must be directly runnable.

            PARALLEL EXECUTION REQUIREMENTS:
            * Use a UNIQUE temporary user_data_dir for every run to avoid profile locks.
            * Use a random available port for remote debugging if needed.
            * Ensure the script is HEADLESS by default for server-side parallel runs.

            SCRIPT REQUIREMENTS:
            * All imports (asyncio, json, playwright, pathlib, tempfile).
            * Helper functions (e.g., get_downloads_dir).
            * main() function returning the final result.
            * asyncio.run(main()) at the end.
            * Robust error handling (try/except/finally).
            * Data extraction logic returning structured JSON.

            PLAYWRIGHT CONFIGURATION:
            * browser = await p.chromium.launch(headless=False, args=["--no-sandbox", "--start-maximized"])
            * context = await browser.new_context()
            * page = await context.new_page()
            """
        else:
            SYSTEM_PROMPT = """
            You are a Senior Python Automation Engineer specializing in the 'browser-use' library.

            TASK:
            Convert browser execution traces into a COMPLETE, EXECUTABLE Python script using 'browser-use'.

            OUTPUT RULES (ABSOLUTE)
            * Return ONLY raw Python code.
            * Do NOT use markdown.
            * Do NOT use ```python blocks.
            * Do NOT provide explanations or notes.

            SCRIPT REQUIREMENTS:
            * All imports (asyncio, browser_use).
            * Use Agent from browser_use.
            * Use Controller if needed for custom actions.
            * main() function returning the final result.
            * asyncio.run(main()) at the end.

            BROWSER-USE CONFIGURATION:
            * Use the standard Agent(task=..., llm=...) pattern.
            * The task should be derived from the user intent and execution trace.
            """

        history_str = json.dumps(execution_history, indent=2)
        USER_PROMPT = f"""
        USER INTENT: {task_summary}
        EXECUTION TRACE (Tool Calls):
        {history_str}

        Generate the {framework} script. Ensure every quote is paired, indentation is 4 spaces, and the browser lifecycle is correctly managed.
        """

        # Initial generation
        response = await self.llm.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=USER_PROMPT)
        ])

        content = response.content.strip()
        # Remove markdown code blocks if the LLM ignored the rule
        content = re.sub(r"```(?:python)?\n?(.*?)\n?```", r"\1", content, flags=re.DOTALL)

        # Self-validation loop
        max_retries = 2
        for i in range(max_retries):
            is_valid, error_msg = self._self_check_code(content)
            if is_valid:
                break
            
            fix_prompt = f"The previous code had a syntax error: {error_msg}\n\nPrevious code:\n{content}\n\nPlease fix and return the complete corrected code."
            response = await self.llm.ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=fix_prompt)
            ])
            content = response.content.strip()
            content = re.sub(r"```(?:python)?\n?(.*?)\n?```", r"\1", content, flags=re.DOTALL)

        return content

