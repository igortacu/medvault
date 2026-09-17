"""
STUB TEMPORAR — de șters/înlocuit când branch-ul Inei cu implementarea reală
"""

from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class RequestContext:
    user_id: str
    db: AsyncSession


async def get_request_context() -> RequestContext:
    """
    STUB — implementarea reală (a Inei) trebuie să:
    1. citească session_id din cookie
    2. facă lookup în Redis -> user_id
    3. deschidă o tranzacție DB și ruleze `SET LOCAL app.current_user_id = :uid`
    4. întoarcă RequestContext(user_id=..., db=...)

    Varianta de mai jos NU face nimic din toate astea — există doar ca să
    poți rula local testele endpoint-ului tău cu o bază de test, fără RLS activ.
    """
    raise NotImplementedError(
        "STUB: înlocuiește cu implementarea reală a Inei după merge. "
        "Pentru testare locală izolată, mock-uiește această funcție direct "
        "în testele tale (vezi test_router.py mai jos), nu o implementa aici."
    )


async def write_audit_log(
    db: AsyncSession,
    actor_user_id: str,
    target_patient_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str,
    metadata: dict | None = None,
) -> None:
    print(f"[AUDIT STUB] {action} on {resource_type}/{resource_id} by {actor_user_id} -> {metadata}")