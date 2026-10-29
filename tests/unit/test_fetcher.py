"""Unit tests for the HTTP fetcher module."""

from unittest.mock import MagicMock

import pytest
import requests

from tracker.exceptions import FetchError
from tracker.fetcher import fetch


def test_fetch_sets_user_agent_and_headers():
    """Test that fetch sets proper User-Agent and headers on requests."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>Product Page</body></html>"
    mock_session.get.return_value = mock_response

    html = fetch("https://example.com/item", session=mock_session)

    assert html == "<html><body>Product Page</body></html>"
    mock_session.get.assert_called_once()
    call_kwargs = mock_session.get.call_args.kwargs
    assert "headers" in call_kwargs
    assert "User-Agent" in call_kwargs["headers"]
    assert "PriceTracker" in call_kwargs["headers"]["User-Agent"]


def test_fetch_raises_fetch_error_on_http_error():
    """Test that fetch raises FetchError on 4xx/5xx status codes."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.reason = "Internal Server Error"
    mock_session.get.return_value = mock_response

    with pytest.raises(FetchError) as exc_info:
        fetch("https://example.com/fail", session=mock_session)

    assert exc_info.value.status_code == 500
    assert "500" in str(exc_info.value)


def test_fetch_raises_fetch_error_on_timeout():
    """Test that fetch raises FetchError when a timeout occurs."""
    mock_session = MagicMock()
    mock_session.get.side_effect = requests.Timeout("Connection timed out")

    with pytest.raises(FetchError) as exc_info:
        fetch("https://example.com/timeout", session=mock_session)

    assert "timed out" in str(exc_info.value).lower()


def test_fetch_raises_fetch_error_on_connection_error():
    """Test that fetch raises FetchError on network connection failure."""
    mock_session = MagicMock()
    mock_session.get.side_effect = requests.ConnectionError("Failed to resolve host")

    with pytest.raises(FetchError) as exc_info:
        fetch("https://invalid-host.local", session=mock_session)

    assert "Failed to resolve host" in str(exc_info.value)
