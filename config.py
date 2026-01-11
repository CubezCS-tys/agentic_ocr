"""
RA-OCR Configuration Module
Loads settings from .env file and defines pipeline constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# API Keys
# =============================================================================
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gemini")  # "gemini" or "openai"

# =============================================================================
# Model Configuration
# =============================================================================
GENERATOR_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")  # For HTML generation
GEMINI_JUDGE_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")  # For visual comparison (Gemini)
OPENAI_JUDGE_MODEL = "gpt-4o"  # For visual comparison (OpenAI)

# =============================================================================
# Pipeline Parameters
# =============================================================================
MAX_RETRIES = 5  # Maximum iterations for the feedback loop
TARGET_SCORE = 90  # Fidelity score threshold (0-100) - stricter quality requirement
DPI = 300  # Resolution for PDF to image conversion

# =============================================================================
# Dual Judge Configuration
# =============================================================================
USE_DUAL_JUDGE = os.getenv("USE_DUAL_JUDGE", "true").lower() == "true"
USE_CROSS_MODEL = os.getenv("USE_CROSS_MODEL", "true").lower() == "true"  # Gemini + GPT-4o
USE_EQUATION_SPECIALIST = os.getenv("USE_EQUATION_SPECIALIST", "true").lower() == "true"
USE_VERIFICATION = os.getenv("USE_VERIFICATION", "true").lower() == "true"

# Judge weights (must sum to 1.0)
GEMINI_WEIGHT = float(os.getenv("GEMINI_WEIGHT", "0.5"))
OPENAI_WEIGHT = float(os.getenv("OPENAI_WEIGHT", "0.5"))
EQUATION_WEIGHT = float(os.getenv("EQUATION_WEIGHT", "0.3"))  # Extra weight for equation specialist

# =============================================================================
# Document Analyzer Configuration
# =============================================================================
USE_ANALYZER = os.getenv("USE_ANALYZER", "true").lower() == "true"  # Pre-analyze documents

# =============================================================================
# Paths
# =============================================================================
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
TEMPLATES_DIR = BASE_DIR / "templates"

# Ensure output directory exists
OUTPUT_DIR.mkdir(exist_ok=True)

# =============================================================================
# Validation
# =============================================================================
def validate_config() -> dict:
    """Validate configuration and return status."""
    issues = []
    
    if not GOOGLE_API_KEY:
        issues.append("GOOGLE_API_KEY is not set in .env file")
    
    if JUDGE_MODEL == "openai" and not OPENAI_API_KEY:
        issues.append("OPENAI_API_KEY is required when JUDGE_MODEL=openai")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "config": {
            "generator_model": GENERATOR_MODEL,
            "judge_model": GEMINI_JUDGE_MODEL if JUDGE_MODEL == "gemini" else OPENAI_JUDGE_MODEL,
            "max_retries": MAX_RETRIES,
            "target_score": TARGET_SCORE,
            "dpi": DPI,
        }
    }
