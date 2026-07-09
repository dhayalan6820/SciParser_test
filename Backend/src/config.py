"""
Central configuration module for the SciParser AI backend.

This is the single place that reads environment variables and exposes every
configurable value used across the backend — secrets, URLs, ports, and
timeouts. No other module should read `os.getenv(...)` for these values or
hardcode a URL/secret directly; import from here instead.

Environment variables are loaded from a `.env` file in development (see
`Backend/.env.example` for the full list) and from Replit Secrets in
production. Set `ENVIRONMENT=production` to enable strict validation that
fails fast on missing required secrets, instead of silently falling back to
an insecure development default.
"""
import os
import secrets
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

_logger = logging.getLogger("sciparser")

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"


def _require(name: str) -> str:
    """Read a required environment variable, raising a clear error if unset."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable '{name}'. "
            f"Set it via Replit Secrets (production) or a Backend/.env file (development). "
            f"See Backend/.env.example for the full list of supported variables."
        )
    return value


def _secret(name: str, dev_default: str) -> str:
    """
    Read a secret. In production it MUST be set (no fallback). In development
    it falls back to a clearly-labeled insecure default so local dev keeps working.
    """
    if IS_PRODUCTION:
        return _require(name)
    return os.getenv(name) or dev_default


def _str(name: str, default: str) -> str:
    return os.getenv(name, default)


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw not in (None, "") else default


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw not in (None, "") else default


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _list(name: str, default: list) -> list:
    raw = os.getenv(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Security / Auth
# ---------------------------------------------------------------------------
# No hardcoded fallback secret is ever used. In production JWT_SECRET_KEY
# must be set (Replit Secrets) or startup fails. In development, if it's not
# set in .env, a random secret is generated fresh for this process only —
# it is never written to disk or logged, so it changes on every restart
# (existing sessions will need to log in again after a restart without a
# persisted JWT_SECRET_KEY). Set JWT_SECRET_KEY in Backend/.env to keep
# dev sessions stable across restarts.
if IS_PRODUCTION:
    JWT_SECRET_KEY = _require("JWT_SECRET_KEY")
else:
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    if not JWT_SECRET_KEY:
        JWT_SECRET_KEY = secrets.token_hex(32)
        _logger.warning(
            "JWT_SECRET_KEY is not set — generated a random, process-local secret for "
            "this development session. Sessions will not survive a restart. Set "
            "JWT_SECRET_KEY in Backend/.env to keep sessions stable."
        )
JWT_ALGORITHM = _str("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = _int("ACCESS_TOKEN_EXPIRE_MINUTES", 15 * 60)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASE_URL = _require("DATABASE_URL") if IS_PRODUCTION else os.getenv("DATABASE_URL", "")

# ---------------------------------------------------------------------------
# LLM / third-party API keys & endpoints
# ---------------------------------------------------------------------------
OPENROUTER_API_KEY = _require("OPENROUTER_API_KEY") if IS_PRODUCTION else os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = _str("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = _str("OPENROUTER_MODEL", "google/gemini-3-flash-preview")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# ---------------------------------------------------------------------------
# LLM cost pricing (per million tokens) — used for analytics and credit billing.
# Update these when the provider changes pricing. These are the single source of
# truth; ATAG.py's LLM_PRICING dict reads from here at import time.
# ---------------------------------------------------------------------------
LLM_INPUT_COST_PER_MILLION = _float("LLM_INPUT_COST_PER_MILLION", 0.1)
LLM_OUTPUT_COST_PER_MILLION = _float("LLM_OUTPUT_COST_PER_MILLION", 0.4)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# Development default keeps the previous wide-open behavior; production
# should set CORS_ALLOWED_ORIGINS to a comma-separated allowlist of origins.
CORS_ALLOWED_ORIGINS = _list("CORS_ALLOWED_ORIGINS", default=["*"])

# In production, a wildcard (or unset) CORS_ALLOWED_ORIGINS allows any site to
# make authenticated cross-origin requests against the API. Warn loudly so
# this is never accidentally shipped; opt into it explicitly via
# CORS_ALLOW_WILDCARD_IN_PRODUCTION=true only if you fully understand the risk.
if IS_PRODUCTION and CORS_ALLOWED_ORIGINS == ["*"]:
    if not _bool("CORS_ALLOW_WILDCARD_IN_PRODUCTION", False):
        raise RuntimeError(
            "Refusing to start in production with CORS_ALLOWED_ORIGINS='*' (or unset). "
            "A wildcard CORS policy lets any website make authenticated requests against "
            "this API on behalf of your users. Set CORS_ALLOWED_ORIGINS to a comma-separated "
            "allowlist of trusted origins (e.g. 'https://app.example.com,https://example.com'). "
            "If you have reviewed the risk and truly need a wildcard, set "
            "CORS_ALLOW_WILDCARD_IN_PRODUCTION=true to bypass this check."
        )
    _logger.warning(
        "SECURITY WARNING: CORS_ALLOWED_ORIGINS is '*' in production. Any website can make "
        "authenticated cross-origin requests against this API. Set CORS_ALLOWED_ORIGINS to a "
        "comma-separated allowlist of trusted origins as soon as possible."
    )

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
SERVER_HOST = _str("SERVER_HOST", "0.0.0.0")
SERVER_PORT = _int("SERVER_PORT", 8000)

# ---------------------------------------------------------------------------
# SMTP / email notifications
# ---------------------------------------------------------------------------
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = _int("SMTP_PORT", 587)
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "") or SMTP_USER
SMTP_TIMEOUT_SECONDS = _int("SMTP_TIMEOUT_SECONDS", 15)

# ---------------------------------------------------------------------------
# HTTP client timeouts
# ---------------------------------------------------------------------------
HTTP_CLIENT_TIMEOUT_SECONDS = _float("HTTP_CLIENT_TIMEOUT_SECONDS", 6)
CDP_JSON_TIMEOUT_SECONDS = _float("CDP_JSON_TIMEOUT_SECONDS", 3)
CDP_SCREENSHOT_TIMEOUT_SECONDS = _float("CDP_SCREENSHOT_TIMEOUT_SECONDS", 8)
PROXY_TEST_TIMEOUT_SECONDS = _float("PROXY_TEST_TIMEOUT_SECONDS", 10)

# ---------------------------------------------------------------------------
# Browser automation
# ---------------------------------------------------------------------------
BROWSER_ENGINE = _str("BROWSER_ENGINE", "chrome")
BROWSER_DEFAULT_CDP_HOST = _str("BROWSER_DEFAULT_CDP_HOST", "localhost")
BROWSER_DEFAULT_CDP_PORT = _int("BROWSER_DEFAULT_CDP_PORT", 9222)
BROWSER_CDP_READY_TIMEOUT_SECONDS = _float("BROWSER_CDP_READY_TIMEOUT_SECONDS", 90)
BROWSER_NAVIGATION_TIMEOUT_MS = _int("BROWSER_NAVIGATION_TIMEOUT_MS", 30000)
BROWSER_USE_HEADLESS_DEFAULT = _bool("BROWSER_USE_HEADLESS", True)
BROWSER_USER_AGENT_INDEX_DEFAULT = _int("BROWSER_USER_AGENT_INDEX", 0)

# ---------------------------------------------------------------------------
# Browser automation — per-session runtime overrides
# ---------------------------------------------------------------------------
# Unlike every other value in this file, these are NOT read once at process
# startup. mcp_agent.py (MCPToolManager) launches one browser_use_bridge.py
# subprocess *per user session* and injects a fresh copy of these vars into
# that subprocess's env dict so each concurrent session gets its own CDP
# endpoint/port/profile dir/proxy. The subprocess only ever sees its own copy
# — never the parent process's — so these MUST stay as functions read at
# call time inside the subprocess (browser_use_bridge.py), not module-level
# constants computed once at import time. They are legitimate inter-process
# passthrough values, not stray hardcoded config.
def browser_cdp_url_override() -> Optional[str]:
    """Session-specific CDP URL injected by MCPToolManager for this bridge subprocess."""
    return os.getenv("MCP_BROWSER_CDP_URL") or os.getenv("BROWSER_CDP_URL")


def browser_cdp_port_override() -> Optional[str]:
    """Session-specific CDP port injected by MCPToolManager for this bridge subprocess."""
    return os.getenv("BROWSER_USE_CDP_PORT")


def browser_user_data_dir_override(default: str) -> str:
    """Session-specific browser profile directory injected by MCPToolManager (falls back to `default` if unset)."""
    return os.getenv("BROWSER_USER_DATA_DIR", default)


def browser_proxy_url_override() -> str:
    """Session-specific outbound proxy URL injected by MCPToolManager, e.g. http://user:pass@host:port."""
    return os.getenv("BROWSER_PROXY_URL", "").strip()


def browser_use_own_browser() -> bool:
    """Whether the bridge subprocess should launch/own its own browser instance vs. attach to an existing CDP endpoint."""
    return os.getenv("MCP_BROWSER_USE_OWN_BROWSER", "false").lower() == "true"


# ---------------------------------------------------------------------------
# Third-party check endpoints / defaults
# ---------------------------------------------------------------------------
IP_CHECK_URL = _str("IP_CHECK_URL", "https://api.ipify.org?format=json")
DEFAULT_TARGET_DOMAIN = _str("DEFAULT_TARGET_DOMAIN", "google.com")

# Fallback chain of IP-check services used when testing a proxy. Not every
# provider/network can reach every one of these, so the proxy test tries them
# in order rather than hard-failing against a single site. Can be overridden
# with a comma-separated IP_CHECK_URLS env var.
IP_CHECK_URLS = [
    u.strip() for u in _str(
        "IP_CHECK_URLS",
        "https://api.ipify.org?format=json,https://ipinfo.io/json,https://ifconfig.me/all.json,https://httpbin.org/ip",
    ).split(",") if u.strip()
]

