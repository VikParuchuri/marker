import os
from typing import Optional, List, Dict

from dotenv import find_dotenv
from pydantic import computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # General
    TORCH_DEVICE: str = "cpu"
    NUM_GPUS: int = 1 # How many gpus are available.  1 GPU means ~40GB of VRAM.  Set to fractions if you have less.
    SUPPORTED_FILETYPES: Dict = {
        "application/pdf": "pdf",
        "application/epub+zip": "epub",
        "application/x-mobipocket-ebook": "mobi",
        "application/vnd.ms-xpsdocument": "xps",
        "application/x-fictionbook+xml": "fb2"
    }


    # OCR
    INVALID_CHARS: List[str] = [chr(0xfffd), "~", chr(65533), "↵"]
    DPI: int = 400
    TESSDATA_PREFIX: str = ""
    FALLBACK_OCR_LANG: str = "eng"

    # Nougat Model
    NOUGAT_MODEL_MAX: int = 1024 # Max inference length for nougat
    NOUGAT_HALLUCINATION_WORDS: List[str] = ["[MISSING_PAGE_POST]", "## References\n", "**Figure Captions**\n", "Footnote",
                                  "\par\par\par", "## Chapter", "Fig."]

    # Layout Model
    BAD_SPAN_TYPES: List[str] = ["Caption", "Footnote", "Page-footer", "Page-header", "Picture"]
    LAYOUT_MODEL_MAX: int = 512
    LAYOUT_CHUNK_OVERLAP: int = 128

    # Ray
    RAY_CACHE_PATH: Optional[str] = None # Where to save ray cache
    RAY_DASHBOARD_HOST: str = "127.0.0.1"
    RAY_CORES_PER_WORKER: int = 1 # How many cpu cores to allocate per worker

    @computed_field
    @property
    def CUDA(self) -> bool:
        return "cuda" in self.TORCH_DEVICE

    class Config:
        env_file = find_dotenv("local.env")


settings = Settings()