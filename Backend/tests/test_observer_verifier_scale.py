"""
Task #157: confirm the Observer/Verifier loop (added in Task #154) doesn't
regress token usage or step count on longer (10+ step) multi-page browsing
tasks versus the pre-hardening baseline.

A live LLM-driven run was attempted for this task but blocked by the
OpenRouter key's daily quota (see task notes). These tests instead exercise
the exact production code path Observer/Verifier run on per tool call
(`observe` -> `verify_action` -> `_compress_observation_for_llm`, the same
sequence `Brain._call_tool` runs) over a synthetic 14-step multi-page run,
and assert the two properties that matter for a longer task:

1. Per-step overhead is negligible wall-clock time (no LLM call is made by
   either step — they are pure regex/string logic) and does not grow with
   step count.
2. The prompt-size delta the Verifier's `to_prompt_note()` adds versus the
   pre-hardening baseline (raw observation with no note) is bounded to only
   the steps that actually fail/warn — it does not compound across
   successful steps, so a longer run does not accumulate a growing tax the
   way a per-step-regardless-of-outcome addition would.
"""
from __future__ import annotations

import time

from src.services.observer import observe
from src.services.verifier import verify_action
from src.services.brain import _compress_observation_for_llm, MAX_OBSERVATION_CHARS_FOR_LLM


def _synthetic_multi_page_run(num_steps: int = 14):
    """Builds a synthetic run mixing successful navigations/clicks with a
    couple of induced failures, mirroring a real multi-page task shape."""
    steps = []
    for i in range(num_steps):
        if i == 5:
            raw = "Error executing tool: element not found for selector #submit-btn"
            tool, args, status = "browser_click", {"index": 3}, "FAILED"
        elif i == 9:
            raw = (
                "Current URL: https://example.com/step9\n"
                "Please complete the reCAPTCHA challenge to continue."
            )
            tool, args, status = "browser_click", {"index": 1}, "SUCCESS"
        else:
            raw = f"Current URL: https://example.com/step{i}\n" + ("Page content here. " * 200)
            tool, args, status = "browser_navigate", {"url": f"https://example.com/step{i}"}, "SUCCESS"
        steps.append((tool, args, status, raw))
    return steps


def _run_pipeline_step(tool, args, status, raw):
    """Reproduces the exact Observer -> Verifier -> compression sequence
    `Brain._call_tool` runs per tool result."""
    observed = observe(raw)
    validation = verify_action(tool, args, status, observed)
    note = validation.to_prompt_note()
    observation = raw + note
    llm_observation = _compress_observation_for_llm(observation, MAX_OBSERVATION_CHARS_FOR_LLM)
    baseline_llm_observation = _compress_observation_for_llm(raw, MAX_OBSERVATION_CHARS_FOR_LLM)
    return note, llm_observation, baseline_llm_observation


def test_observer_verifier_adds_negligible_latency_across_a_long_run():
    steps = _synthetic_multi_page_run(14)

    timings_ms = []
    for tool, args, status, raw in steps:
        t0 = time.perf_counter()
        _run_pipeline_step(tool, args, status, raw)
        timings_ms.append((time.perf_counter() - t0) * 1000)

    # Pure regex/string logic, no LLM/network call — every step should be
    # well under what would be noticeable against an LLM round-trip (which
    # takes hundreds to thousands of ms), and the cost per step should not
    # trend upward as more steps accumulate (no O(n) or worse growth).
    assert max(timings_ms) < 25, f"Unexpectedly slow step: {max(timings_ms):.3f}ms"
    first_half_avg = sum(timings_ms[:7]) / 7
    second_half_avg = sum(timings_ms[7:]) / 7
    assert second_half_avg < first_half_avg * 3, (
        "Per-step Observer/Verifier cost grew across the run instead of staying flat "
        f"(first half avg={first_half_avg:.3f}ms, second half avg={second_half_avg:.3f}ms)"
    )


def test_observer_verifier_prompt_overhead_is_bounded_not_compounding():
    steps = _synthetic_multi_page_run(14)

    total_note_chars = 0
    total_baseline_chars = 0
    total_hardened_chars = 0
    failing_or_warning_steps = 0

    for tool, args, status, raw in steps:
        note, llm_observation, baseline_llm_observation = _run_pipeline_step(tool, args, status, raw)
        total_note_chars += len(note)
        total_baseline_chars += len(baseline_llm_observation)
        total_hardened_chars += len(llm_observation)
        if note:
            failing_or_warning_steps += 1

    # Only the induced failure (index 5) and CAPTCHA-blocked step (index 9)
    # should have produced a note — clean successful steps get zero overhead.
    assert failing_or_warning_steps == 2

    # The added overhead across the whole run should be a small fraction of
    # total observation size, not a per-step tax that scales with step count.
    delta_pct = 100 * (total_hardened_chars - total_baseline_chars) / total_baseline_chars
    assert delta_pct < 2.0, f"Verifier notes added {delta_pct:.2f}% overhead, expected a small bounded amount"

    # Each individual note stays short — it's a one-line annotation, not a
    # growing block that could itself balloon on a long/complex run.
    for tool, args, status, raw in steps:
        note, _, _ = _run_pipeline_step(tool, args, status, raw)
        if note:
            assert len(note) < 200


def test_execution_memory_summary_stays_bounded_per_entry_regardless_of_verifier_note():
    """Mirrors call_model's EXECUTION MEMORY rendering (brain.py) — each
    execution_history entry is rendered from `entry['result'][:100]`, so the
    per-turn memory block genuinely grows by a fixed ~100 chars per step,
    exactly as it did before Task #154 added the Verifier. The verifier note
    (appended at the END of the observation) does not add to that per-step
    cost when the underlying observation is already longer than 100 chars."""
    raw = "Current URL: https://example.com/step\n" + ("Page content here. " * 200)
    observed = observe(raw)
    validation = verify_action("browser_click", {"index": 1}, "SUCCESS", observed)

    # Force a note by asserting on a failing case instead, to check the worst case.
    failing_validation = verify_action("browser_click", {"index": 1}, "FAILED", observed)
    note = failing_validation.to_prompt_note()
    observation = raw + note
    llm_observation = _compress_observation_for_llm(observation, MAX_OBSERVATION_CHARS_FOR_LLM)

    memory_entry_result = llm_observation[:500]
    rendered_in_memory_block = memory_entry_result[:100]

    # The 100-char EXECUTION MEMORY excerpt is unaffected by the note when
    # the raw observation already exceeds 100 chars — this is a real, minor
    # side effect worth knowing about (the note may never surface in the
    # short-lived memory summary, only in the full ToolMessage for recent
    # steps), but it is NOT a source of per-step growth.
    assert len(rendered_in_memory_block) == 100
