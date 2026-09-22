"""SolaX API response classification tests."""

from solax_cloud_api.api_response import (
    is_data_unauthorized_response,
    is_token_invalid_response,
)


def test_token_invalid_response_supports_live_and_documented_codes():
    """Both observed code 103 and documented code 1001 are token failures."""
    assert is_token_invalid_response(
        {"success": False, "code": 103, "exception": "token invalid!"}
    )
    assert is_token_invalid_response(
        {"success": False, "code": 1001, "exception": "Interface Unauthorized"}
    )
    assert is_token_invalid_response(
        {"success": False, "exception": "Token invalid!"}
    )


def test_code_less_no_auth_is_serial_access_failure():
    """A code-less no-auth response must not be classified as token-invalid."""
    payload = {"success": False, "exception": "no auth!", "result": None}

    assert not is_token_invalid_response(payload)
    assert is_data_unauthorized_response(payload)


def test_explicit_1003_remains_serial_access_failure():
    """Documented code 1003 behavior must remain unchanged."""
    payload = {
        "success": False,
        "code": 1003,
        "exception": "no auth!",
        "result": None,
    }

    assert is_data_unauthorized_response(payload)
    assert not is_token_invalid_response(payload)
