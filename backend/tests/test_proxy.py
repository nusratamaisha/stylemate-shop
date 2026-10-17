"""Behind nginx (Docker), every request comes from nginx's address; PROXY_COUNT makes Flask see the visitor's."""

import pytest

from .test_help import MESSAGE

NGINX = {"REMOTE_ADDR": "172.18.0.3"}


@pytest.fixture
def extra_config():
    return {"PROXY_COUNT": 1, "CONTACT_MESSAGES_PER_DAY": 1}


def test_visitors_behind_the_proxy_have_their_own_daily_limits(client):
    first = {"X-Forwarded-For": "203.0.113.5"}
    assert client.post("/api/contact", json=MESSAGE, headers=first, environ_base=NGINX).status_code == 201
    assert client.post("/api/contact", json=MESSAGE, headers=first, environ_base=NGINX).status_code == 429

    # Same nginx address, different visitor: not blocked by the first visitor's limit
    second = {"X-Forwarded-For": "198.51.100.7"}
    assert client.post("/api/contact", json=MESSAGE, headers=second, environ_base=NGINX).status_code == 201
