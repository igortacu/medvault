"""SQLAlchemy ORM models for the medvault schema.

Importing this package registers every model on Base.metadata, so env.py can
`from app.models import metadata` and hand it to alembic as target_metadata.
"""
from .audit import AuditLog
from .base import Base, metadata
from .caregiver import CaregiverLink, CaregiverPermission
from .document import Document
from .export import DataExport
from .institution import Institution, InstitutionConnection
from .user import PatientProfile, User

__all__ = [
    "Base",
    "metadata",
    "User",
    "PatientProfile",
    "Institution",
    "InstitutionConnection",
    "CaregiverLink",
    "CaregiverPermission",
    "Document",
    "DataExport",
    "AuditLog",
]
