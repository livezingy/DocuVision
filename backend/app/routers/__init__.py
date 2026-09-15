"""Domain routers for the v1.8.2 main.py split.

Each module exposes a single ``router = APIRouter()`` with the full paths
written on the decorators (no ``prefix``) so the OpenAPI contract stays
byte-identical to the pre-split main.py.
"""
