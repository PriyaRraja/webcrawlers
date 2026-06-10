from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redfin_gis_url: str = "https://www.redfin.com/stingray/api/gis"
    redfin_autocomplete_url: str = "https://www.redfin.com/stingray/do/location-autocomplete"
    page_size: int = 350
    politeness_delay_s: float = 1.0
    max_retries: int = 3
    request_timeout_s: int = 15
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )


settings = Settings()
