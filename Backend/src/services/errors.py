import uuid
from datetime import datetime, timezone
from typing import Optional, Any

class SciParserError(Exception):
    """Base exception class for all SciParser custom errors."""
    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 500,
        title: str = "Internal Error",
        severity: str = "error",
        retryable: bool = False,
        original_exception: Optional[Exception] = None,
        context: Optional[dict] = None
    ):
        super().__init__(message)
        self.error_id = f"ERR-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        self.message = message
        self.code = code
        self.status_code = status_code
        self.title = title
        self.severity = severity
        self.retryable = retryable
        self.original_exception = original_exception
        self.context = context or {}

class ValidationError(SciParserError):
    def __init__(self, message: str, context: Optional[dict] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=400,
            title="Validation Error",
            severity="warning",
            retryable=False,
            context=context
        )

class AuthenticationError(SciParserError):
    def __init__(self, message: str = "Authentication credentials not provided or invalid.", context: Optional[dict] = None):
        super().__init__(
            message=message,
            code="AUTHENTICATION_FAILED",
            status_code=401,
            title="Authentication Failed",
            severity="error",
            retryable=False,
            context=context
        )

class AuthorizationError(SciParserError):
    def __init__(self, message: str = "You do not have permission to access this resource.", context: Optional[dict] = None):
        super().__init__(
            message=message,
            code="PERMISSION_DENIED",
            status_code=403,
            title="Permission Denied",
            severity="error",
            retryable=False,
            context=context
        )

class NotFoundError(SciParserError):
    def __init__(self, message: str = "The requested resource could not be found.", context: Optional[dict] = None):
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=404,
            title="Resource Not Found",
            severity="warning",
            retryable=False,
            context=context
        )

class RateLimitExceededError(SciParserError):
    def __init__(self, message: str = "Too many requests were sent in a short period. Please wait a moment.", context: Optional[dict] = None):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            title="Rate Limit Exceeded",
            severity="warning",
            retryable=True,
            context=context
        )

class CreditLimitExceededError(SciParserError):
    def __init__(self, message: str = "You have reached your credit usage limit. Please contact your administrator.", context: Optional[dict] = None):
        super().__init__(
            message=message,
            code="CREDIT_LIMIT_EXCEEDED",
            status_code=402,
            title="Credit Limit Reached",
            severity="error",
            retryable=False,
            context=context
        )

class LLMProviderError(SciParserError):
    def __init__(self, message: str = "The AI service is experiencing difficulties responding. Please try again.", original_exception: Optional[Exception] = None, context: Optional[dict] = None):
        super().__init__(
            message=message,
            code="LLM_PROVIDER_ERROR",
            status_code=502,
            title="AI Service Error",
            severity="error",
            retryable=True,
            original_exception=original_exception,
            context=context
        )

class ModelTimeoutError(SciParserError):
    def __init__(self, message: str = "The AI service took longer than expected to respond.", original_exception: Optional[Exception] = None, context: Optional[dict] = None):
        super().__init__(
            message=message,
            code="MODEL_TIMEOUT",
            status_code=504,
            title="Request Timed Out",
            severity="warning",
            retryable=True,
            original_exception=original_exception,
            context=context
        )

class ToolExecutionError(SciParserError):
    def __init__(self, message: str, original_exception: Optional[Exception] = None, context: Optional[dict] = None):
        super().__init__(
            message=message,
            code="TOOL_EXECUTION_FAILED",
            status_code=500,
            title="Tool Action Failed",
            severity="error",
            retryable=True,
            original_exception=original_exception,
            context=context
        )

class DatabaseError(SciParserError):
    def __init__(self, message: str = "We're experiencing a temporary service issue. Please try again.", original_exception: Optional[Exception] = None, context: Optional[dict] = None):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            status_code=500,
            title="Service Issue",
            severity="critical",
            retryable=True,
            original_exception=original_exception,
            context=context
        )
