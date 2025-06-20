import os
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from typing import Optional
from utils.logger import logger
from config import config

LLM_TEMPERATURE = 0.2
LLM_MAX_TOKENS = 10000


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

    logger.debug(
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
    logger.debug("✅ LLM instance created successfully")
    logger.debug(f"LLM Endpoint: {getattr(llm, 'azure_endpoint', 'Unknown')}")
    logger.debug(f"LLM Deployment: {getattr(llm, 'deployment_name', 'Unknown')}")
    logger.debug(f"LLM API Version: {getattr(llm, 'openai_api_version', 'Unknown')}")
    logger.debug(f"Model Version: {getattr(llm, 'model_version', 'Unknown')}")
    logger.debug(f"LLM Model: {getattr(llm, 'model_name','Unknown')}")
    logger.debug(f"LLM Temperature: {getattr(llm, 'temperature', 'Unknown')}")
    logger.debug(f"LLM Max Tokens: {getattr(llm, 'max_tokens', 'Unknown')}")
    logger.debug(
        f"LLM Client Type: {type(getattr(llm, 'client', None)).__name__ if hasattr(llm, 'client') else 'Unknown'}"
    )

    return llm


def get_embedding_model(
    azure_endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
    deployment_name: Optional[str] = None,
    api_version: Optional[str] = None,
):
    """Get the embedding model instance with improved error handling."""

    azure_endpoint = azure_endpoint or config.AZURE_ENDPOINT
    api_key = api_key or config.API_KEY
    deployment_name = deployment_name or config.EMBEDDING_MODEL_NAME
    api_version = api_version or config.EMBEDDING_MODEL_VERSION

    logger.debug(f"Creating embedding model with:")
    logger.debug(f"  Endpoint: {azure_endpoint}")
    logger.debug(f"  Deployment: {deployment_name}")
    logger.debug(f"  API Version: {api_version}")

    try:
        embedding_model = AzureOpenAIEmbeddings(
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            azure_deployment=deployment_name,
            api_version=api_version,
        )

        logger.debug("Testing embedding model...")
        test_embedding = embedding_model.embed_query("test")
        logger.debug(
            f"Embedding model test successful. Vector size: {len(test_embedding)}"
        )

        return embedding_model

    except Exception as e:
        logger.error(f"Failed to create embedding model: {e}")
        logger.error(f"Check your Azure OpenAI configuration:")
        logger.error(f"  - Endpoint: {azure_endpoint}")
        logger.error(f"  - Deployment name: {deployment_name}")
        logger.error(f"  - API version: {api_version}")
        raise
