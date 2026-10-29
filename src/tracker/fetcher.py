"""HTTP fetching module for price tracker."""

import requests
from pydantic import ValidationError
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from tracker.config import get_settings
from tracker.exceptions import FetchError

# Default timeout in seconds when config is unavailable
DEFAULT_TIMEOUT = 15
DEFAULT_USER_AGENT = "PriceTracker/1.0 (+https://github.com/<user>/price-tracker)"


def create_retry_session() -> requests.Session:
    """Create a requests session with retry strategy and exponential backoff."""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,  # 1s, 2s, 4s backoff intervals
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def fetch(
    url: str,
    timeout: int | None = None,
    session: requests.Session | None = None,
) -> str:
    """Fetch a URL and return the HTML body as a string.

    Args:
        url: The web page URL to fetch.
        timeout: Optional request timeout in seconds. Defaults to config setting or 15s.
        session: Optional requests.Session instance to use (for reuse / testing).

    Returns:
        The response HTML body as a string.

    Raises:
        FetchError: If the request fails after all retries or returns an error status code.
    """
    try:
        settings = get_settings()
        user_agent = settings.user_agent
        default_timeout = settings.fetch_timeout
    except ValidationError:
        user_agent = DEFAULT_USER_AGENT
        default_timeout = DEFAULT_TIMEOUT

    effective_timeout = timeout if timeout is not None else default_timeout

    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,pt-PT;q=0.8,pt;q=0.7",
    }

    req_session = session or create_retry_session()

    try:
        response = req_session.get(
            url,
            headers=headers,
            timeout=effective_timeout,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        raise FetchError(url=url, message=str(exc), status_code=status_code) from exc

    if response.status_code >= 400:
        raise FetchError(
            url=url,
            message=f"HTTP status {response.status_code} ({response.reason})",
            status_code=response.status_code,
        )

    return response.text
