# src/Testaiownik/Backend/middleware/session.py
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import uuid

from ..database.crud import create_user, get_user, update_user_activity
from ..database.sql_database_connector import SessionLocal, get_db
from utils import logger


class SessionMiddleware(BaseHTTPMiddleware):
    """Middleware to handle user management via X-User-ID header"""

    EXEMPT_PATHS = ["/api/health", "/docs", "/redoc", "/openapi.json"]

    async def dispatch(self, request: Request, call_next):
        logger.debug(f"Middleware processing: {request.method} {request.url.path}")

        if any(request.url.path.startswith(path) for path in self.EXEMPT_PATHS):
            logger.debug(f"Skipping auth for exempt path: {request.url.path}")
            return await call_next(request)

        user_id = request.headers.get("X-User-ID")
        logger.debug(f"Received X-User-ID header: {user_id}")

        if not user_id:
            user_id = f"user_{uuid.uuid4()}"
            logger.info(f"Generated new user: {user_id}")
            db = SessionLocal() 
            try:

                user_data = create_user(db, user_id)

                logger.info(f"Created user: {user_data.user_id}")

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

        db = next(get_db())
        try:
            logger.debug(f"Validating user: {user_id}")
            user_data = get_user(db, user_id)  

            if not user_data: 
                logger.info(f"User {user_id} not found, creating...")
                user_data = create_user(db, user_id)
                logger.info(f"Created missing user: {user_data.user_id}")
            else:
                logger.debug(f"User {user_id} found, updating activity...")
                update_user_activity(db, user_id)
                logger.debug(f"Updated activity for user: {user_id}")

            request.state.user_id = user_id
            logger.debug(f"Set request.state.user_id = {user_id}")

            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"User validation error for {user_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=401, detail=f"User validation failed: {str(e)}"
            )
