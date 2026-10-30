"""Custom exceptions for price tracker."""


class TrackerError(Exception):
    """Base exception for all price tracker errors."""


class FetchError(TrackerError):
    """Exception raised when fetching a web page fails."""

    def __init__(
        self,
        url: str,
        message: str,
        status_code: int | None = None,
    ) -> None:
        self.url = url
        self.message = message
        self.status_code = status_code
        status_detail = f" (status code: {status_code})" if status_code else ""
        super().__init__(f"Failed to fetch '{url}'{status_detail}: {message}")


class NoPriceFoundError(TrackerError):
    """Raised when a product page has no extractable price."""


class DuplicateProductError(TrackerError):
    """Raised when a product URL is already being tracked."""


class ProductNotFoundError(TrackerError):
    """Raised when a product cannot be found by ID or URL."""
