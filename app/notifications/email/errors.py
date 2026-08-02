"""Email delivery errors (safe messages — never include secrets)."""


class EmailConfigurationError(RuntimeError):
    """Raised when email cannot be sent due to missing/invalid configuration."""


class EmailDeliveryError(RuntimeError):
    """Raised when the transport fails to deliver a message."""
