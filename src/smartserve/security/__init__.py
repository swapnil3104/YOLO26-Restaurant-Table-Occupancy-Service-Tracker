"""Authentication, API keys, and role-based access control."""

from smartserve.security.auth import (
    get_current_actor,
    require_admin_actor,
    require_manager_or_admin,
    require_roles,
    require_staff_actor,
    resolve_actor,
)

__all__ = [
    "get_current_actor",
    "resolve_actor",
    "require_roles",
    "require_staff_actor",
    "require_manager_or_admin",
    "require_admin_actor",
]
