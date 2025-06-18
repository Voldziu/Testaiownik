from pathlib import Path
from dotenv import load_dotenv
from utils.logger import logger
import os

project_root = Path(__file__).parent.parent.parent.parent

logger.info(f"Loading dotenv from {project_root}")
load_dotenv(project_root / ".env")


AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
DEPLOYMENT_NAME_DEV = os.getenv("CHAT_MODEL_NAME_DEV")
API_VERSION_DEV = os.getenv("CHAT_MODEL_VERSION_DEV")

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")
EMBEDDING_MODEL_VERSION = os.getenv("EMBEDDING_MODEL_VERSION")
