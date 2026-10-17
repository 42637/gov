from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore")
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    top_k: int = 5
    rag_data_dir: str = "rag_data/Indian_Schemes_RAG_Updated"
    frontend_origin: str = "http://localhost:5173"
    max_question_length: int = 2000

    def rag_path(self) -> Path:
        return (Path(__file__).resolve().parents[2] / self.rag_data_dir).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()

