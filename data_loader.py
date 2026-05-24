import importlib.util
import os
import sys
from typing import Any, Dict, List, Optional


def get_project_root() -> str:
    if getattr(sys, "frozen", False):
        return os.path.abspath(os.path.dirname(sys.executable))
    return os.path.abspath(os.path.dirname(__file__))


def get_candidate_paths() -> List[str]:
    root = get_project_root()
    candidates = [root, os.getcwd(), "/srv/app", "/app", "/usr/src/app", "/workspace"]
    return [os.path.abspath(path) for path in candidates if path]


def ensure_project_root() -> None:
    project_root = get_project_root()
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    for candidate in get_candidate_paths():
        if candidate not in sys.path and os.path.isdir(candidate):
            sys.path.insert(0, candidate)


def load_module_from_path(module_name: str, path: str) -> Optional[Any]:
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_courses() -> Dict[int, Dict[str, Any]]:
    try:
        from data.courses import COURSES
        return COURSES
    except Exception:
        pass

    candidates = [
        os.path.join(get_project_root(), "data", "courses.py"),
        "/srv/app/data/courses.py",
        "/app/data/courses.py",
        os.path.join(os.getcwd(), "data", "courses.py"),
    ]
    for path in candidates:
        module = load_module_from_path("data.courses", path)
        if module is not None and hasattr(module, "COURSES"):
            return getattr(module, "COURSES")

    raise ImportError(
        "Cannot import COURSES from data.courses. "
        "Checked standard package import and fallback paths: "
        + ", ".join(candidates)
    )
