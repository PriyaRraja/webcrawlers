from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mqa_base_url: str = "https://mqa-internet.doh.state.fl.us/MQASearchServices/HealthCareProviders"
    browser_timeout_ms: int = 30_000
    politeness_delay_s: float = 0.5
    headless: bool = True


settings = Settings()
