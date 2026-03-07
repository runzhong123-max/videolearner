from app.services.errors import ServiceError


class AIError(ServiceError):
    """Base error type for AI generation flow."""


class AIConfigurationError(AIError):
    """Raised when provider/model/key configuration is invalid."""


class AINetworkError(AIError):
    """Raised when request transport fails (timeout, DNS, connection)."""


class AIProviderResponseError(AIError):
    """Raised when provider response status or structure is invalid."""


class AIContractError(AIError):
    """Raised when normalized AI output violates section contract."""
