import json
import uuid
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import delete, select, and_, or_

from src.database.chat_db import (
    AsyncSessionLocal,
    MemoryEpisodic,
    MemorySemantic,
    MemoryProcedural,
    MemoryReflection,
)
from src.utils.logger import logger
from langchain_core.messages import HumanMessage


class MemoryContext:
    def __init__(self):
        self.episodes: List[Dict] = []
        self.semantic_facts: List[Dict] = []
        self.procedural_skills: List[Dict] = []
        self.reflections: List[Dict] = []

    def is_empty(self) -> bool:
        return not any([self.episodes, self.semantic_facts, self.procedural_skills, self.reflections])

    def to_prompt_block(self) -> str:
        if self.is_empty():
            return ""

        lines = ["## Learned Knowledge (from prior runs on this domain)"]

        if self.semantic_facts:
            lines.append("\n### Known Facts:")
            for f in self.semantic_facts:
                conf = f.get("confidence_score", 1.0)
                lines.append(f"  - {f['fact_key']}: {f['fact_value']} (confidence {conf:.2f})")

        if self.procedural_skills:
            lines.append("\n### Available Skills:")
            for s in self.procedural_skills:
                conf = s.get("confidence_score", 0.7)
                lines.append(f"  - **{s['skill_name']}** (confidence {conf:.2f}): {s['procedure_summary']}")

        if self.episodes:
            lines.append("\n### Prior Experiences:")
            for ep in self.episodes:
                lines.append(f"  - [{ep['outcome']}] {ep['task_summary'][:120]}")

        if self.reflections:
            lines.append("\n### Lessons Learned (do not repeat these mistakes):")
            for r in self.reflections:
                lines.append(f"  - [{r['severity']}][{r['category']}] {r['lesson']}")

        return "\n".join(lines)


_DECAY_LAST_RUN: Dict[str, datetime] = {}
_DECAY_INTERVAL = timedelta(hours=6)
_DECAY_STALE_DAYS = 7
_DECAY_DELETE_THRESHOLD = 0.05

_CAPTCHA_REFLECTION_MAX_DAYS = 30
_CAPTCHA_SKILL_CONFIDENCE_FLOOR = 0.15

# Argument/fact keys that typically carry task-specific *input data* (search
# terms, personal info, credentials, free-form answers) rather than durable
# facts about how a site works. Used both to skip rule-based extraction of
# risky args and as a safety-net filter on LLM-proposed facts. Task #162:
# semantic ("Known Facts") memory must only retain reusable site mechanics
# (selectors, stable URLs, timing/bot-detection notes) — never the specific
# values a task happened to use.
_TASK_SPECIFIC_KEY_MARKERS = (
    "text", "value", "query", "search", "keys", "answer", "input",
    "address", "email", "phone", "name", "amount", "message", "content",
    "otp", "code", "password", "username", "secret", "token", "ssn",
    "card", "cvv", "dob", "birth", "zip", "postal",
)


def _looks_task_specific(key: str) -> bool:
    """Heuristic: does a fact/arg key look like it holds task input data
    (rather than a durable, reusable site fact) based on common naming
    patterns for form values, credentials, and personal data."""
    k = (key or "").lower()
    return any(marker in k for marker in _TASK_SPECIFIC_KEY_MARKERS)


_EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
_PHONE_RE = re.compile(r'(?:\+?\d[\s\-.]?){7,}')
_QUERY_STRING_RE = re.compile(r'\?[\w%.+-]+=')


def _collect_task_input_values(key_steps: List[Dict]) -> List[str]:
    """Gather the literal string argument values used across a run's steps
    (e.g. a typed search term, a name, an address) so LLM-proposed facts can
    be checked for containing them verbatim — a value-level backstop that
    doesn't rely on the fact's *key* being labeled honestly."""
    values: List[str] = []
    for step in key_steps or []:
        args = step.get("args") or {}
        if not isinstance(args, dict):
            continue
        for v in args.values():
            if isinstance(v, str) and len(v.strip()) >= 4:
                values.append(v.strip().lower())
    return values


def _looks_task_specific_value(value: str, task_input_values: Optional[List[str]] = None) -> bool:
    """Heuristic: does a proposed fact *value* look like task-input data
    (an email, phone number, leaked query string, or a literal value the
    task actually typed/searched for) rather than a durable site mechanic.
    This is deliberately checked independently of the fact's key, since a
    task-specific value can be smuggled in under an innocuous-looking key.
    """
    v = (value or "").strip()
    if not v:
        return False
    if _EMAIL_RE.search(v) or _PHONE_RE.search(v) or _QUERY_STRING_RE.search(v):
        return True
    v_lower = v.lower()
    for input_value in (task_input_values or []):
        if input_value and (input_value in v_lower or v_lower in input_value):
            return True
    return False


def _strip_query_and_fragment(url: str) -> str:
    """Drop query string / fragment from a URL before storing it as a
    durable fact — query params frequently encode task-specific values
    (e.g. a search term or record id) that don't generalize across tasks."""
    try:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except Exception:
        return url


class MemoryService:
    def __init__(self, llm=None):
        self.llm = llm

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def extract_domain(text: str) -> str:
        url_match = re.search(r'https?://(?:www\.)?([^/\s?#]+)', text)
        if url_match:
            return url_match.group(1).lower()
        domain_match = re.search(
            r'\b([a-zA-Z0-9-]+\.(?:com|org|net|io|gov|edu|co\.uk|de|fr|info|ai|app))\b',
            text, re.IGNORECASE
        )
        if domain_match:
            return domain_match.group(1).lower()
        return "general"

    @staticmethod
    def _extract_tags(text: str) -> List[str]:
        stop = {'the','a','an','is','are','was','were','to','for','on','in','at','of',
                'and','or','but','with','this','that','from','by','go','get','use','i','me'}
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        return list({w for w in words if w not in stop})[:12]

    # ── core retrieval ────────────────────────────────────────────────────────

    async def retrieve(self, user_id: str, domain: str, task_summary: str) -> MemoryContext:
        ctx = MemoryContext()
        try:
            async with AsyncSessionLocal() as db:
                # Episodic: top 3 by confidence for this user+domain
                ep_res = await db.execute(
                    select(MemoryEpisodic)
                    .where(and_(
                        MemoryEpisodic.user_id == user_id,
                        MemoryEpisodic.domain == domain,
                        MemoryEpisodic.confidence_score > 0.1,
                    ))
                    .order_by(MemoryEpisodic.confidence_score.desc())
                    .limit(3)
                )
                for ep in ep_res.scalars().all():
                    ctx.episodes.append({
                        "outcome": ep.outcome,
                        "task_summary": ep.task_summary,
                        "confidence_score": ep.confidence_score,
                    })
                    ep.access_count = (ep.access_count or 0) + 1
                    ep.last_accessed = datetime.now(timezone.utc)

                # Semantic: all facts for user+domain with confidence > 0.2
                sem_res = await db.execute(
                    select(MemorySemantic)
                    .where(and_(
                        MemorySemantic.user_id == user_id,
                        MemorySemantic.domain == domain,
                        MemorySemantic.confidence_score > 0.2,
                    ))
                    .order_by(MemorySemantic.confidence_score.desc())
                    .limit(10)
                )
                for fact in sem_res.scalars().all():
                    ctx.semantic_facts.append({
                        "fact_key": fact.fact_key,
                        "fact_value": fact.fact_value[:200],
                        "confidence_score": fact.confidence_score,
                    })
                    fact.access_count = (fact.access_count or 0) + 1

                # Procedural: domain-specific + universal skills
                proc_res = await db.execute(
                    select(MemoryProcedural)
                    .where(and_(
                        or_(MemoryProcedural.user_id == user_id, MemoryProcedural.user_id.is_(None)),
                        or_(MemoryProcedural.domain == domain, MemoryProcedural.domain.is_(None)),
                        MemoryProcedural.confidence_score > 0.1,
                    ))
                    .order_by(MemoryProcedural.confidence_score.desc())
                    .limit(5)
                )
                for skill in proc_res.scalars().all():
                    proc = json.loads(skill.procedure) if skill.procedure else {}
                    ctx.procedural_skills.append({
                        "skill_name": skill.skill_name,
                        "confidence_score": skill.confidence_score,
                        "procedure_summary": proc.get("summary", "")[:200],
                    })

                # Reflections: top 5 most validated lessons for this user+domain
                # Exclude CAPTCHA reflections older than _CAPTCHA_REFLECTION_MAX_DAYS so that
                # stale failure lessons from superseded CAPTCHA implementations don't continue
                # to pollute the context with misleading guidance.
                _captcha_cutoff = datetime.now(timezone.utc) - timedelta(days=_CAPTCHA_REFLECTION_MAX_DAYS)
                ref_res = await db.execute(
                    select(MemoryReflection)
                    .where(and_(
                        MemoryReflection.user_id == user_id,
                        MemoryReflection.domain == domain,
                        or_(
                            MemoryReflection.category != "CAPTCHA",
                            MemoryReflection.created_at >= _captcha_cutoff,
                        ),
                    ))
                    .order_by(MemoryReflection.validated_count.desc())
                    .limit(5)
                )
                for ref in ref_res.scalars().all():
                    ctx.reflections.append({
                        "lesson": ref.lesson,
                        "category": ref.category,
                        "severity": ref.severity,
                    })

                await db.commit()
        except Exception as e:
            logger.error(f"[Memory] retrieve error: {e}")
        return ctx

    # ── storage ───────────────────────────────────────────────────────────────

    async def store_episode(
        self,
        user_id: str,
        domain: str,
        task_summary: str,
        outcome: str,
        key_steps: List[Dict],
        tags: Optional[List[str]] = None,
    ) -> str:
        episode_id = str(uuid.uuid4())
        try:
            async with AsyncSessionLocal() as db:
                db.add(MemoryEpisodic(
                    id=episode_id,
                    user_id=user_id,
                    domain=domain,
                    task_summary=task_summary[:500],
                    outcome=outcome,
                    key_steps=json.dumps(key_steps[:20]),
                    tags=json.dumps(tags or self._extract_tags(task_summary)),
                    confidence_score=1.0 if outcome == "SUCCESS" else 0.5,
                    access_count=0,
                    created_at=datetime.now(timezone.utc),
                ))
                await db.commit()

            # Side effects on success
            if outcome == "SUCCESS" and key_steps:
                await self._extract_semantic_facts(user_id, domain, key_steps, episode_id)
                skill_name = f"task_{domain.replace('.', '_').replace('-', '_')}"
                await self._update_procedural(user_id, skill_name, domain, key_steps, success=True)

        except Exception as e:
            logger.error(f"[Memory] store_episode error: {e}")
        return episode_id

    async def _extract_semantic_facts(
        self, user_id: str, domain: str, key_steps: List[Dict], episode_id: str
    ):
        facts: List[tuple] = []

        # Rule-based extraction — no LLM needed. Deliberately narrow: only
        # structural/navigational args (url, selector) are ever read here —
        # never form values, search terms, or other task-input fields — so
        # this loop can't leak task-specific data even if callers pass richer
        # args in the future. URLs are stripped of query/fragment since those
        # frequently encode the task's specific input (e.g. a search term).
        for step in key_steps:
            args = step.get("args", {})
            tool = step.get("tool", "")
            if url := (args.get("url") or args.get("go_to_url")):
                facts.append(("known_url", _strip_query_and_fragment(str(url))[:255]))
            if sel := (args.get("selector") or args.get("css_selector")):
                label = args.get("label") or f"selector_{tool}"
                if not _looks_task_specific(label):
                    facts.append((label[:100], str(sel)[:255]))

        # LLM-assisted extraction when available
        if self.llm and key_steps:
            _task_input_values = _collect_task_input_values(key_steps)
            try:
                steps_text = json.dumps(key_steps[:10], indent=2)
                prompt = (
                    f"Extract durable, REUSABLE factual knowledge about the domain '{domain}' "
                    f"from these successful automation steps — facts that would still be true "
                    f"and useful on a completely DIFFERENT task on this same site.\n"
                    f"Return ONLY JSON: {{\"facts\": [{{\"key\": \"...\", \"value\": \"...\"}}]}}\n"
                    f"Focus on: stable selectors, stable page URLs (no query params), "
                    f"timing/rate-limit constraints, and bot-detection behavior.\n"
                    f"Do NOT include anything specific to this one task's request: no search "
                    f"terms, names, addresses, emails, phone numbers, dates, amounts, order/ "
                    f"item details, credentials, codes, or any other input value the user "
                    f"supplied. If a step's only notable content is a value like that, skip it.\n"
                    f"Keep values under 150 chars.\n\nSteps:\n{steps_text[:2000]}"
                )
                resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
                m = re.search(r'\{.*\}', resp.content, re.DOTALL)
                if m:
                    data = json.loads(m.group())
                    for f in data.get("facts", []):
                        fact_key, fact_value = f.get("key"), f.get("value")
                        if not (fact_key and fact_value):
                            continue
                        # Safety net beyond the prompt: reject anything whose key
                        # OR value looks like task-input data rather than a
                        # durable site fact. The value check matters even when
                        # the key looks innocuous, since a task-specific value
                        # (email, phone, leaked query string, or a literal
                        # value the run actually typed/searched for) can be
                        # smuggled in under a generic-sounding key.
                        if _looks_task_specific(str(fact_key)):
                            continue
                        if _looks_task_specific_value(str(fact_value), _task_input_values):
                            continue
                        facts.append((str(fact_key)[:100], str(fact_value)[:255]))
            except Exception as e:
                logger.debug(f"[Memory] LLM fact extraction skipped: {e}")

        if not facts:
            return

        try:
            async with AsyncSessionLocal() as db:
                for fact_key, fact_value in facts:
                    existing = await db.execute(
                        select(MemorySemantic).where(and_(
                            MemorySemantic.user_id == user_id,
                            MemorySemantic.domain == domain,
                            MemorySemantic.fact_key == fact_key,
                        ))
                    )
                    row = existing.scalar_one_or_none()
                    if row:
                        row.fact_value = fact_value
                        row.confidence_score = min(1.0, (row.confidence_score or 0.5) + 0.1)
                        row.last_validated = datetime.now(timezone.utc)
                    else:
                        db.add(MemorySemantic(
                            user_id=user_id,
                            domain=domain,
                            fact_key=fact_key,
                            fact_value=fact_value,
                            confidence_score=0.8,
                            source_episode_id=episode_id,
                            access_count=0,
                            created_at=datetime.now(timezone.utc),
                        ))
                await db.commit()
        except Exception as e:
            logger.error(f"[Memory] _extract_semantic_facts store error: {e}")

    async def _update_procedural(
        self,
        user_id: str,
        skill_name: str,
        domain: Optional[str],
        steps: List[Dict],
        success: bool,
    ):
        try:
            async with AsyncSessionLocal() as db:
                res = await db.execute(
                    select(MemoryProcedural).where(and_(
                        MemoryProcedural.user_id == user_id,
                        MemoryProcedural.skill_name == skill_name,
                    ))
                )
                skill = res.scalar_one_or_none()
                now = datetime.now(timezone.utc)
                procedure_data = {"summary": f"Procedure for {skill_name}", "steps": steps[:15]}

                if skill:
                    if success:
                        skill.success_count = (skill.success_count or 0) + 1
                        skill.last_success = now
                        skill.procedure = json.dumps(procedure_data)
                    else:
                        skill.failure_count = (skill.failure_count or 0) + 1
                    total = (skill.success_count or 0) + (skill.failure_count or 0)
                    raw_confidence = (skill.success_count or 0) / total if total else 0.5
                    # CAPTCHA skills retain a minimum useful confidence so that stale failures
                    # from a superseded CAPTCHA implementation can never permanently discard the
                    # skill — a success streak can always recover from the floor.
                    if skill_name.startswith("captcha_"):
                        raw_confidence = max(raw_confidence, _CAPTCHA_SKILL_CONFIDENCE_FLOOR)
                    skill.confidence_score = raw_confidence
                    skill.last_used = now
                else:
                    db.add(MemoryProcedural(
                        user_id=user_id,
                        skill_name=skill_name,
                        domain=domain,
                        procedure=json.dumps(procedure_data),
                        success_count=1 if success else 0,
                        failure_count=0 if success else 1,
                        confidence_score=0.8 if success else 0.2,
                        last_used=now,
                        last_success=now if success else None,
                        created_at=now,
                    ))
                await db.commit()
        except Exception as e:
            logger.error(f"[Memory] _update_procedural error: {e}")

    async def store_reflection(
        self,
        user_id: str,
        domain: str,
        lesson: str,
        category: str = "OTHER",
        severity: str = "MEDIUM",
    ):
        try:
            async with AsyncSessionLocal() as db:
                db.add(MemoryReflection(
                    user_id=user_id,
                    domain=domain,
                    lesson=lesson[:500],
                    category=category,
                    severity=severity,
                    validated_count=0,
                    created_at=datetime.now(timezone.utc),
                ))
                await db.commit()
        except Exception as e:
            logger.error(f"[Memory] store_reflection error: {e}")

    # ── decay ────────────────────────────────────────────────────────────────

    async def apply_decay(self, user_id: str):
        """Reduce confidence of stale memories and hard-delete near-zero rows.

        Rate-limited to at most once per 6 hours per user.  Only rows whose
        last-access / last-validated timestamp is older than _DECAY_STALE_DAYS
        are touched, so freshly-used rows are never loaded unnecessarily.
        Rows that fall below _DECAY_DELETE_THRESHOLD are deleted outright.
        """
        now = datetime.now(timezone.utc)

        last_run = _DECAY_LAST_RUN.get(user_id)
        if last_run and (now - last_run) < _DECAY_INTERVAL:
            logger.debug(f"[Memory] apply_decay skipped for {user_id} (ran {now - last_run} ago)")
            return

        _DECAY_LAST_RUN[user_id] = now
        stale_cutoff = now - timedelta(days=_DECAY_STALE_DAYS)

        try:
            async with AsyncSessionLocal() as db:
                ep_rows = (await db.execute(
                    select(MemoryEpisodic).where(and_(
                        MemoryEpisodic.user_id == user_id,
                        or_(
                            MemoryEpisodic.last_accessed < stale_cutoff,
                            and_(
                                MemoryEpisodic.last_accessed.is_(None),
                                MemoryEpisodic.created_at < stale_cutoff,
                            ),
                        ),
                    ))
                )).scalars().all()

                for row in ep_rows:
                    ref = row.last_accessed or row.created_at
                    if ref:
                        ref = ref.replace(tzinfo=timezone.utc) if ref.tzinfo is None else ref
                        weeks = max(0, (now - ref).days / 7)
                        row.confidence_score = max(0.0, (row.confidence_score or 1.0) - 0.03 * weeks)

                await db.execute(
                    delete(MemoryEpisodic).where(and_(
                        MemoryEpisodic.user_id == user_id,
                        MemoryEpisodic.confidence_score < _DECAY_DELETE_THRESHOLD,
                    ))
                )

                sem_rows = (await db.execute(
                    select(MemorySemantic).where(and_(
                        MemorySemantic.user_id == user_id,
                        or_(
                            MemorySemantic.last_validated < stale_cutoff,
                            and_(
                                MemorySemantic.last_validated.is_(None),
                                MemorySemantic.created_at < stale_cutoff,
                            ),
                        ),
                    ))
                )).scalars().all()

                for row in sem_rows:
                    ref = row.last_validated or row.created_at
                    if ref:
                        ref = ref.replace(tzinfo=timezone.utc) if ref.tzinfo is None else ref
                        weeks = max(0, (now - ref).days / 7)
                        row.confidence_score = max(0.0, (row.confidence_score or 1.0) - 0.03 * weeks)

                await db.execute(
                    delete(MemorySemantic).where(and_(
                        MemorySemantic.user_id == user_id,
                        MemorySemantic.confidence_score < _DECAY_DELETE_THRESHOLD,
                    ))
                )

                # Hard-delete CAPTCHA reflection lessons older than the max lifetime.
                # This prevents stale failures (e.g. from a since-replaced reCAPTCHA v2
                # implementation) from permanently accumulating and dragging down skill
                # confidence scores through the store_reflection→confidence feedback loop.
                captcha_expiry = now - timedelta(days=_CAPTCHA_REFLECTION_MAX_DAYS)
                del_result = await db.execute(
                    delete(MemoryReflection).where(and_(
                        MemoryReflection.user_id == user_id,
                        MemoryReflection.category == "CAPTCHA",
                        MemoryReflection.created_at < captcha_expiry,
                    ))
                )
                deleted_captcha = del_result.rowcount

                await db.commit()
                logger.debug(
                    f"[Memory] apply_decay done for {user_id}: "
                    f"processed {len(ep_rows)} episodic, {len(sem_rows)} semantic stale rows, "
                    f"deleted {deleted_captcha} expired CAPTCHA reflection(s)"
                )
        except Exception as e:
            logger.error(f"[Memory] apply_decay error: {e}")

    # ── CAPTCHA skills ────────────────────────────────────────────────────────

    async def get_captcha_skill(self, user_id: str, captcha_type: str) -> Optional[Dict]:
        skill_name = f"captcha_{captcha_type}"
        try:
            async with AsyncSessionLocal() as db:
                res = await db.execute(
                    select(MemoryProcedural).where(and_(
                        MemoryProcedural.skill_name == skill_name,
                        MemoryProcedural.confidence_score > 0.1,
                        or_(MemoryProcedural.user_id == user_id, MemoryProcedural.user_id.is_(None)),
                    ))
                    .order_by(MemoryProcedural.confidence_score.desc())
                    .limit(1)
                )
                skill = res.scalar_one_or_none()
                if skill:
                    skill.last_used = datetime.now(timezone.utc)
                    await db.commit()
                    return json.loads(skill.procedure) if skill.procedure else None
        except Exception as e:
            logger.error(f"[Memory] get_captcha_skill error: {e}")
        return None

    async def seed_captcha_skills(self):
        """Insert default CAPTCHA procedural skills on first startup (idempotent)."""
        skills = [
            {
                "skill_name": "captcha_recaptcha_v2",
                "procedure": {
                    "summary": "Solve reCAPTCHA v2 checkbox — click, wait, try audio if needed",
                    "steps": [
                        {"action": "find_iframe", "selector": "iframe[src*='recaptcha']"},
                        {"action": "switch_to_iframe"},
                        {"action": "click", "selector": ".recaptcha-checkbox", "description": "Click 'I am not a robot'"},
                        {"action": "wait", "ms": 3000},
                        {"action": "check_solved", "selector": ".recaptcha-checkbox-checked"},
                        {"action": "if_unsolved", "description": "Click audio challenge button"},
                        {"action": "get_audio_url", "description": "Fetch audio challenge href"},
                        {"action": "vision_or_ocr", "description": "If text challenge, screenshot + LLM vision to read"},
                        {"action": "type_solution", "selector": "#audio-response"},
                        {"action": "click_verify", "selector": "#recaptcha-verify-button"},
                        {"action": "switch_back"},
                    ],
                },
            },
            {
                "skill_name": "captcha_recaptcha_v3",
                "procedure": {
                    "summary": "reCAPTCHA v3 is invisible — reload + human simulation to improve score",
                    "steps": [
                        {"action": "detect_low_score_redirect"},
                        {"action": "wait", "ms": 3000},
                        {"action": "scroll_slowly", "description": "Scroll down and up to simulate human"},
                        {"action": "wait", "ms": 2000},
                        {"action": "reload_page"},
                        {"action": "retry_original_action"},
                    ],
                },
            },
            {
                "skill_name": "captcha_hcaptcha",
                "procedure": {
                    "summary": "Solve hCaptcha — click checkbox, handle image tile challenge via vision",
                    "steps": [
                        {"action": "find_iframe", "selector": "iframe[src*='hcaptcha']"},
                        {"action": "switch_to_iframe"},
                        {"action": "click", "selector": "#checkbox"},
                        {"action": "wait", "ms": 2000},
                        {"action": "check_auto_solved"},
                        {"action": "screenshot_challenge", "description": "Screenshot image challenge"},
                        {"action": "vision_identify_tiles", "description": "LLM vision: identify correct tiles"},
                        {"action": "click_correct_tiles"},
                        {"action": "click_verify"},
                        {"action": "switch_back"},
                    ],
                },
            },
            {
                "skill_name": "captcha_cloudflare_turnstile",
                "procedure": {
                    "summary": "Cloudflare Turnstile — wait for auto-solve, click checkbox if still pending",
                    "steps": [
                        {"action": "wait", "ms": 4000, "description": "Wait for Turnstile auto-solve"},
                        {"action": "check_spinner", "selector": ".cf-turnstile"},
                        {"action": "click_checkbox", "selector": ".cf-turnstile input[type=checkbox]", "description": "Click if spinner still visible"},
                        {"action": "wait", "ms": 3000},
                        {"action": "verify_page_progressed"},
                    ],
                },
            },
            {
                "skill_name": "captcha_slider",
                "procedure": {
                    "summary": "Drag slider CAPTCHA with human-like incremental mouse movement",
                    "steps": [
                        {"action": "find_slider", "description": "Locate slider handle element"},
                        {"action": "get_slider_bounds"},
                        {"action": "mouse_down_on_handle"},
                        {"action": "incremental_drag_right", "description": "Move right in small steps, add slight Y jitter"},
                        {"action": "mouse_up"},
                        {"action": "wait", "ms": 1000},
                        {"action": "check_success"},
                    ],
                },
            },
            {
                "skill_name": "captcha_image_text",
                "procedure": {
                    "summary": "Read image-text CAPTCHA using LLM vision OCR",
                    "steps": [
                        {"action": "find_captcha_image"},
                        {"action": "screenshot_captcha_element"},
                        {"action": "llm_vision_ocr", "description": "Send screenshot to LLM vision — read the characters"},
                        {"action": "normalize_text", "description": "Remove spaces, normalize case"},
                        {"action": "find_text_input"},
                        {"action": "type_solution"},
                        {"action": "submit_captcha"},
                    ],
                },
            },
        ]

        try:
            async with AsyncSessionLocal() as db:
                seeded = 0
                for s in skills:
                    res = await db.execute(
                        select(MemoryProcedural).where(and_(
                            MemoryProcedural.skill_name == s["skill_name"],
                            MemoryProcedural.user_id.is_(None),
                        ))
                    )
                    if not res.scalar_one_or_none():
                        db.add(MemoryProcedural(
                            id=str(uuid.uuid4()),
                            user_id=None,
                            skill_name=s["skill_name"],
                            domain=None,
                            procedure=json.dumps(s["procedure"]),
                            success_count=0,
                            failure_count=0,
                            confidence_score=0.7,
                            last_used=None,
                            last_success=None,
                            created_at=datetime.now(timezone.utc),
                        ))
                        seeded += 1
                if seeded:
                    await db.commit()
                    logger.info(f"[Memory] Seeded {seeded} CAPTCHA skills.")
        except Exception as e:
            logger.error(f"[Memory] seed_captcha_skills error: {e}")

    # ── API helpers ───────────────────────────────────────────────────────────

    async def get_recent_episodes(self, user_id: str, domain: Optional[str] = None, limit: int = 20) -> List[Dict]:
        try:
            async with AsyncSessionLocal() as db:
                q = select(MemoryEpisodic).where(MemoryEpisodic.user_id == user_id)
                if domain:
                    q = q.where(MemoryEpisodic.domain == domain)
                q = q.order_by(MemoryEpisodic.created_at.desc()).limit(limit)
                rows = (await db.execute(q)).scalars().all()
                return [
                    {
                        "id": r.id,
                        "domain": r.domain,
                        "task_summary": r.task_summary,
                        "outcome": r.outcome,
                        "confidence_score": r.confidence_score,
                        "access_count": r.access_count,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"[Memory] get_recent_episodes error: {e}")
            return []

    async def get_all_skills(self, user_id: str) -> List[Dict]:
        try:
            async with AsyncSessionLocal() as db:
                q = (
                    select(MemoryProcedural)
                    .where(or_(MemoryProcedural.user_id == user_id, MemoryProcedural.user_id.is_(None)))
                    .order_by(MemoryProcedural.confidence_score.desc())
                )
                rows = (await db.execute(q)).scalars().all()
                return [
                    {
                        "id": r.id,
                        "skill_name": r.skill_name,
                        "domain": r.domain,
                        "success_count": r.success_count,
                        "failure_count": r.failure_count,
                        "confidence_score": r.confidence_score,
                        "last_used": r.last_used.isoformat() if r.last_used else None,
                        "last_success": r.last_success.isoformat() if r.last_success else None,
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"[Memory] get_all_skills error: {e}")
            return []
