# Generate Tavily scripts when search was the tool used

## What & Why
When a user chats with the AI and the response is produced by Tavily web search
(tool name `tavily_search_results_json` or `ai_parser_dynamic_search`), the
Schedule Automation Task dialog currently always generates a Playwright browser
script — even though no browser was used. The generated script fails or is
irrelevant because the original task never needed a browser.

The fix: inspect the tool_context/execution_history at schedule-creation time,
detect whether the execution was search-only or browser-based, and choose the
correct script type automatically.

## Done looks like
- A schedule created from a Tavily-only chat session generates a Python script
  that calls `TavilyClient` directly — no browser launched, no Playwright code
- A schedule from a browser-use/Playwright session continues to generate a
  Playwright script (unchanged behavior)
- A session that used BOTH Tavily (for URL discovery) and browser tools
  generates a Playwright script (browser wins)
- The generated Tavily script is executable: it imports TavilyClient, reads
  TAVILY_API_KEY from env, runs the same query that was used in chat, and prints
  structured JSON output

## Out of scope
- UI changes — no frontend changes needed
- Changing how the agent decides to use Tavily vs browser during chat
- Mixed Tavily+browser scripts (browser takes precedence)

## Steps
1. **Detection helper** — In `create_schedule` (main.py), after building
   `tool_context` and `execution_history`, add a helper that checks whether all
   tool names are Tavily variants (`tavily_search_results_json`,
   `ai_parser_dynamic_search`) with no browser tool names present (`browser_`,
   `navigate`, `click`, `type`, `scroll`). If so, set `framework="tavily"`.

2. **Tavily script system prompt** — In `run_script_generation` (ATAG.py), add a
   new `elif framework == "tavily":` branch with a system prompt tailored to
   generating a self-contained Python script that:
   - Imports `os`, `json`, `TavilyClient`
   - Reads the original search query from the task_summary
   - Calls `client.search(query=..., search_depth="basic", max_results=5)`
   - Prints a structured JSON result
   - Has proper try/except and a `main()` / `asyncio.run(main())` pattern
     (keeping it consistent with Playwright scripts for the runner)
   - Does NOT import or use playwright, browser_use, asyncio (unless needed for
     the runner pattern)

3. **Wire the framework choice** — Pass the detected `framework` value from
   `create_schedule` into `brain.code_processor.run_script_generation(...)`.

## Relevant files
- `Backend/src/main.py:302-344`
- `Backend/src/services/ATAG.py:481-622`
