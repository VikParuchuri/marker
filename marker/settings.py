from typing import Optional, List, Dict, Literal

from dotenv import find_dotenv
from pydantic import computed_field
from pydantic_settings import BaseSettings
import torch


class Settings(BaseSettings):
    # General
    TORCH_DEVICE: Optional[str] = None # Note: MPS device does not work for text detection, and will default to CPU
    IMAGE_DPI: int = 96 # DPI to render images pulled from pdf at
    EXTRACT_IMAGES: bool = True # Extract images from pdfs and save them

    @computed_field
    @property
    def TORCH_DEVICE_MODEL(self) -> str:
        if self.TORCH_DEVICE is not None:
            return self.TORCH_DEVICE

        if torch.cuda.is_available():
            return "cuda"

        if torch.backends.mps.is_available():
            return "mps"

        return "cpu"

    INFERENCE_RAM: int = 40 # How much VRAM each GPU has (in GB).
    VRAM_PER_TASK: float = 4.5 # How much VRAM to allocate per task (in GB).  Peak marker VRAM usage is around 5GB, but avg across workers is lower.
    DEFAULT_LANG: str = "English" # Default language we assume files to be in, should be one of the keys in TESSERACT_LANGUAGES

    SUPPORTED_FILETYPES: Dict = {
        "application/pdf": "pdf",
    }

    # Text extraction
    PDFTEXT_CPU_WORKERS: int = 4 # How many CPU workers to use for pdf text extraction

    # Text line Detection
    DETECTOR_BATCH_SIZE: Optional[int] = None # Defaults to 6 for CPU, 12 otherwise
    SURYA_DETECTOR_DPI: int = 96
    DETECTOR_POSTPROCESSING_CPU_WORKERS: int = 4

    # OCR
    INVALID_CHARS: List[str] = [chr(0xfffd), "�"]
    OCR_ENGINE: Optional[Literal["surya", "ocrmypdf"]] = "surya" # Which OCR engine to use, either "surya" or "ocrmypdf".  Defaults to "ocrmypdf" on CPU, "surya" on GPU.
    OCR_ALL_PAGES: bool = False # Run OCR on every page even if text can be extracted

    ## Surya
    SURYA_OCR_DPI: int = 96
    RECOGNITION_BATCH_SIZE: Optional[int] = None # Batch size for surya OCR defaults to 64 for cuda, 32 otherwise

    ## Tesseract
    OCR_PARALLEL_WORKERS: int = 2 # How many CPU workers to use for OCR
    TESSERACT_TIMEOUT: int = 20 # When to give up on OCR
    TESSDATA_PREFIX: str = ""

    # Texify model
    TEXIFY_MODEL_MAX: int = 384 # Max inference length for texify
    TEXIFY_TOKEN_BUFFER: int = 256 # Number of tokens to buffer above max for texify
    TEXIFY_DPI: int = 96 # DPI to render images at
    TEXIFY_BATCH_SIZE: Optional[int] = None # Defaults to 6 for cuda, 12 otherwise
    TEXIFY_MODEL_NAME: str = "vikp/texify"

    # Layout model
    SURYA_LAYOUT_DPI: int = 96
    BAD_SPAN_TYPES: List[str] = ["Caption", "Footnote", "Page-footer", "Page-header", "Picture"]
    LAYOUT_MODEL_CHECKPOINT: str = "vikp/surya_layout2"
    BBOX_INTERSECTION_THRESH: float = 0.7 # How much the layout and pdf bboxes need to overlap to be the same
    LAYOUT_BATCH_SIZE: Optional[int] = None # Defaults to 12 for cuda, 6 otherwise

    # Ordering model
    SURYA_ORDER_DPI: int = 96
    ORDER_BATCH_SIZE: Optional[int] = None  # Defaults to 12 for cuda, 6 otherwise
    ORDER_MAX_BBOXES: int = 255

    # Final editing model
    EDITOR_BATCH_SIZE: Optional[int] = None # Defaults to 6 for cuda, 12 otherwise
    EDITOR_MAX_LENGTH: int = 1024
    EDITOR_MODEL_NAME: str = "vikp/pdf_postprocessor_t5"
    ENABLE_EDITOR_MODEL: bool = False # The editor model can create false positives
    EDITOR_CUTOFF_THRESH: float = 0.9 # Ignore predictions below this probability

    # Ray
    RAY_CACHE_PATH: Optional[str] = None # Where to save ray cache
    RAY_CORES_PER_WORKER: int = 1 # How many cpu cores to allocate per worker

    # Debug
    DEBUG: bool = False # Enable debug logging
    DEBUG_DATA_FOLDER: Optional[str] = None
    DEBUG_LEVEL: int = 0 # 0 to 2, 2 means log everything

    @computed_field
    @property
    def CUDA(self) -> bool:
        return "cuda" in self.TORCH_DEVICE_MODEL

    @computed_field
    @property
    def MODEL_DTYPE(self) -> torch.dtype:
        if self.TORCH_DEVICE_MODEL == "cuda":
            return torch.bfloat16
        else:
            return torch.float32

    @computed_field
    @property
    def TEXIFY_DTYPE(self) -> torch.dtype:
        return torch.float32 if self.TORCH_DEVICE_MODEL == "cpu" else torch.float16

    class Config:
        env_file = find_dotenv("local.env")
        extra = "ignore"


settings = Settings()