# Agent Guidelines: Handling Large Data and Loop Prevention

## 1. Short-Term vs Long-Term Memory
- **Short-Term Memory (LLM Context)**: Keep it lightweight. Never let raw DOM structures, massive page extracts, base64 strings, or logs accumulate in the history.
- **Long-Term Memory (Database/Filesystem)**: Always save complete raw outputs, CSVs, and screenshots to the database (`ToolExecutionLog`) or the local filesystem.

## 2. Linear Step-by-Step Execution
- Always create a checklist of tasks at the beginning of a run.
- Update the checklist after each step, marking finished tasks with `[x]` and current task with `[current]`.
- Focus on one URL or document at a time. Finish extracting and compiling its metadata summary before moving to the next.

## 3. Metadata and Summarization
- When a tool returns a large volume of data, RAG-compress or summarize it down to key facts (e.g. package names, prices, speeds, early termination fees).
- Return a structured metadata JSON to the reasoning loop containing:
  ```json
  {
    "status": "SUCCESS_SAVED_TO_DATABASE",
    "url": "https://...",
    "db_log_id": 123,
    "summary": "Summarized facts..."
  }
  ```
- Use the `db_log_id` references to track where full payloads reside.

## 4. Loop Detection
- Do not repeat the same tool calls with the same arguments. If a click or type fails twice, find an alternative path or log it as a failure.
