from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./trading_intel.db"
    ALPHA_VANTAGE_API_KEY: str = "NBJP5NJ08WDSH3Z3"
    ALPHA_VANTAGE_BASE_URL: str = "https://www.alphavantage.co/query"
    FINNHUB_API_KEY: str = ""
    NEWSAPI_KEY: str = ""
    FRED_API_KEY: str = ""
    MINIMAX_API_KEY: str = ""
    MINIMAX_BASE_URL: str = "https://api.minimax.io/anthropic"
    MINIMAX_MODEL: str = "MiniMax-M2.7"
    OPENROUTER_API_KEY: str = ""
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
