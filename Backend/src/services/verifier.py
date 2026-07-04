"""
Per-action Verifier step.

After every tool call, checks whether the tool's expected effect actually
occurred — using the tool name/args and the Observer's structured
`ObservedState` — and produces a `ValidationResult` that is surfaced to the
planning/critic loop. This closes the gap where a silently-failed action
(a click that did nothing, a form field that didn't take the typed value, a
navigation that landed on an error page) would otherwise be indistinguishable
from real progress until several turns later.

Deliberately conservative: it only returns `passed=False` when there is
positive evidence the action did not take effect (an explicit tool error, a
blocker appearing where the action should have made progress, or a
recognizable error signal). It never blocks on merely ambiguous/neutral
observations — browser automation text is inherently noisy, and a verifier
with a high false-positive rate would just add another source of stalls.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from src.services.observer import ObservedState

# Tool-name families the verifier reasons about explicitly. Matched by
# substring against the live MCP tool name so this stays correct even if the
# MCP server renames/versions its tools slightly (e.g. `browser_click` vs
# `browser_click_element`), without hardcoding an exhaustive exact-name list.
_CLICK_HINTS = ("click",)
_TYPE_HINTS = ("type", "input_text", "fill", "send_keys")
_NAV_HINTS = ("navigate", "go_to_url", "open_url", "goto")


@dataclass
class ValidationResult:
    tool_name: str
    passed: bool
    reason: str
    severity: str = "INFO"  # INFO | WARNING | BLOCKING

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "passed": self.passed,
            "reason": self.reason,
            "severity": self.severity,
        }

    def to_prompt_note(self) -> str:
        """Short note appended to the tool observation so the next planning
        turn sees the verification outcome without a separate lookup."""
        if self.passed:
            return ""
        return f"\n\n[VERIFICATION {self.severity}: {self.reason}]"


def _matches_any(name: str, hints: tuple) -> bool:
    n = (name or "").lower()
    return any(h in n for h in hints)


def verify_action(
    tool_name: str,
    tool_args: Dict[str, Any],
    status: str,
    observed: ObservedState,
) -> ValidationResult:
    """Verify the expected effect of the last tool call occurred.

    `status` is the SUCCESS/FAILED classification `_call_tool` already
    computes from the raw observation text; `observed` is the structured
    state produced by `src.services.observer.observe` for the SAME
    observation, so this never re-parses raw text itself.
    """
    if status == "FAILED":
        return ValidationResult(tool_name, False, "Tool execution reported an error.", severity="BLOCKING")

    if observed.captcha_type:
        return ValidationResult(
            tool_name, False,
            f"A {observed.captcha_type} CAPTCHA appeared after this action.",
            severity="BLOCKING",
        )

    if observed.otp_type:
        return ValidationResult(
            tool_name, False,
            "A verification-code prompt appeared after this action.",
            severity="BLOCKING",
        )

    if observed.has_error:
        return ValidationResult(
            tool_name, False,
            f"Post-action observation shows error signal(s): {', '.join(observed.error_signals)}.",
            severity="WARNING",
        )

    if _matches_any(tool_name, _NAV_HINTS):
        target = str(tool_args.get("url") or tool_args.get("go_to_url") or "").strip()
        if target and observed.url:
            target_host = target.split("://")[-1].split("/")[0].lower()
            if target_host and target_host not in observed.url.lower():
                return ValidationResult(
                    tool_name, True,
                    "Navigated, but the resulting URL differs from the requested target "
                    "(may be a legitimate redirect — treat as informational, not a failure).",
                    severity="WARNING",
                )

    if _matches_any(tool_name, _CLICK_HINTS + _TYPE_HINTS) and observed.is_loading:
        return ValidationResult(
            tool_name, True,
            "Action accepted; page still loading — confirm the intended effect on the next observation.",
            severity="INFO",
        )

    return ValidationResult(tool_name, True, "No blocking signal detected after this action.", severity="INFO")
