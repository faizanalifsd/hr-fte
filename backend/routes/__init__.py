"""
API Routes package.
"""

from .mission_routes import router as mission_router
from .job_routes import router as job_router
from .email_routes import router as email_router
from .application_routes import router as application_router
from .cv_routes import router as cv_router

__all__ = [
    "mission_router",
    "job_router",
    "email_router",
    "application_router",
    "cv_router",
]
