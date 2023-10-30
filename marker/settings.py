import os
from typing import Optional, List

from dotenv import find_dotenv
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Path settings
    DPI: int = 400
    INVALID_CHARS: List[str] = [chr(0xfffd), "~", chr(65533), "↵"]
    TORCH_DEVICE: str = "cpu"
    TESSDATA_PREFIX: str = ""
    BAD_SPAN_TYPES: List[str] = ["Caption", "Footnote", "Page-footer", "Page-header", "Picture"]

    class Config:
        env_file = find_dotenv("local.env")


settings = Settings()