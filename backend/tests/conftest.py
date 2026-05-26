"""Pytest hooks for Pro GPU backend tests."""

from app.core.gpu_lib_path import ensure_pro_gpu_lib_path


def pytest_configure(config):  # noqa: ARG001
    ensure_pro_gpu_lib_path()
