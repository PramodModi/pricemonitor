import os
from dataclasses import dataclass


@dataclass
class Config:
    api_base_url: str


settings = Config(
    api_base_url=os.environ.get("API_BASE_URL", "http://localhost:8001")
)