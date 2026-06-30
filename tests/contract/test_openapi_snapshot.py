import os
import json
import inspect
import pytest
from fapi.main import app

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "snapshots")
SNAPSHOT_PATH = os.path.join(SNAPSHOT_DIR, "openapi_snapshot.json")

class ResolvedRoute:
    def __init__(self, original_route, resolved_path):
        self.path = resolved_path
        self.methods = getattr(original_route, "methods", [])
        if hasattr(original_route, "endpoint"):
            self.endpoint = original_route.endpoint

def get_all_routes(app_or_router, prefix=""):
    routes = []
    for route in app_or_router.routes:
        route_class = type(route).__name__
        if route_class == "_IncludedRouter":
            inc_prefix = getattr(route.include_context, "prefix", "")
            routes.extend(get_all_routes(route.include_context.included_router, prefix=prefix + inc_prefix))
        elif hasattr(route, "routes"):
            mount_prefix = getattr(route, "path", "")
            routes.extend(get_all_routes(route, prefix=prefix + mount_prefix))
        else:
            routes.append(ResolvedRoute(route, (prefix + getattr(route, "path", "")).replace("//", "/")))
    return routes

def get_route_source_location(path: str):
    """Finds the Python function handling a path and returns its file and line number."""
    for route in get_all_routes(app):
        if getattr(route, "path", None) == path:
            endpoint = getattr(route, "endpoint", None)
            if endpoint:
                try:
                    file_path = inspect.getsourcefile(endpoint)
                    line_num = inspect.getsourcelines(endpoint)[1]
                    return f"{file_path}:{line_num}"
                except Exception:
                    pass
    return "Unknown Location"

def test_openapi_schema_snapshot():
    """
    Compares the generated OpenAPI schema against a saved snapshot to detect
    any modified, deleted, or added routes and schema definitions.
    """
    current_schema = app.openapi()
    
    if os.environ.get("UPDATE_SNAPSHOT") == "1":
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        with open(SNAPSHOT_PATH, "w") as f:
            json.dump(current_schema, f, indent=2)
        pytest.skip("Snapshot file successfully updated!")
        
    assert os.path.exists(SNAPSHOT_PATH), "Snapshot file not found"
    
    with open(SNAPSHOT_PATH, "r") as f:
        saved_schema = json.load(f)
        
    current_paths = current_schema.get("paths", {})
    saved_paths = saved_schema.get("paths", {})
    
    # Identify differing paths
    differing_paths = []
    for path in set(current_paths.keys()).union(saved_paths.keys()):
        if current_paths.get(path) != saved_paths.get(path):
            location = get_route_source_location(path)
            differing_paths.append(f"  - Route: {path}\n    Source Code Location: {location}")
            
    if differing_paths:
        error_msg = (
            "API CONTRACT VIOLATION: Endpoint routes or methods changed!\n"
            "Mismatched locations:\n" + "\n".join(differing_paths) + "\n\n"
            "If this was intentional, update the API contract snapshot by running:\n"
            "UPDATE_SNAPSHOT=1 venv/bin/pytest tests/test_openapi_snapshot.py"
        )
        raise AssertionError(error_msg)
