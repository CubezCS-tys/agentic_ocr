"""
Staged OCR Pipeline

A modular, multi-stage approach to document OCR where each stage has a single responsibility:
- Stage 1: Layout Extraction (HTML skeleton with data-ref placeholders)
- Stage 2: Text Extraction (JSON content mapping)
- Stage 2.5: Math Refinement (optional, for complex equations)
- Stage 3: Assembly (Pure Python, no LLM)
- Stage 4: Validation (optional, LLM judge for quality check)
- Stage 5: Auto-Retry (for pages that fail validation)
"""

from .layout_extractor import LayoutExtractor
from .text_extractor import TextExtractor
from .assembler import Assembler
from .judge import OCRJudge, JudgeVerdict, BatchJudge
from .runner import StagedPipelineRunner

__all__ = [
    "LayoutExtractor",
    "TextExtractor",
    "Assembler",
    "OCRJudge",
    "JudgeVerdict",
    "BatchJudge",
    "StagedPipelineRunner",
]
