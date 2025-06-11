import os
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from typing import Optional
from utils.logger import logger
from config import config

LLM_TEMPERATURE = 0.2
LLM_MAX_TOKENS = 1000


def get_llm(
    azure_endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
    deployment_name: Optional[str] = None,
    api_version: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
):

    azure_endpoint = azure_endpoint or config.AZURE_ENDPOINT
    api_key = api_key or config.API_KEY
    deployment_name = (
        deployment_name or config.DEPLOYMENT_NAME_DEV
    )  #  gpt4o-mini for CHAT_MODEL_NAME_DEV and gpt4o for CHAT_MODEL_NAME
    api_version = api_version or config.API_VERSION_DEV
    # 2024-07-18 for CHAT_MODEL_VERSION_DEV and 2024-11-20 for CHAT_MODEL_VERSION
    temperature = temperature if temperature is not None else LLM_TEMPERATURE
    max_tokens = max_tokens if max_tokens is not None else LLM_MAX_TOKENS

    logger.info(
        f"Instianting Azure Chat OpenAi with parameters: "
        f"endpoint={azure_endpoint}, "
        f"deployment={deployment_name}, "
        f"api_version={api_version}, "
        f"temperature={temperature}, "
        f"max_tokens={max_tokens}"
    )

    llm = AzureChatOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        deployment_name=deployment_name,
        api_version=api_version,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # Log comprehensive LLM status
    logger.info("✅ LLM instance created successfully")
    logger.info(f"LLM Endpoint: {getattr(llm, 'azure_endpoint', 'Unknown')}")
    logger.info(f"LLM Deployment: {getattr(llm, 'deployment_name', 'Unknown')}")
    logger.info(f"LLM API Version: {getattr(llm, 'openai_api_version', 'Unknown')}")
    logger.info(f"Model Version: {getattr(llm, 'model_version', 'Unknown')}")
    logger.info(f"LLM Model: {getattr(llm, 'model_name','Unknown')}")
    logger.info(f"LLM Temperature: {getattr(llm, 'temperature', 'Unknown')}")
    logger.info(f"LLM Max Tokens: {getattr(llm, 'max_tokens', 'Unknown')}")
    logger.info(
        f"LLM Client Type: {type(getattr(llm, 'client', None)).__name__ if hasattr(llm, 'client') else 'Unknown'}"
    )

    return llm


def get_embedding_model(
    azure_endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
    deployment_name: Optional[str] = None,
    api_version: Optional[str] = None,
):
    """Get the embedding model instance."""

    azure_endpoint = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
    deployment_name = deployment_name or os.getenv("EMBEDDING_MODEL_NAME")
    api_version = api_version or os.getenv("EMBEDDING_MODEL_VERSION")

    return AzureOpenAIEmbeddings(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        deployment_name=deployment_name,
        api_version=api_version,
    )
