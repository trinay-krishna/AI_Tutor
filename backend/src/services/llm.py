"""LangChain model factories. Built once and reused; tests can substitute fakes."""

from functools import lru_cache

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from src.config import get_settings


@lru_cache
def get_main_llm() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(model=settings.openai_chat_model, api_key=settings.openai_api_key, temperature=0.2)


@lru_cache
def get_fast_llm() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(model=settings.openai_fast_model, api_key=settings.openai_api_key, temperature=0)


@lru_cache
def get_embeddings() -> OpenAIEmbeddings:
    settings = get_settings()
    return OpenAIEmbeddings(model=settings.openai_embedding_model, api_key=settings.openai_api_key)
