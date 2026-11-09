import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from core.pagination import StandardLimitOffsetPagination


@pytest.mark.parametrize(
    ("query_string", "expected_message"),
    [("?limit=0", "limit must be at least 1."), ("?limit=abc", "limit must be a non-negative integer.")],
)
def test_pagination_rejects_invalid_limit(query_string, expected_message):
    request = Request(APIRequestFactory().get(f"/api/todos{query_string}"))
    paginator = StandardLimitOffsetPagination()

    with pytest.raises(Exception) as exc_info:
        paginator.get_limit(request)

    assert expected_message in str(exc_info.value.detail)


def test_pagination_caps_large_limit():
    request = Request(APIRequestFactory().get("/api/todos?limit=1000"))
    paginator = StandardLimitOffsetPagination()

    assert paginator.get_limit(request) == 100
