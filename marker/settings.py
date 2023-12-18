import os
from typing import Optional, List, Dict

from dotenv import find_dotenv
from pydantic import computed_field
from pydantic_settings import BaseSettings
import fitz as pymupdf
import torch


class Settings(BaseSettings):
    # General
    TORCH_DEVICE: str = "cpu"
    INFERENCE_RAM: int = 40 # How much VRAM each GPU has (in GB).
    VRAM_PER_TASK: float = 2.5 # How much VRAM to allocate per task (in GB).  Peak marker VRAM usage is around 3GB, but avg across workers is lower.
    DEFAULT_LANG: str = "English" # Default language we assume files to be in, should be one of the keys in TESSERACT_LANGUAGES

    SUPPORTED_FILETYPES: Dict = {
        "application/pdf": "pdf",
        "application/epub+zip": "epub",
        "application/x-mobipocket-ebook": "mobi",
        "application/vnd.ms-xpsdocument": "xps",
        "application/x-fictionbook+xml": "fb2"
    }

    # PyMuPDF
    TEXT_FLAGS: int = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_LIGATURES & ~pymupdf.TEXT_PRESERVE_IMAGES

    # OCR
    INVALID_CHARS: List[str] = [chr(0xfffd), "�"]
    OCR_DPI: int = 400
    TESSDATA_PREFIX: str = ""
    TESSERACT_LANGUAGES: Dict = {
        "English": "eng",
        "Spanish": "spa",
        "Portuguese": "por",
        "French": "fra",
        "German": "deu",
        "Russian": "rus",
        "Chinese": "chi_sim",
        "Japanese": "jpn",
        "Korean": "kor",
        "Hindi": "hin",
    }
    TESSERACT_TIMEOUT: int = 20 # When to give up on OCR
    SPELLCHECK_LANGUAGES: Dict = {
        "English": "en",
        "Spanish": "es",
        "Portuguese": "pt",
        "French": "fr",
        "German": "de",
        "Russian": "ru",
        "Chinese": None,
        "Japanese": None,
        "Korean": None,
        "Hindi": None,
    }
    OCR_ALL_PAGES: bool = False # Run OCR on every page even if text can be extracted
    OCR_PARALLEL_WORKERS: int = 2 # How many CPU workers to use for OCR
    OCR_ENGINE: str = "ocrmypdf" # Which OCR engine to use, either "tesseract" or "ocrmypdf".  Ocrmypdf is higher quality, but slower.

    # Nougat model
    NOUGAT_MODEL_MAX: int = 512 # Max inference length for nougat
    NOUGAT_TOKEN_BUFFER: int = 256 # Number of tokens to buffer above max for nougat
    NOUGAT_HALLUCINATION_WORDS: List[str] = [
        "[MISSING_PAGE_POST]",
        "## References\n",
        "**Figure Captions**\n",
        "Footnote",
        "\par\par\par",
        "## Chapter",
        "Fig.",
        "particle",
        "[REPEATS]",
        "[TRUNCATED]",
        "### ",
        "effective field strength",
        "\Phi_{\rm eff}",
        "\mathbf{\mathbf"
    ]
    NOUGAT_DPI: int = 96 # DPI to render images at, matches default settings for nougat
    NOUGAT_MODEL_NAME: str = "0.1.0-small" # Name of the model to use
    NOUGAT_BATCH_SIZE: int = 6 if TORCH_DEVICE == "cuda" else 1 # Batch size for nougat, don't batch on cpu

    # Layout model
    BAD_SPAN_TYPES: List[str] = ["Caption", "Footnote", "Page-footer", "Page-header", "Picture"]
    LAYOUT_MODEL_MAX: int = 512
    LAYOUT_CHUNK_OVERLAP: int = 64
    LAYOUT_DPI: int = 96
    LAYOUT_MODEL_NAME: str = "vikp/layout_segmenter"
    LAYOUT_BATCH_SIZE: int = 8 # Max 512 tokens means high batch size

    # Ordering model
    ORDERER_BATCH_SIZE: int = 32 # This can be high, because max token count is 128
    ORDERER_MODEL_NAME: str = "vikp/column_detector"

    # Final editing model
    EDITOR_BATCH_SIZE: int = 4
    EDITOR_MAX_LENGTH: int = 1024
    EDITOR_MODEL_NAME: str = "vikp/pdf_postprocessor_t5"
    ENABLE_EDITOR_MODEL: bool = False # The editor model can create false positives
    EDITOR_CUTOFF_THRESH: float = 0.9 # Ignore predictions below this probability

    # Ray
    RAY_CACHE_PATH: Optional[str] = None # Where to save ray cache
    RAY_DASHBOARD_HOST: str = "127.0.0.1"
    RAY_CORES_PER_WORKER: int = 1 # How many cpu cores to allocate per worker

    # Debug
    DEBUG: bool = False # Enable debug logging
    DEBUG_DATA_FOLDER: Optional[str] = None
    DEBUG_LEVEL: int = 0 # 0 to 2, 2 means log everything

    @computed_field
    @property
    def CUDA(self) -> bool:
        return "cuda" in self.TORCH_DEVICE

    @computed_field
    @property
    def MODEL_DTYPE(self) -> torch.dtype:
        return torch.bfloat16 if self.CUDA else torch.float32

    class Config:
        env_file = find_dotenv("local.env")
        extra = "ignore"


settings = Settings()