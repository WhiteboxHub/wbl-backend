"""
Dependencies for AI Prep Platform endpoints.
"""

from typing import Generator, Any
from fapi.db.database import get_db


def get_current_candidate_id() -> int:
    """Returns candidate ID from auth context or default fallback candidate ID 1."""
    return 1
