"""권한 체크 헬퍼. 모든 자성/메모리 접근 전에 호출."""
from __future__ import annotations

from src.self_improvement.user_registry import (
    UnauthorizedError,
    UserRegistry,
    get_registry,
)


def require_known_user(user_id: str, registry: UserRegistry | None = None) -> None:
    """등록되지 않은 사용자면 raise."""
    (registry or get_registry()).get(user_id)


def require_admin(user_id: str, registry: UserRegistry | None = None) -> None:
    """admin이 아니면 raise."""
    r = registry or get_registry()
    if not r.is_admin(user_id):
        raise UnauthorizedError(f"admin 전용 동작 — user_id={user_id}")


def require_adult(user_id: str, registry: UserRegistry | None = None) -> None:
    """미성년자면 raise (성인용 컨텐츠/공유 메모리 접근 차단)."""
    r = registry or get_registry()
    user = r.get(user_id)
    if user.is_minor:
        raise UnauthorizedError(
            f"미성년 사용자 차단 — user_id={user_id} (성인 전용 동작)"
        )


def is_minor(user_id: str, registry: UserRegistry | None = None) -> bool:
    return (registry or get_registry()).get(user_id).is_minor
