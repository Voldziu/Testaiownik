# src/Testaiownik/Backend/middleware/session.py
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import uuid
from datetime import datetime

from database.crud import create_session, get_session, update_session_activity
from utils import logger


class SessionMiddleware(BaseHTTPMiddleware):
    """Middleware to handle session management via X-Session-ID header"""

    # Endpoints that don't require session
    EXEMPT_PATHS = ["/api/health", "/docs", "/redoc", "/openapi.json"]

    async def dispatch(self, request: Request, call_next):
        # Skip session check for exempt paths
        if any(request.url.path.startswith(path) for path in self.EXEMPT_PATHS):
            return await call_next(request)

        session_id = request.headers.get("X-Session-ID")

        # Generate new session if not provided
        if not session_id:
            session_id = f"session_{uuid.uuid4()}"
            logger.info(f"Generated new session: {session_id}")

            # Create session in database
            create_session(session_id)

            # Add session to request for route handlers
            request.state.session_id = session_id

            response = await call_next(request)
            response.headers["X-Session-ID"] = session_id
            return response

        # Validate existing session
        try:
            session = get_session(session_id)
            if not session:
                # Session doesn't exist, create it
                create_session(session_id)
                logger.info(f"Created missing session: {session_id}")
            else:
                # Update last activity
                update_session_activity(session_id)

            # Add session to request state
            request.state.session_id = session_id

            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"Session validation error: {e}")
            raise HTTPException(
                status_code=401, detail="Invalid session. Please refresh the page."
            )
