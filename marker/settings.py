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
    NOUGAT_MODEL_MAX: int = 1024 # Max inference length for nougat
    NOUGAT_HALLUCINATION_WORDS: List[str] = ["[MISSING_PAGE_POST]", "## References\n", "**Figure Captions**\n", "Footnote",
                                  "\par\par\par", "## Chapter", "Fig."]
    LAYOUT_MODEL_MAX: int = 512
    LAYOUT_CHUNK_OVERLAP: int = 128

    class Config:
        env_file = find_dotenv("local.env")


settings = Settings()