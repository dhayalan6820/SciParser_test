# Cognitive Memory System + CAPTCHA Skills

## What & Why
The agent currently has no persistent learning across runs. Every task starts from scratch — it re-discovers the same selectors, re-encounters the same bot-detection traps, and fails the same CAPTCHAs repeatedly. This task adds a five-layer cognitive memory system modelled on human memory psychology, so the agent learns from every run and reuses that knowledge automatically.

The six memory layers:
- **Episodic** — "Last time I searched Zillow with this query, these 4 steps worked."
- **Semantic** — "Zillow's address input triggers bot-detection if you type faster than 80ms/key."
- **Procedural** — Stored skill programs: reusable step-by-step procedures for known-complex actions (address entry, login flows, CAPTCHA solving).
- **Self-Reflection** — Lessons distilled from failure: "When reCAPTCHA appears on this domain, do X not Y."
- **Memory Routing** — At the start of every run, query all four stores by domain + task-type and inject relevant memories into the agent's context as "Learned Knowledge."
- **Forgetting & Decay** — Confidence scores decay over time and on failure; boosted on success. Low-confidence memories are archived so the agent doesn't keep trusting stale knowledge.

CAPTCHA handling is implemented as a special class of procedural memories — "skills" — pre-seeded for the most common CAPTCHA types and refined by every run.

## Done looks like
- Agent starts each run with a "Learned Knowledge" block in its system prompt showing domain-relevant memories (selectors, known traps, prior successful procedures).
- On a repeat task for the same domain (e.g., search Zillow twice), the agent's second run visibly reuses the stored procedure from the first — fewer steps, no repeated mistakes.
- When a CAPTCHA is detected mid-run, the agent automatically looks up its procedural skill for that CAPTCHA type and executes it, without stalling.
- Each run's outcome (success/failure, tool steps, lessons) is written back to the memory store and the confidence scores updated.
- Memories that haven't been used or validated in 4+ weeks automatically decay toward archival.
- History panel can show a "Memories Used" section listing which memories were retrieved and applied for the current thread.

## Out of scope
- Visual embedding / vector similarity search (use keyword + domain matching for retrieval — keep it simple and fast).
- Cross-user memory sharing (all memories are per-user).
- Browser fingerprint rotation or proxy management (separate concern).
- Changing the frontend chat UI beyond the History panel "Memories Used" section.

## Steps

### Phase 1 — DB Schema
1. **Create four memory tables in `chat_db.py`:**
   - `MemoryEpisodic` — `id, user_id, domain, task_summary, outcome (SUCCESS/FAIL/PARTIAL), key_steps (JSON array of compact tool-call records), tags (JSON array of keywords), confidence_score (float, default 1.0), access_count, last_accessed, created_at`
   - `MemorySemantic` — `id, user_id, domain, fact_key (e.g. "address_input_selector"), fact_value (text), confidence_score, source_episode_id (FK), access_count, last_validated, created_at`
   - `MemoryProcedural` — `id, user_id, skill_name (e.g. "zillow_address_search", "captcha_recaptcha_v2"), domain (nullable — null means universal), procedure (JSON: ordered step definitions), success_count, failure_count, confidence_score, last_used, last_success, created_at`
   - `MemoryReflection` — `id, user_id, domain, lesson (text), category (enum: BOT_DETECTION, SELECTOR, AUTH, CAPTCHA, NAVIGATION, OTHER), severity (LOW/MEDIUM/HIGH), validated_count, created_at`

### Phase 2 — Memory Service (`memory_service.py`)
2. **Create `Backend/src/services/memory_service.py`** — a standalone service class `MemoryService` with:
   - `retrieve(user_id, domain, task_summary) → MemoryContext` — queries all four tables filtered by `user_id + domain`; returns top 3 episodic matches (by confidence), all semantic facts for the domain, the best matching procedural skill by `skill_name` keyword match, and top 5 reflection lessons. Assembles them into a formatted text block ready for LLM injection.
   - `store_episode(user_id, domain, task_summary, outcome, key_steps, tags)` — writes a new `MemoryEpisodic` row. If outcome is SUCCESS, also calls `_extract_semantic_facts` and `_update_procedural`.
   - `_extract_semantic_facts(episode)` — LLM-assisted extraction: given the episode's key_steps, identify URL patterns, selector values, timing constraints, and write them as `MemorySemantic` rows (upsert by `domain + fact_key`).
   - `_update_procedural(skill_name, domain, steps, success)` — upserts `MemoryProcedural` for the skill; increments `success_count` or `failure_count`; recalculates confidence as `success_count / (success_count + failure_count)`.
   - `store_reflection(user_id, domain, lesson, category, severity)` — writes a `MemoryReflection` row.
   - `apply_decay(user_id)` — runs on schedule or at end of each run: for each memory row, `confidence -= 0.03 * weeks_since_last_accessed`; archive (set `confidence = 0`) if below 0.1.
   - `get_captcha_skill(user_id, captcha_type) → procedure | None` — queries `MemoryProcedural` where `skill_name = "captcha_<type>"`.

3. **Pre-seed CAPTCHA skills** — On first startup (or via a migration script), insert default `MemoryProcedural` rows for:
   - `captcha_recaptcha_v2` — Click checkbox iframe; wait up to 8s for solve; if unsolved, click the audio challenge button, read the audio src, use speech-to-text (or LLM vision on the text challenge), submit.
   - `captcha_recaptcha_v3` — Invisible; detect low-score redirect; reload the page with a delay of 3–5s; retry the action once.
   - `captcha_hcaptcha` — Click the hCaptcha iframe checkbox; wait; if image challenge appears, use LLM vision tool to identify and click the correct tiles; submit.
   - `captcha_cloudflare_turnstile` — Wait 4s for auto-solve; if spinner still visible, click the checkbox; wait another 3s.
   - `captcha_slider` — Use JS drag simulation on the slider element: move right slowly with incremental mousedown/mousemove/mouseup events rather than a single drag.
   - `captcha_image_text` — Screenshot the CAPTCHA image; send to LLM vision for OCR; type the result into the input field.
   Each pre-seed row gets `confidence_score = 0.7` (not fully trusted until validated in a live run), `success_count = 0`, `failure_count = 0`, `domain = null` (universal).

### Phase 3 — Integration into `brain.py`
4. **Memory retrieval at run start** — In `Brain.process_message`, after extracting the domain from the user's task, call `memory_service.retrieve(user_id, domain, task_summary)`. Prepend the returned `MemoryContext` block to `_AGENT_STATIC_PROMPT` as a dynamic section: `"## Learned Knowledge (from prior runs)\n{memory_context}"`. If no memories exist yet, omit the section entirely.

5. **CAPTCHA detection in `_sanitize_browser_observation`** — Extend the existing blocker detection regex to also identify CAPTCHA signals: presence of `"recaptcha"`, `"hcaptcha"`, `"cf-turnstile"`, `"slider"` in the page content or frame URL. When detected, return a structured tag `[CAPTCHA_DETECTED: <type>]` in the observation string.

6. **CAPTCHA skill execution in `_call_tool`** — After a tool returns `[CAPTCHA_DETECTED: <type>]`, immediately call `memory_service.get_captcha_skill(user_id, captcha_type)`. If a skill exists, inject its procedure steps as the next LLM instruction via a synthetic `HumanMessage`. If the skill succeeds (next tool call passes the CAPTCHA), call `_update_procedural(skill_name, success=True)`. If it fails, call `store_reflection` with the failure lesson and `_update_procedural(success=False)`.

7. **Memory write-back at run end** — At the end of `process_message` (in the `finally` block), call `memory_service.store_episode(...)` with: the final status, a compact list of the successful tool calls (name + key input fields only, no raw output blobs), and auto-extracted tags (domain keywords). Then call `memory_service.apply_decay(user_id)`.

### Phase 4 — API Exposure (optional, for History panel)
8. **Add `/memory/` endpoints in `main.py`** — Read-only endpoints:
   - `GET /memory/episodes?domain=` — list recent episodic memories for the user.
   - `GET /memory/skills` — list procedural skills with confidence scores.
   These allow the frontend History panel to show a "Memories Used" section.

## Relevant files
- `Backend/src/services/brain.py`
- `Backend/src/services/ATAG.py`
- `Backend/src/db/chat_db.py`
- `Backend/src/models/chat_models.py`
- `Backend/src/main.py`
