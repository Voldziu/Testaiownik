# src/Testaiownik/Backend/middleware/session.py
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import Depends

from ..database.crud import create_user, get_user, update_user_activity
from ..database.sql_database_connector import SessionLocal
from utils import logger


class SessionMiddleware(BaseHTTPMiddleware):
    """Middleware to handle user management via X-User-ID header"""

    # Endpoints that don't require user ID
    EXEMPT_PATHS = ["/api/health", "/docs", "/redoc", "/openapi.json"]

    async def dispatch(self, request: Request, call_next):
        logger.debug(f"Middleware processing: {request.method} {request.url.path}")

        # Skip user check for exempt paths
        if any(request.url.path.startswith(path) for path in self.EXEMPT_PATHS):
            logger.debug(f"Skipping auth for exempt path: {request.url.path}")
            return await call_next(request)

        user_id = request.headers.get("X-User-ID")
        logger.debug(f"Received X-User-ID header: {user_id}")

        # Generate new user if not provided
        if not user_id:
            user_id = f"user_{uuid.uuid4()}"
            logger.info(f"Generated new user: {user_id}")
            db = SessionLocal()  # Create a new session for the request
            try:
                # Create user in database (returns dict now)

                user_data = create_user(db, user_id)

                logger.info(f"Created user: {user_data.user_id}")

                # Add user to request for route handlers
                request.state.user_id = user_id
                logger.debug(f"Set request.state.user_id = {user_id}")

                response = await call_next(request)
                response.headers["X-User-ID"] = user_id
                return response

            except Exception as e:
                logger.error(f"Failed to create new user: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500, detail="Failed to create user session"
                )
            finally:
                db.close()

        # Validate existing user
        db = SessionLocal()
        try:
            logger.debug(f"Validating existing user: {user_id}")
            user_data = get_user(db, user_id)  # Returns dict or None

            if not user_data:  # User doesn't exist
                logger.info(f"User {user_id} not found, creating...")
                user_data = create_user(db, user_id)
                logger.info(f"Created missing user: {user_data['user_id']}")
            else:
                # Update last activity for existing user
                logger.debug(f"User {user_id} found, updating activity...")
                update_user_activity(db, user_id)
                logger.debug(f"Updated activity for user: {user_id}")

            # Add user to request state
            request.state.user_id = user_id
            logger.debug(f"Set request.state.user_id = {user_id}")

            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"User validation error for {user_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=401, detail=f"User validation failed: {str(e)}"
            )
        finally:
            db.close()
