from functools import lru_cache
from urllib.parse import quote_plus
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "ShopEase Product Catalog Service"
    app_version: str = "1.0.0"
    app_port: int = 8005
    debug: bool = False
    db_host: str = "127.0.0.1"
    db_port: int = 3310
    db_name: str = "shopease_product_catalog_db"
    db_user: str = "shopease_catalog_user"
    db_password: str = ""
    db_root_password: str = ""
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "shopease-auth-service"
    low_stock_threshold: int = Field(default=5, ge=0)
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    @property
    def database_url(self) -> str:
        user, password = quote_plus(self.db_user), quote_plus(self.db_password)
        return f"mysql+pymysql://{user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"

@lru_cache
def get_settings() -> Settings:
    return Settings()
