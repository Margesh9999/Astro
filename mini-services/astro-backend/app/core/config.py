import os

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Configuration
    ASTRO_API_HOST: str = "0.0.0.0"
    ASTRO_API_PORT: int = 8000
    ASTRO_CORS_ORIGINS: str = "http://localhost:3000"

    # Cache Configuration
    ASTRO_CACHE_DIR: str = "./data"

    # Default Analysis Parameters
    ASTRO_DEFAULT_SYMBOL: str = "^GSPC"  # S&P 500
    ASTRO_LOOKBACK_YEARS: int = 10

    # Ephemeris Settings
    ASTRO_EPHE_PATH: str = ""  # Use default Swiss Ephemeris path

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# Serverless hosts (Vercel, AWS Lambda) only allow writes under /tmp
if (os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")) and "ASTRO_CACHE_DIR" not in os.environ:
    settings.ASTRO_CACHE_DIR = "/tmp/astro-data"