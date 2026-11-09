from rest_framework.exceptions import NotFound, NotAuthenticated, PermissionDenied, Throttled, ValidationError

from core.exceptions import exception_handler


def test_validation_exception_has_consistent_error_shape():
    response = exception_handler(
        ValidationError({"title": ["This field is required."], "priority": ["Must be one of: 1."]}),
        {"request": None},
    )

    assert response.status_code == 400
    assert response.data == {
        "error": "title: This field is required. (and 1 more)",
        "code": 400,
        "details": {
            "title": ["This field is required."],
            "priority": ["Must be one of: 1."],
        },
    }


def test_not_found_exception_has_consistent_error_shape():
    response = exception_handler(NotFound("Not found."), {"request": None})

    assert response.status_code == 404
    assert response.data == {"error": "Not found.", "code": 404}


def test_authentication_and_permission_errors_have_consistent_error_shape():
    for exception, status_code in (
        (NotAuthenticated(), 401),
        (PermissionDenied(), 403),
    ):
        response = exception_handler(exception, {"request": None})

        assert response.status_code == status_code
        assert response.data["code"] == status_code
        assert isinstance(response.data["error"], str)


def test_throttle_error_preserves_retry_after_and_error_shape():
    response = exception_handler(Throttled(wait=7), {"request": None})

    assert response.status_code == 429
    assert response.data["code"] == 429
    assert response["Retry-After"] == "7"
