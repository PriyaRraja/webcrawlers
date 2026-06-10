from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    base_url: str = "http://books.toscrape.com"
    page_size: int = 20
    politeness_delay_s: float = 0.5
    max_retries: int = 3
    request_timeout_s: int = 15
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

    class Config:
        env_prefix = "BOOKS_"


settings = Settings()
