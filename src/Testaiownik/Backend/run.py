# src/Testaiownik/Backend/run.py
"""
TESTAIOWNIK Backend Runner

This script starts the FastAPI backend server and can be used alongside
the existing CLI interface in main.py.

Usage:
    python -m Backend.run                    # Development server
"""

import sys
import argparse
import uvicorn
import os
from pathlib import Path
from Backend import app, validate_environment, init_db, create_test_data
from utils import logger

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def parse_args():
    parser = argparse.ArgumentParser(description="TESTAIOWNIK FastAPI Backend Server")

    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)",
    )

    parser.add_argument(
        "--production",
        action="store_true",
        help="Run in production mode (disable auto-reload and debug)",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (production only, default: 1)",
    )

    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip environment validation on startup",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Set the logging level (default: info)",
    )

    parser.add_argument(
        "--create-test-data",
        action="store_true",
        help="Create test data for development",
    )

    return parser.parse_args()


def setup_environment():
    """Setup environment variables if not set"""
    # Set default environment
    if not os.getenv("ENVIRONMENT"):
        os.environ["ENVIRONMENT"] = "development"

    # Ensure upload directory exists
    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)

    logger.info("Environment setup completed")


def main():
    args = parse_args()

    try:
        # Setup environment
        setup_environment()

        # Initialize database
        logger.info("Initializing database...")
        init_db()

        # Validate environment
        if not args.skip_validation:
            logger.info("Validating environment...")
            validate_environment()

        # Create test data if requested
        if args.create_test_data:
            logger.info("Creating test data...")
            create_test_data()

        # Configure server
        server_config = {
            "app": "Backend.main:app",
            "host": args.host,
            "port": args.port,
            "log_level": args.log_level,
        }

        if args.production:
            # Production configuration
            server_config.update(
                {
                    "reload": False,
                    "workers": args.workers,
                    "access_log": True,
                }
            )
            logger.info(f"🚀 Starting TESTAIOWNIK Backend in PRODUCTION mode")
            logger.info(f"   Server: {args.host}:{args.port}")
            logger.info(f"   Workers: {args.workers}")
        else:
            # Development configuration
            server_config.update(
                {
                    "reload": True,
                    "reload_dirs": [str(project_root / "src")],
                    "reload_excludes": ["*.pyc", "__pycache__", "*.log", "uploads/*"],
                }
            )
            logger.info(f"🔧 Starting TESTAIOWNIK Backend in DEVELOPMENT mode")
            logger.info(f"   Server: {args.host}:{args.port}")
            logger.info(f"   Auto-reload: Enabled")

        logger.info(f"   API Docs: http://{args.host}:{args.port}/docs")
        logger.info(f"   Health Check: http://{args.host}:{args.port}/api/health")

        # Start server
        uvicorn.run(**server_config)

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
