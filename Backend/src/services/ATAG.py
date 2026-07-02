import json
import os
import re
from typing import Any, Dict, List, Optional, Annotated, Sequence, TypedDict
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

## STEALTH BEHAVIOR (MANDATORY — apply to every mission)
To avoid bot-detection systems (DataDome, Akamai, Cloudflare) the agent MUST behave like a real human:
- **Scroll before interacting**: Before clicking any button or filling any field, call `browser_scroll` to scroll the element into view first.
- **Hover before clicking**: Always call `browser_hover` to move the mouse to the target element before calling `browser_click`. Never click without hovering first.
- **Add natural delays**: Call `browser_wait` with 200–600 ms between consecutive actions. After a page load or navigation, wait at least 800 ms before the first interaction.
- **Do not rush after load**: Never click, type, or scroll within the first 1 second of a new page loading. Always `browser_wait` 800–1200 ms after any navigation.
- **Type slowly**: When using `browser_type`, type the full value but follow it with a `browser_wait` of 300–500 ms to allow autocomplete or validation to trigger.
- **Avoid mechanical patterns**: Do not click the same element repeatedly in quick succession. If a click does not work, wait 500 ms and scroll before retrying.

## OUTPUT FORMAT
TASK: {task_summary}

{prior_context}

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
    def __init__(self, llm, tavily_api_key: Optional[str] = None):
        self.llm = llm
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")

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

    async def run_execution_generation(self, user_request: str, task_summary: str, confirmed_inputs: Dict[str, Any], discovery_strategy: str, prior_context: str = "") -> str:
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
        ).replace(
            "{prior_context}", prior_context
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

        TAVILY_RUNTIME_BLOCK = """
OPTIONAL TAVILY RUNTIME SEARCH (use ONLY when the task requires discovering a URL or live data at runtime):
* import os; from tavily import TavilyClient
* client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
* results = client.search(query="...", search_depth="basic", max_results=3)
* Use the first result URL as the navigation target when the target URL is not already known.
* Always fall back gracefully if results are empty.
"""

        if framework == "playwright":
            SYSTEM_PROMPT = f"""
You are a Senior Python Automation Engineer specialising in Playwright.

TASK:
Convert browser execution traces into a COMPLETE, EXECUTABLE, PRODUCTION-READY
Python Playwright script.  You have been given real-world web research and tool
outputs — use them to write a script that targets the exact live URLs, selectors,
and data values observed, rather than making generic guesses.

OUTPUT RULES (ABSOLUTE)
* Return ONLY raw Python code — no markdown, no ``` blocks, no explanations.
* Script must be directly runnable with: python script.py

EXECUTION ENVIRONMENT
* The script runs on a Linux server (Replit / CI) with NO display and NO GPU.
* Playwright Chromium is pre-installed — do NOT run `playwright install` inside the script.
* MUST pass these args every time: --no-sandbox, --disable-dev-shm-usage,
  --disable-gpu, --disable-setuid-sandbox

REQUIRED SCRIPT STRUCTURE
* All imports: asyncio, json, os, tempfile, playwright.async_api.
* A main() async function that returns a structured JSON result dict.
* asyncio.run(main()) at the bottom.
* Robust try/except/finally — always close browser/context in finally.
* Data extraction returns structured JSON — never bare print statements.
{TAVILY_RUNTIME_BLOCK}
PLAYWRIGHT BROWSER CONFIGURATION — copy this pattern exactly:
    CHROMIUM_ARGS = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-setuid-sandbox",
    ]
    async with async_playwright() as p:
        # Use launch_persistent_context so profile isolation is handled correctly
        user_data_dir = tempfile.mkdtemp()
        context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=True,
            args=CHROMIUM_ARGS,
        )
        page = await context.new_page()
        try:
            # --- task steps here ---
            pass
        finally:
            await context.close()
"""
        elif framework == "tavily":
            SYSTEM_PROMPT = """
You are a Senior Python Engineer specialising in web research automation using the Tavily API.

TASK:
Generate a COMPLETE, EXECUTABLE, PRODUCTION-READY Python script that reproduces a
Tavily web-search workflow.  The script must replicate the exact search intent that
was used in the original chat session, using the tool execution log and web research
provided.  Do NOT use Playwright, browser-use, or any browser automation library.

OUTPUT RULES (ABSOLUTE)
* Return ONLY raw Python code — no markdown, no ``` blocks, no explanations.
* Script must be directly runnable with: python script.py

REQUIRED SCRIPT STRUCTURE
* Imports: os, json, tavily (TavilyClient).
* Read TAVILY_API_KEY from os.getenv("TAVILY_API_KEY").
* A synchronous main() function that:
    1. Builds the search query from the task intent (use the user intent literally
       or refine it based on the tool execution log).
    2. Calls client.search(query=..., search_depth="basic", max_results=5,
       include_answer=True).
    3. Extracts and structures the result into a dict with keys:
       "query", "answer", "results" (list of {title, url, content}).
    4. Prints json.dumps(output, indent=2, ensure_ascii=False) to stdout.
    5. Returns the output dict.
* if __name__ == "__main__": main() at the bottom — no asyncio needed.

ERROR HANDLING
* Wrap the Tavily call in try/except.
* On error print {"error": str(e)} and exit with code 1.

EXAMPLE STRUCTURE (adapt query and fields to the actual task):
    import os, json, sys
    from tavily import TavilyClient

    def main():
        api_key = os.getenv("TAVILY_API_KEY", "")
        if not api_key:
            print(json.dumps({"error": "TAVILY_API_KEY not set"}))
            sys.exit(1)
        client = TavilyClient(api_key=api_key)
        try:
            result = client.search(
                query="<derived from task intent>",
                search_depth="basic",
                max_results=5,
                include_answer=True,
            )
            output = {
                "query": "<same query>",
                "answer": result.get("answer"),
                "results": [
                    {"title": r.get("title"), "url": r.get("url"), "content": r.get("content", "")[:500]}
                    for r in result.get("results", [])
                ],
            }
            print(json.dumps(output, indent=2, ensure_ascii=False))
            return output
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)

    if __name__ == "__main__":
        main()
"""
        else:
            SYSTEM_PROMPT = f"""
You are a Senior Python Automation Engineer specialising in the 'browser-use' library.

TASK:
Convert browser execution traces into a COMPLETE, EXECUTABLE Python script using
'browser-use'.  Use the real-world web research and tool outputs provided to
target exact live URLs and replicate actual observed values.

OUTPUT RULES (ABSOLUTE)
* Return ONLY raw Python code — no markdown, no ``` blocks, no explanations.

REQUIRED SCRIPT STRUCTURE
* All imports: asyncio, os, browser_use.
* Use Agent from browser_use; use Controller only for custom actions.
* A main() async function returning the final result.
* asyncio.run(main()) at the bottom.
{TAVILY_RUNTIME_BLOCK}
BROWSER-USE CONFIGURATION
* Use the standard Agent(task=..., llm=...) pattern.
* Derive the task string from the user intent + execution trace.
"""

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

