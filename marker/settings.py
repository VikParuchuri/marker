from typing import Optional, List, Dict, Literal

from dotenv import find_dotenv
from pydantic import computed_field
from pydantic_settings import BaseSettings
import torch
import os


class Settings(BaseSettings):
    # General
    TORCH_DEVICE: Optional[str] = None # Note: MPS device does not work for text detection, and will default to CPU
    IMAGE_DPI: int = 96 # DPI to render images pulled from pdf at
    EXTRACT_IMAGES: bool = True # Extract images from pdfs and save them
    PAGINATE_OUTPUT: bool = False # Paginate output markdown
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
    SURYA_OCR_DPI: int = 192
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
    BAD_SPAN_TYPES: List[str] = ["Page-footer", "Page-header", "Picture"] # You can add "Caption" and "Footnote" here to get rid of those elements - this just removes the text, not the image in case of Picture
    LAYOUT_MODEL_CHECKPOINT: str = "vikp/surya_layout3"
    BBOX_INTERSECTION_THRESH: float = 0.7 # How much the layout and pdf bboxes need to overlap to be the same
    TABLE_INTERSECTION_THRESH: float = 0.7
    LAYOUT_BATCH_SIZE: Optional[int] = None # Defaults to 12 for cuda, 6 otherwise
    DEFAULT_BLOCK_TYPE: str = "Text"

    # Ordering model
    SURYA_ORDER_DPI: int = 96
    ORDER_BATCH_SIZE: Optional[int] = None  # Defaults to 12 for cuda, 6 otherwise
    ORDER_MAX_BBOXES: int = 255

    # Table models
    SURYA_TABLE_DPI: int = 192
    TABLE_REC_BATCH_SIZE: Optional[int] = None

    # Headings
    HEADING_LEVEL_COUNT: int = 4
    HEADING_MERGE_THRESHOLD: float = .25
    HEADING_DEFAULT_LEVEL: int = 2

    # Output
    PAGE_SEPARATOR: str = "\n\n" + "-" * 48 + "\n\n"

    # Debug
    DEBUG_DATA_FOLDER: str = os.path.join(BASE_DIR, "debug_data")
    DEBUG: bool = False
    FONT_DIR: str = os.path.join(BASE_DIR, "static", "fonts")
    DEBUG_RENDER_FONT: str = os.path.join(FONT_DIR, "GoNotoCurrent-Regular.ttf")
    FONT_DL_BASE: str = "https://github.com/satbyy/go-noto-universal/releases/download/v7.0"

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