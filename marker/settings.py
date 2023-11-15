import os
from typing import Optional, List, Dict

from dotenv import find_dotenv
from pydantic import computed_field
from pydantic_settings import BaseSettings
import fitz as pymupdf


class Settings(BaseSettings):
    # General
    TORCH_DEVICE: str = "cpu"
    TASKS_PER_GPU: int = 30 # Each process needs about 1.5GB of VRAM, so set this accordingly
    SUPPORTED_FILETYPES: Dict = {
        "application/pdf": "pdf",
        "application/epub+zip": "epub",
        "application/x-mobipocket-ebook": "mobi",
        "application/vnd.ms-xpsdocument": "xps",
        "application/x-fictionbook+xml": "fb2"
    }
    DEFAULT_LANG: str = "eng" # Default language we assume files to be in

    # PyMuPDF
    TEXT_FLAGS: int = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_LIGATURES & ~pymupdf.TEXT_PRESERVE_IMAGES

    # OCR
    INVALID_CHARS: List[str] = [chr(0xfffd)]
    DPI: int = 800
    SEGMENT_DPI: int = 1200
    TESSDATA_PREFIX: str = ""
    TESSERACT_LANGUAGES: Dict = {
        "English": "eng",
        "Spanish": "spa",
        "Portuguese": "por",
        "French": "fra",
        "German": "deu",
        "Russian": "rus",
    }
    SPELLCHECK_LANGUAGES: Dict = {
        "English": "en",
        "Spanish": "es",
        "Portuguese": "pt",
        "French": "fr",
        "German": "de",
        "Russian": "ru",
    }
    OCR_ALL_PAGES: bool = False

    # Nougat Model
    NOUGAT_MODEL_MAX: int = 1024 # Max inference length for nougat
    NOUGAT_MIN_TOKENS: int = 192 # Min number of tokens to allow nougat to generate
    NOUGAT_HALLUCINATION_WORDS: List[str] = ["[MISSING_PAGE_POST]", "## References\n", "**Figure Captions**\n", "Footnote",
                                  "\par\par\par", "## Chapter", "Fig.", "particle"]
    NOUGAT_DPI: int = 96 # DPI to render images at, matches default settings for nougat
    NOUGAT_MODEL_NAME: str = "Norm/nougat-latex-base" # Name of the model to use

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