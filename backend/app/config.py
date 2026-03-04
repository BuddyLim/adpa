from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gcp_key: str
    openai_key: str
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")


settings = Settings()  # pyright: ignore[reportCallIssue]
