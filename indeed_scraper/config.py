from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    indeed_base_url: str = "https://ca.indeed.com/jobs"
    page_size: int = 10
    politeness_delay_s: float = 1.5
    max_retries: int = 3
    request_timeout_s: int = 15
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    class Config:
        env_prefix = "INDEED_"


settings = Settings()
