"""Pytest hooks for Pro GPU backend tests."""

import pytest

from app.core.gpu_lib_path import ensure_pro_gpu_lib_path

LIVE_API_HEALTH_URL = "http://localhost:8000/health"
LIVE_API_SKIP_MESSAGE = f"Live API not reachable at {LIVE_API_HEALTH_URL}"

_LIVE_API_TEST_MODULES = frozenset({"test_api.py", "test_e2e.py"})


def live_api_reachable() -> bool:
    try:
        import requests
    except ImportError:
        return False

    try:
        response = requests.get(LIVE_API_HEALTH_URL, timeout=3)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


@pytest.fixture(scope="module", autouse=True)
def require_live_api(request):
    """Skip live-server integration tests when :8000 is not running."""
    module_file = getattr(request.module, "__file__", "") or ""
    if not any(module_file.endswith(name) for name in _LIVE_API_TEST_MODULES):
        return
    if not live_api_reachable():
        pytest.skip(LIVE_API_SKIP_MESSAGE)


def pytest_configure(config):  # noqa: ARG001
    ensure_pro_gpu_lib_path()
