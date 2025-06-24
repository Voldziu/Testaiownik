# src/Testaiownik/Backend/middleware/session.py
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import uuid
from datetime import datetime

from ..database.crud import create_user, get_user, update_user_activity
from utils import logger


class SessionMiddleware(BaseHTTPMiddleware):
    """Middleware to handle user management via X-User-ID header"""

    # Endpoints that don't require user ID
    EXEMPT_PATHS = ["/api/health", "/docs", "/redoc", "/openapi.json"]

    async def dispatch(self, request: Request, call_next):
        # Skip user check for exempt paths
        if any(request.url.path.startswith(path) for path in self.EXEMPT_PATHS):
            return await call_next(request)

        user_id = request.headers.get("X-User-ID")

        # Generate new user if not provided
        if not user_id:
            user_id = f"user_{uuid.uuid4()}"
            logger.info(f"Generated new user: {user_id}")

            # Create user in database
            create_user(user_id)

            # Add user to request for route handlers
            request.state.user_id = user_id

            response = await call_next(request)
            response.headers["X-User-ID"] = user_id
            return response

        # Validate existing user
        try:
            user = get_user(user_id)
            if not user:
                # User doesn't exist, create it
                create_user(user_id)
                logger.info(f"Created missing user: {user_id}")
            else:
                # Update last activity
                update_user_activity(user_id)

            # Add user to request state
            request.state.user_id = user_id

            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"User validation error: {e}")
            raise HTTPException(
                status_code=401, detail="Invalid user ID. Please refresh the page."
            )
