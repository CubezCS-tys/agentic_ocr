# RA-OCR: Recursive Augmentation OCR

## Complete System Documentation

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture Overview](#system-architecture-overview)
3. [Core Concept: The Agentic Feedback Loop](#core-concept-the-agentic-feedback-loop)
4. [Component Deep Dive](#component-deep-dive)
   - [Configuration Module](#1-configuration-module-configpy)
   - [Main CLI Entry Point](#2-main-cli-entry-point-mainpy)
   - [Pipeline Package](#3-pipeline-package)
   - [Viewer Application](#4-viewer-application-viewer-next)
5. [Data Flow Diagrams](#data-flow-diagrams)
6. [File Structure Reference](#file-structure-reference)
7. [Algorithm Details](#algorithm-details)
8. [API Reference](#api-reference)
9. [Output Structure](#output-structure)
10. [Configuration Options](#configuration-options)

---

## Executive Summary

**RA-OCR (Recursive Augmentation OCR)** is an autonomous AI-powered pipeline that converts PDF documents into "pixel-perfect" HTML/CSS representations. Unlike traditional OCR systems that simply extract text, RA-OCR preserves:

- **Layout fidelity** (multi-column, headers, footers)
- **Typography** (fonts, sizes, weights)
- **Mathematical equations** (rendered via MathJax/LaTeX)
- **Images and figures** (extracted and embedded)
- **Colors and styling** (backgrounds, borders, accents)

The system uses a **self-improving agentic loop** where AI "judges" evaluate the quality of generated HTML and provide feedback for iterative refinement.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        RA-OCR: High-Level Flow                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────┐    ┌───────────┐    ┌──────────┐    ┌─────────────────┐  │
│   │   PDF   │───▶│  Analyze  │───▶│ Generate │───▶│ Render & Judge  │  │
│   │  Input  │    │  Document │    │   HTML   │    │   (Loop ×N)     │  │
│   └─────────┘    └───────────┘    └──────────┘    └────────┬────────┘  │
│                                                             │          │
│                                   ┌─────────────────────────▼────────┐ │
│                                   │  Pixel-Perfect HTML Output       │ │
│                                   │  (Selectable text, MathJax eqs)  │ │
│                                   └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## System Architecture Overview

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Language | Python 3.10+ | Core pipeline logic |
| Generator LLM | Google Gemini 2.5 Flash | PDF → HTML conversion |
| Judge LLMs | Gemini + GPT-4o (Dual) | Visual quality assessment |
| PDF Processing | PyMuPDF (fitz) | Page extraction, image handling |
| HTML Rendering | Playwright | Headless browser screenshots |
| Math Rendering | MathJax 3 | LaTeX equation display |
| CLI Framework | Typer + Rich | User interface |
| Viewer Frontend | Next.js 16 + React 19 | Results visualization |

### Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              RA-OCR SYSTEM ARCHITECTURE                        │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                           CLI Layer (main.py)                            │  │
│  │  • Argument parsing (typer)                                              │  │
│  │  • Configuration validation                                              │  │
│  │  • Progress display (rich)                                               │  │
│  └───────────────────────────────────┬─────────────────────────────────────┘  │
│                                      │                                        │
│  ┌───────────────────────────────────▼─────────────────────────────────────┐  │
│  │                        Pipeline Orchestrator (loop.py)                   │  │
│  │  • OCRPipeline class - main coordinator                                  │  │
│  │  • Page-by-page processing                                               │  │
│  │  • Iteration management                                                  │  │
│  │  • Result aggregation                                                    │  │
│  └───────────────────────────────────┬─────────────────────────────────────┘  │
│                                      │                                        │
│  ┌───────────────────────────────────┼─────────────────────────────────────┐  │
│  │                          Core Pipeline Components                        │  │
│  │                                   │                                      │  │
│  │  ┌────────────┐  ┌────────────┐  │  ┌────────────┐  ┌────────────────┐  │  │
│  │  │  Analyzer  │  │ Ingestion  │◀─┴─▶│ Generator  │  │     Judge      │  │  │
│  │  │            │  │            │     │            │  │ (Single/Dual)  │  │  │
│  │  │ • Doc type │  │ • PDF load │     │ • Gemini   │  │ • Gemini       │  │  │
│  │  │ • Language │  │ • Page PNG │     │ • HTML gen │  │ • GPT-4o       │  │  │
│  │  │ • Layout   │  │ • Figures  │     │ • Refine   │  │ • Equation     │  │  │
│  │  │ • Prompt   │  │ • Base64   │     │            │  │ • Verify       │  │  │
│  │  └────────────┘  └────────────┘     └────────────┘  └────────────────┘  │  │
│  │                                                                          │  │
│  │                          ┌────────────┐                                  │  │
│  │                          │  Renderer  │                                  │  │
│  │                          │            │                                  │  │
│  │                          │ • Playwright                                  │  │
│  │                          │ • MathJax wait                                │  │
│  │                          │ • Screenshot                                  │  │
│  │                          └────────────┘                                  │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                        External Services Layer                           │  │
│  │                                                                          │  │
│  │   ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────┐    │  │
│  │   │  Google Gemini  │  │   OpenAI API    │  │   MathJax CDN        │    │  │
│  │   │  API            │  │   (GPT-4o)      │  │                      │    │  │
│  │   └─────────────────┘  └─────────────────┘  └──────────────────────┘    │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                        Viewer Layer (Next.js)                            │  │
│  │                                                                          │  │
│  │   ┌────────────────────────────────────────────────────────────────┐    │  │
│  │   │  Components: Header | Sidebar | ComparisonView | FeedbackPanel │    │  │
│  │   └────────────────────────────────────────────────────────────────┘    │  │
│  │   ┌────────────────────────────────────────────────────────────────┐    │  │
│  │   │  API Routes: /projects | /project/:name | /page/:id            │    │  │
│  │   └────────────────────────────────────────────────────────────────┘    │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Concept: The Agentic Feedback Loop

The heart of RA-OCR is its **recursive self-improvement loop**. This is what makes it "agentic" - the system autonomously identifies and corrects its own mistakes.

### The Loop Explained

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     THE AGENTIC FEEDBACK LOOP                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Iteration 1                                                               │
│   ──────────                                                                │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                  │
│   │  Original   │     │  Generate   │     │   Render    │                  │
│   │  PDF Page   │────▶│    HTML     │────▶│  to Image   │                  │
│   │  (PNG)      │     │  (Gemini)   │     │ (Playwright)│                  │
│   └─────────────┘     └─────────────┘     └──────┬──────┘                  │
│                                                  │                          │
│                                                  ▼                          │
│   ┌──────────────────────────────────────────────────────────────────┐     │
│   │                          JUDGE                                    │     │
│   │  Compare: Original PDF Image  vs  Rendered HTML Image            │     │
│   │                                                                   │     │
│   │  Scores:                                                          │     │
│   │  • Fidelity: 72/100   ❌ Below target (85)                       │     │
│   │  • Layout: 75/100                                                 │     │
│   │  • Text: 80/100                                                   │     │
│   │  • Equations: 60/100                                              │     │
│   │                                                                   │     │
│   │  Errors:                                                          │     │
│   │  • "Equation 3 rendered as ASCII x^2 instead of LaTeX"           │     │
│   │  • "Second column text wrapping incorrectly"                      │     │
│   │  • "Title font weight should be bold"                             │     │
│   └──────────────────────────────────────────────────────────────────┘     │
│                              │                                              │
│                              ▼                                              │
│   Iteration 2 (Refinement)                                                  │
│   ────────────────────────                                                  │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │  Generator receives:                                             │      │
│   │  • Previous HTML code                                            │      │
│   │  • Judge's error list with FIX instructions                      │      │
│   │  • Original image for reference                                  │      │
│   │                                                                  │      │
│   │  "Fix these specific issues while keeping correct parts..."      │      │
│   └─────────────────────────────────────────────────────────────────┘      │
│                              │                                              │
│                              ▼                                              │
│   ┌─────────────────────────────────────────────────────────────────┐      │
│   │  Re-render → Re-judge → Score: 88/100 ✓ PASSED                  │      │
│   └─────────────────────────────────────────────────────────────────┘      │
│                                                                             │
│   Loop terminates when:                                                     │
│   • Score ≥ TARGET_SCORE (default: 85), OR                                  │
│   • MAX_RETRIES reached (default: 5)                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why This Works

1. **Vision LLMs understand layout** - They can see column structures, fonts, spacing
2. **Specific feedback enables targeted fixes** - Not "make it better", but "change font-size to 24px"
3. **Iterative refinement converges** - Each iteration typically improves 5-15 points
4. **Multiple judges reduce bias** - Gemini + GPT-4o catch different issues

---

## Component Deep Dive

### 1. Configuration Module (`config.py`)

The configuration module centralizes all settings and loads them from environment variables.

```python
# Key Configuration Parameters

# API Keys (from .env)
GOOGLE_API_KEY      # Required: For Gemini models
OPENAI_API_KEY      # Optional: For GPT-4o judge

# Model Selection
GENERATOR_MODEL = "gemini-2.5-flash"    # HTML generation
GEMINI_JUDGE_MODEL = "gemini-2.5-flash" # Visual comparison
OPENAI_JUDGE_MODEL = "gpt-4o"           # Secondary judge

# Pipeline Parameters
MAX_RETRIES = 5      # Max iterations per page
TARGET_SCORE = 85    # Minimum acceptable fidelity (0-100)
DPI = 300            # PDF rendering resolution

# Dual Judge Configuration
USE_DUAL_JUDGE = true           # Use multiple judges
USE_CROSS_MODEL = true          # Use both Gemini + GPT-4o
USE_EQUATION_SPECIALIST = true  # Dedicated equation checker
USE_VERIFICATION = true         # Final pass gate

# Judge Weights
GEMINI_WEIGHT = 0.5    # Weight for Gemini scores
OPENAI_WEIGHT = 0.5    # Weight for GPT-4o scores
EQUATION_WEIGHT = 0.3  # Extra emphasis on equations

# Document Analyzer
USE_ANALYZER = true    # Pre-analyze documents
```

**Validation Function:**
```python
def validate_config() -> dict:
    """Checks API keys are present and returns config status."""
```

---

### 2. Main CLI Entry Point (`main.py`)

The CLI provides three commands:

#### `convert` - Main Conversion Command

```bash
ra-ocr convert document.pdf [OPTIONS]

Options:
  -p, --pages TEXT         Page range (e.g., "1", "1-3", "1,3,5")
  -t, --target INTEGER     Target fidelity score (0-100) [default: 85]
  -r, --max-retries INT    Max refinement iterations [default: 5]
  -o, --output PATH        Output directory
  -l, --language TEXT      Override language detection (e.g., "arabic")
  -d, --direction TEXT     Override text direction ("rtl" or "ltr")
  -v/-q, --verbose/--quiet Show detailed progress
```

#### `check` - Configuration Checker

```bash
ra-ocr check

# Validates:
# ✓ API keys configured
# ✓ Dependencies installed
# ✓ Playwright browsers ready
```

#### `version` - Version Info

```bash
ra-ocr version
# RA-OCR - Recursive Augmentation OCR
# Version 0.1.0
```

---

### 3. Pipeline Package

The `pipeline/` package contains the core processing modules:

```
pipeline/
├── __init__.py      # Package exports
├── analyzer.py      # Document pre-analysis
├── ingestion.py     # PDF loading and extraction
├── generator.py     # HTML generation (Gemini)
├── renderer.py      # HTML → screenshot (Playwright)
├── judge.py         # Single visual judge
├── dual_judge.py    # Multi-judge system
└── loop.py          # Main orchestrator
```

#### 3.1 Ingestion Module (`ingestion.py`)

**Purpose:** Load PDFs and extract page images + embedded figures.

```
┌─────────────────────────────────────────────────────────────────┐
│                      PDFIngestion Class                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Input: PDF file path                                           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    extract_page(n)                       │   │
│  │                                                          │   │
│  │  1. Open PDF with PyMuPDF (fitz)                        │   │
│  │  2. Render page at 300 DPI (zoom = 300/72 ≈ 4.17x)      │   │
│  │  3. Save as PNG to output/doc_name/page_000.png         │   │
│  │  4. Convert to base64 for LLM API                       │   │
│  │  5. Extract embedded images:                             │   │
│  │     • Get image list from page                          │   │
│  │     • Extract each as base64                            │   │
│  │     • Calculate scaled bounding boxes                   │   │
│  │                                                          │   │
│  │  Returns: PageAssets dataclass                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Output: PageAssets {                                           │
│    page_number: int                                             │
│    page_image_path: Path                                        │
│    page_image_base64: str                                       │
│    figures: [{index, bbox, image_base64, mime_type, data_uri}]  │
│    width: int                                                   │
│    height: int                                                  │
│  }                                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key Methods:**
- `extract_page(page_number)` - Extract single page with assets
- `extract_all_pages()` - Extract all pages
- `_extract_figures()` - Find and crop embedded images

---

#### 3.2 Analyzer Module (`analyzer.py`)

**Purpose:** Pre-analyze documents to understand their characteristics and generate custom prompts for better generation.

```
┌─────────────────────────────────────────────────────────────────┐
│                   DocumentAnalyzer Class                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Input: Multiple page images (for holistic analysis)            │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Analysis Categories                     │   │
│  │                                                          │   │
│  │  Language & Direction:                                   │   │
│  │  • primary_language: "Arabic", "English", etc.          │   │
│  │  • text_direction: "rtl" or "ltr"                       │   │
│  │  • has_mixed_directions: bool                            │   │
│  │                                                          │   │
│  │  Content Types:                                          │   │
│  │  • has_equations: bool                                   │   │
│  │  • equation_complexity: "none" | "simple" | "complex"   │   │
│  │  • has_tables, has_figures, has_code_blocks: bool       │   │
│  │                                                          │   │
│  │  Layout:                                                 │   │
│  │  • layout_type: "single-column" | "multi-column"        │   │
│  │  • column_count: int                                     │   │
│  │  • has_headers, has_footers, has_footnotes: bool        │   │
│  │                                                          │   │
│  │  Typography:                                             │   │
│  │  • font_styles: ["serif", "sans-serif", ...]            │   │
│  │  • has_bold, has_italic, has_underline: bool            │   │
│  │                                                          │   │
│  │  Document Type:                                          │   │
│  │  • "academic", "legal", "technical", "letter", etc.     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Output:                                                        │
│  • DocumentAnalysis dataclass (all detected properties)        │
│  • Custom prompt with specific CSS/HTML instructions           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Custom Prompt Generation:**

The analyzer generates tailored instructions based on detected characteristics:

```markdown
## ⚠️ CRITICAL: Right-to-Left (RTL) Document

This is an RTL document. You MUST:
1. Add `dir="rtl"` to the `<html>` tag
2. Add `direction: rtl;` to the body CSS
3. Use `text-align: right;` for text blocks
4. Use an appropriate Arabic font (Amiri, Scheherazade, etc.)
...

## Mathematical Equations

This document contains **complex** equations.
Use MathJax for all equations. Include the MathJax CDN.
...

## Multi-Column Layout

This document has **2 columns**.
Use CSS Grid or Flexbox:
```css
.columns {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
}
```
```

---

#### 3.3 Generator Module (`generator.py`)

**Purpose:** Use Gemini Vision to convert PDF page images to HTML/CSS.

```
┌─────────────────────────────────────────────────────────────────┐
│                    HTMLGenerator Class                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Two Generation Modes:                                          │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  1. INITIAL GENERATION (generate_initial)               │   │
│  │                                                          │   │
│  │  Input:                                                  │   │
│  │  • Page image (base64)                                   │   │
│  │  • Extracted figures                                     │   │
│  │  • Custom prompt from analyzer                           │   │
│  │                                                          │   │
│  │  Prompt instructs LLM to:                                │   │
│  │  • Match exact column structure                          │   │
│  │  • Use appropriate fonts (serif for academic)           │   │
│  │  • Render equations with LaTeX/MathJax                  │   │
│  │  • Place figure placeholders                            │   │
│  │  • Include MathJax CDN scripts                          │   │
│  │                                                          │   │
│  │  Output: Complete HTML file                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  2. REFINEMENT (refine)                                  │   │
│  │                                                          │   │
│  │  Input:                                                  │   │
│  │  • Previous HTML attempt                                 │   │
│  │  • Judge feedback (score + errors)                       │   │
│  │  • Original page image                                   │   │
│  │                                                          │   │
│  │  Prompt:                                                 │   │
│  │  "Your previous attempt scored 72/100.                   │   │
│  │   Fix these issues:                                      │   │
│  │   - Equation 3: use \\frac{a}{b} instead of a/b         │   │
│  │   - Add font-weight: bold to h1                         │   │
│  │   - Set grid-template-columns: 1fr 1fr"                 │   │
│  │                                                          │   │
│  │  Output: Corrected HTML                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Post-processing:                                               │
│  • Clean markdown code blocks from response                     │
│  • Inject extracted figures as base64 data URIs                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key Prompt Features:**

The generator prompt emphasizes:
1. **MathJax integration** with proper configuration
2. **Typography precision** (font families, sizes, weights)
3. **Layout accuracy** (CSS Grid/Flexbox for columns)
4. **LaTeX equation formatting** (inline `\(...\)` and display `$$...$$`)

---

#### 3.4 Renderer Module (`renderer.py`)

**Purpose:** Render HTML to images using Playwright headless browser.

```
┌─────────────────────────────────────────────────────────────────┐
│                     HTMLRenderer Class                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Configuration:                                                 │
│  • viewport_width: 1200px                                       │
│  • viewport_height: 1600px                                      │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │               render_to_image(html, path)                │   │
│  │                                                          │   │
│  │  1. Save HTML to temp file                               │   │
│  │  2. Launch Chromium browser (headless)                   │   │
│  │  3. Navigate to file:// URL                              │   │
│  │  4. Wait for MathJax rendering:                          │   │
│  │     await MathJax.startup.promise                        │   │
│  │  5. Wait for network idle (fonts, images)                │   │
│  │  6. Take full-page screenshot                            │   │
│  │  7. Save as PNG                                          │   │
│  │                                                          │   │
│  │  Returns: Path to rendered image                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  MathJax Wait Logic:                                            │
│  • Check if MathJax global exists                               │
│  • Wait for MathJax.startup.promise to resolve                  │
│  • Additional 500ms delay for rendering completion             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

#### 3.5 Judge Module (`judge.py`)

**Purpose:** Compare original PDF with rendered HTML using vision LLMs.

```
┌─────────────────────────────────────────────────────────────────┐
│                     VisualJudge Class                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Supports: Gemini or OpenAI (based on JUDGE_MODEL config)       │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 compare(original, rendered)              │   │
│  │                                                          │   │
│  │  Sends to LLM:                                           │   │
│  │  • "Here is the ORIGINAL PDF page:" + image             │   │
│  │  • "Here is the RENDERED HTML page:" + image            │   │
│  │  • Detailed evaluation prompt                            │   │
│  │                                                          │   │
│  │  LLM evaluates and returns JSON:                         │   │
│  │  {                                                       │   │
│  │    "fidelity_score": 82,                                │   │
│  │    "layout_score": 85,                                  │   │
│  │    "text_accuracy_score": 90,                           │   │
│  │    "color_match_score": 75,                             │   │
│  │    "equation_score": 70,                                │   │
│  │    "critical_errors": [                                 │   │
│  │      "Equation 3 shows 'x^2' as plain text",            │   │
│  │      "Column 2 margin is 20px too wide",                │   │
│  │      "Header should use Times New Roman"                │   │
│  │    ]                                                    │   │
│  │  }                                                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Scoring Criteria:                                              │
│  • 95-100: Nearly indistinguishable                            │
│  • 85-94: Very close, minor differences                        │
│  • 70-84: Good attempt, noticeable differences                 │
│  • 50-69: Significant discrepancies                            │
│  • <50: Major structural errors                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**JudgeFeedback Dataclass:**
```python
@dataclass
class JudgeFeedback:
    fidelity_score: int      # Overall weighted score (0-100)
    critical_errors: list    # Specific actionable errors
    layout_score: int        # Column/margin accuracy
    text_accuracy_score: int # Typography fidelity
    color_match_score: int   # Color accuracy
    equation_score: int      # Math rendering quality
    raw_response: str        # Original LLM response
```

---

#### 3.6 Dual Judge Module (`dual_judge.py`)

**Purpose:** Combine multiple judges for more robust evaluation.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DUAL JUDGE ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Strategy Layers:                                                           │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  Layer 1: CROSS-MODEL JUDGING                                         │ │
│  │                                                                        │ │
│  │  ┌─────────────────┐              ┌─────────────────┐                │ │
│  │  │  Gemini Judge   │              │  GPT-4o Judge   │                │ │
│  │  │  (Primary)      │              │  (Secondary)    │                │ │
│  │  │                 │              │                 │                │ │
│  │  │  Weight: 0.5    │              │  Weight: 0.5    │                │ │
│  │  └────────┬────────┘              └────────┬────────┘                │ │
│  │           │                                │                          │ │
│  │           └────────────────┬───────────────┘                          │ │
│  │                            ▼                                          │ │
│  │                   Weighted Average                                    │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                            │                                               │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  Layer 2: EQUATION SPECIALIST                                         │ │
│  │                                                                        │ │
│  │  Dedicated judge for mathematical content:                            │ │
│  │  • Detects ASCII art (x^2, a/b) vs proper LaTeX                      │ │
│  │  • Checks subscript/superscript rendering                             │ │
│  │  • Validates fraction display                                         │ │
│  │  • Counts equations (original vs rendered)                            │ │
│  │                                                                        │ │
│  │  ⚠️ ASCII Art Detection = Automatic FAIL (max 40 points)             │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                            │                                               │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  Layer 3: VERIFICATION GATE                                           │ │
│  │                                                                        │ │
│  │  Final sanity check when score ≥ target:                             │ │
│  │  • Quick visual comparison                                            │ │
│  │  • Checks for major issues only                                       │ │
│  │  • Returns: "accept" | "reject" | "needs_refinement"                 │ │
│  │                                                                        │ │
│  │  Lenient by design - minor imperfections accepted                    │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Score Calculation:                                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  fidelity = text * 0.50      (TEXT IS MOST IMPORTANT)                │ │
│  │           + layout * 0.30                                             │ │
│  │           + color * 0.05                                              │ │
│  │           + equation * 0.15                                           │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Consensus Detection:                                                       │
│  • Judges within 15 points = consensus                                     │
│  • Large divergence = re-evaluate                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

#### 3.7 Loop Orchestrator (`loop.py`)

**Purpose:** Coordinate the entire pipeline - the main controller.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OCRPipeline Class                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      process_pdf(pdf_path)                           │   │
│  │                                                                      │   │
│  │  Phase 0: DOCUMENT ANALYSIS (if enabled)                            │   │
│  │  ──────────────────────────────────────                              │   │
│  │  • Extract sample pages                                              │   │
│  │  • Send to Analyzer (single LLM call for all pages)                 │   │
│  │  • Generate custom prompt                                            │   │
│  │  • Save analysis to document_analysis.json                          │   │
│  │  • Save custom_prompt.md                                             │   │
│  │                                                                      │   │
│  │  Phase 1: PAGE PROCESSING                                            │   │
│  │  ──────────────────────────                                          │   │
│  │  For each page:                                                      │   │
│  │    └── process_page(ingestion, page_number)                         │   │
│  │                                                                      │   │
│  │  Phase 2: SUMMARY                                                    │   │
│  │  ───────────────────                                                 │   │
│  │  • Print results table                                               │   │
│  │  • Show success rate                                                 │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                   process_page(ingestion, page_num)                  │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │  ITERATION LOOP (max: MAX_RETRIES)                          │    │   │
│  │  │                                                              │    │   │
│  │  │  ┌────────────────────────────────────────────────────────┐ │    │   │
│  │  │  │  Step A: GENERATE                                      │ │    │   │
│  │  │  │  • If iteration 1: generate_initial()                  │ │    │   │
│  │  │  │  • If iteration N: refine(previous_html, feedback)     │ │    │   │
│  │  │  │  • Save: iteration_01.html                             │ │    │   │
│  │  │  └────────────────────────────────────────────────────────┘ │    │   │
│  │  │                         │                                   │    │   │
│  │  │  ┌────────────────────────────────────────────────────────┐ │    │   │
│  │  │  │  Step B: RENDER                                        │ │    │   │
│  │  │  │  • Open HTML in headless browser                       │ │    │   │
│  │  │  │  • Wait for MathJax                                    │ │    │   │
│  │  │  │  • Screenshot: rendered_01.png                         │ │    │   │
│  │  │  └────────────────────────────────────────────────────────┘ │    │   │
│  │  │                         │                                   │    │   │
│  │  │  ┌────────────────────────────────────────────────────────┐ │    │   │
│  │  │  │  Step C: JUDGE                                         │ │    │   │
│  │  │  │  • Compare original vs rendered                        │ │    │   │
│  │  │  │  • Return scores + errors                              │ │    │   │
│  │  │  └────────────────────────────────────────────────────────┘ │    │   │
│  │  │                         │                                   │    │   │
│  │  │  ┌────────────────────────────────────────────────────────┐ │    │   │
│  │  │  │  Step D: DECIDE                                        │ │    │   │
│  │  │  │  • If score ≥ target: BREAK ✓                         │ │    │   │
│  │  │  │  • Else: Continue to next iteration                    │ │    │   │
│  │  │  └────────────────────────────────────────────────────────┘ │    │   │
│  │  │                                                              │    │   │
│  │  └──────────────────────────────────────────────────────────────┘    │   │
│  │                                                                      │   │
│  │  Save final.html                                                     │   │
│  │  Return PageResult                                                   │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 4. Viewer Application (`viewer-next/`)

A Next.js web application for reviewing OCR results.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         VIEWER APPLICATION                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Header                                       │   │
│  │  • Project selector dropdown                                         │   │
│  │  • Zoom controls                                                     │   │
│  │  • Sync scroll toggle                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌────────────┬────────────────────────────────────────────────────────┐   │
│  │            │                                                         │   │
│  │  Sidebar   │              ComparisonView                            │   │
│  │            │                                                         │   │
│  │  • Page    │  ┌─────────────────────┬─────────────────────┐        │   │
│  │    list    │  │                     │                     │        │   │
│  │            │  │   Original PDF      │   Rendered HTML     │        │   │
│  │  • Status  │  │                     │                     │        │   │
│  │    badges  │  │   (PNG image)       │   (iframe)          │        │   │
│  │            │  │                     │                     │        │   │
│  │  • Page    │  │                     │                     │        │   │
│  │    count   │  │                     │                     │        │   │
│  │            │  │  Synced scrolling   │  Iteration selector │        │   │
│  │            │  │                     │                     │        │   │
│  │            │  └─────────────────────┴─────────────────────┘        │   │
│  │            │                                                         │   │
│  └────────────┴────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     FeedbackPanel (slide-out)                        │   │
│  │  • Status buttons: Approved | Needs Revision | Rejected            │   │
│  │  • Notes textarea                                                    │   │
│  │  • Save feedback to JSON                                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**API Routes:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/projects` | GET | List all projects in output/ |
| `/api/project/:name` | GET | Get project details + pages |
| `/api/project/:name/feedback` | GET | Get saved feedback |
| `/api/feedback` | POST | Save page feedback |
| `/api/project/:name/page/:id/original` | GET | Get original PDF image |
| `/api/project/:name/page/:id/html` | GET | Get final HTML |
| `/api/project/:name/page/:id/iteration/:n` | GET | Get specific iteration |

---

## Data Flow Diagrams

### Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           COMPLETE DATA FLOW                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  INPUT                                                                          │
│  ─────                                                                          │
│  document.pdf                                                                   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────┐                                                               │
│  │  PyMuPDF    │                                                               │
│  │  (fitz)     │                                                               │
│  └──────┬──────┘                                                               │
│         │                                                                       │
│         ├────────────────────┬─────────────────────────────────┐               │
│         ▼                    ▼                                 ▼               │
│  ┌─────────────┐      ┌─────────────┐                  ┌─────────────┐        │
│  │ page_000.png│      │ page_001.png│        ...       │ page_N.png  │        │
│  │ (300 DPI)   │      │ (300 DPI)   │                  │ (300 DPI)   │        │
│  └──────┬──────┘      └─────────────┘                  └─────────────┘        │
│         │                                                                       │
│         ├─────────────────────────────────────────────────┐                    │
│         ▼                                                 ▼                    │
│  ┌─────────────────────────────────┐        ┌─────────────────────────────┐   │
│  │         ANALYZER                │        │     GENERATOR (per page)    │   │
│  │                                 │        │                             │   │
│  │  All pages → Gemini            │        │  Page image → Gemini        │   │
│  │                                 │        │       +                     │   │
│  │  Output:                        │───────▶│  Custom prompt              │   │
│  │  • DocumentAnalysis            │        │                             │   │
│  │  • custom_prompt.md            │        │  Output: draft.html         │   │
│  │  • document_analysis.json      │        │                             │   │
│  └─────────────────────────────────┘        └───────────────┬─────────────┘   │
│                                                             │                  │
│                                                             ▼                  │
│                                              ┌─────────────────────────────┐   │
│                                              │         RENDERER            │   │
│                                              │                             │   │
│                                              │  HTML → Chromium → PNG      │   │
│                                              │                             │   │
│                                              │  Output: rendered_01.png    │   │
│                                              └───────────────┬─────────────┘   │
│                                                             │                  │
│                                                             ▼                  │
│                                              ┌─────────────────────────────┐   │
│                                              │          JUDGE              │   │
│                                              │                             │   │
│                                              │  original.png               │   │
│                                              │       vs                    │   │
│                                              │  rendered.png               │   │
│                                              │                             │   │
│                                              │  Output: JudgeFeedback      │   │
│                                              └───────────────┬─────────────┘   │
│                                                             │                  │
│                                                             ▼                  │
│                                              ┌─────────────────────────────┐   │
│                                              │        DECISION             │   │
│                                              │                             │   │
│                                              │  Score ≥ 85?                │   │
│                                              │    YES → final.html         │   │
│                                              │    NO  → Back to Generator  │   │
│                                              └─────────────────────────────┘   │
│                                                                                 │
│  OUTPUT                                                                         │
│  ──────                                                                         │
│  output/                                                                        │
│  └── document/                                                                  │
│      ├── document_analysis.json                                                 │
│      ├── custom_prompt.md                                                       │
│      ├── page_000.png                                                           │
│      ├── page_000/                                                              │
│      │   ├── iteration_01.html                                                  │
│      │   ├── rendered_01.png                                                    │
│      │   ├── iteration_02.html (if needed)                                     │
│      │   ├── rendered_02.png                                                    │
│      │   └── final.html                                                         │
│      └── page_001/                                                              │
│          └── ...                                                                │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure Reference

```
agentic_ocr/
├── config.py              # Configuration & environment loading
├── main.py                # CLI entry point (typer app)
├── requirements.txt       # Python dependencies
├── PRD.md                 # Product requirements document
├── DOCUMENTATION.md       # This file
│
├── pipeline/              # Core processing modules
│   ├── __init__.py        # Package exports
│   ├── analyzer.py        # Document pre-analysis
│   ├── ingestion.py       # PDF loading & extraction
│   ├── generator.py       # HTML generation (Gemini)
│   ├── renderer.py        # HTML → screenshot (Playwright)
│   ├── judge.py           # Single visual judge
│   ├── dual_judge.py      # Multi-judge system
│   └── loop.py            # Main orchestrator
│
├── templates/             
│   └── base.html          # HTML template with MathJax setup
│
├── output/                # Generated output (per document)
│   └── <document_name>/
│       ├── document_analysis.json
│       ├── custom_prompt.md
│       ├── page_000.png
│       ├── page_000/
│       │   ├── iteration_01.html
│       │   ├── rendered_01.png
│       │   └── final.html
│       └── ...
│
└── viewer-next/           # Next.js viewer application
    ├── package.json
    ├── src/
    │   ├── app/
    │   │   ├── page.tsx           # Main viewer page
    │   │   ├── layout.tsx         # App layout
    │   │   ├── globals.css        # Global styles
    │   │   ├── api/               # API routes
    │   │   │   ├── projects/route.ts
    │   │   │   ├── project/[name]/route.ts
    │   │   │   └── ...
    │   │   └── feedback/
    │   ├── components/
    │   │   ├── Header.tsx
    │   │   ├── Sidebar.tsx
    │   │   ├── ComparisonView.tsx
    │   │   ├── FeedbackPanel.tsx
    │   │   └── Toast.tsx
    │   ├── lib/
    │   │   └── api.ts             # API client functions
    │   └── types/
    │       └── index.ts           # TypeScript interfaces
    └── public/
```

---

## Algorithm Details

### Fidelity Score Calculation

The fidelity score is a weighted composite:

```
fidelity_score = (
    text_accuracy_score × 0.50 +    # Most important
    layout_score × 0.30 +            # Important
    equation_score × 0.15 +          # When applicable
    color_match_score × 0.05         # Least important
)
```

**Rationale:**
- Text extraction is the primary goal (50%)
- Layout preserves document structure (30%)
- Equations matter for academic documents (15%)
- Colors are aesthetic, not functional (5%)

### Dual Judge Consensus

```python
consensus = abs(gemini_score - openai_score) <= 15
```

If judges diverge by more than 15 points, the system notes the disagreement but continues with the weighted average.

### ASCII Art Detection

The equation specialist specifically checks for patterns like:
- `x^2` instead of $x^2$
- `a/b` instead of $\frac{a}{b}$
- Missing Greek letters (α, β, θ)

If detected, the equation score is capped at 40/100.

---

## API Reference

### Python API

```python
from pipeline import OCRPipeline

# Initialize pipeline
pipeline = OCRPipeline(
    max_retries=5,
    target_score=85,
    verbose=True,
    use_dual_judge=True,
    use_analyzer=True,
    language_override=None,  # "Arabic", "English", etc.
    direction_override=None, # "rtl" or "ltr"
)

# Process a PDF
results = pipeline.process_pdf("document.pdf")

# Results structure
for result in results:
    print(f"Page {result.page_number}")
    print(f"  Success: {result.success}")
    print(f"  Score: {result.final_score}/100")
    print(f"  Iterations: {result.iterations}")
    print(f"  HTML: {result.final_html_path}")
```

### REST API (Viewer)

```typescript
// List all projects
GET /api/projects
Response: [{ name, path, page_count, pages }]

// Get project details
GET /api/project/:name
Response: { name, pages: [{ number, has_final, iterations }] }

// Get original PDF image
GET /api/project/:name/page/:page/original
Response: PNG image

// Get final HTML
GET /api/project/:name/page/:page/html
Response: HTML file

// Get specific iteration
GET /api/project/:name/page/:page/iteration/:n
Response: HTML file

// Save feedback
POST /api/feedback
Body: { project, page, status, feedback, timestamp }
```

---

## Output Structure

For a document named `research_paper.pdf`:

```
output/research_paper/
├── document_analysis.json     # Analyzer output
│   {
│     "primary_language": "English",
│     "text_direction": "ltr",
│     "has_equations": true,
│     "equation_complexity": "complex",
│     "layout_type": "multi-column",
│     "column_count": 2,
│     "document_type": "academic",
│     ...
│   }
│
├── custom_prompt.md           # Generated prompt additions
│   "## Multi-Column Layout
│    This document has **2 columns**.
│    Use CSS Grid..."
│
├── page_000.png               # Original PDF page (300 DPI)
├── page_000/
│   ├── iteration_01.html      # First attempt
│   ├── rendered_01.png        # Screenshot of attempt 1
│   ├── iteration_02.html      # Refined attempt
│   ├── rendered_02.png        # Screenshot of attempt 2
│   └── final.html             # Best result (last or passed)
│
├── page_001.png
├── page_001/
│   └── ...
│
└── feedback.json              # Human review feedback (from viewer)
    {
      "0": { "status": "approved", "feedback": "", "timestamp": "..." },
      "1": { "status": "needs_revision", "feedback": "Fix equation 3", ... }
    }
```

---

## Configuration Options

### Environment Variables (.env)

```bash
# Required
GOOGLE_API_KEY=your_gemini_api_key

# Optional (for Dual Judge)
OPENAI_API_KEY=your_openai_api_key

# Judge Selection (if not using dual)
JUDGE_MODEL=gemini  # or "openai"

# Dual Judge Features
USE_DUAL_JUDGE=true
USE_CROSS_MODEL=true
USE_EQUATION_SPECIALIST=true
USE_VERIFICATION=true

# Judge Weights
GEMINI_WEIGHT=0.5
OPENAI_WEIGHT=0.5
EQUATION_WEIGHT=0.3

# Document Analyzer
USE_ANALYZER=true
```

### CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--pages`, `-p` | all | Page range to process |
| `--target`, `-t` | 85 | Target fidelity score |
| `--max-retries`, `-r` | 5 | Max iterations per page |
| `--output`, `-o` | ./output | Output directory |
| `--language`, `-l` | auto | Override language |
| `--direction`, `-d` | auto | Override text direction |
| `--verbose/--quiet` | verbose | Show progress |

---

## Success Criteria

From the PRD, the project succeeds when:

1. ✅ **Visual Fidelity**: HTML looks indistinguishable from PDF in Chrome
2. ✅ **Selectable Text**: All text is selectable and searchable
3. ✅ **Vector Math**: Equations render as MathJax (not images)
4. ✅ **Automatic Iteration**: System self-corrects based on Judge feedback
5. ✅ **Multi-language Support**: Handles RTL languages (Arabic, Hebrew)
6. ✅ **Complex Layouts**: Handles 2-column academic papers

---

## Suggested Improvements for Perfect & Reproducible Results

Based on deep analysis of the pipeline, here are prioritized improvements organized by impact:

---

### 🎯 HIGH IMPACT: Feedback Loop Enhancements

#### 1. **Positive Reinforcement in Feedback** ⭐ (User Suggested)

**Problem:** Currently, the judge only reports errors. The generator doesn't know what it did RIGHT, so it might "fix" things that were already correct.

**Solution:** Include a "what's working" section in feedback:

```python
# Current feedback format (problems only)
{
    "fidelity_score": 78,
    "critical_errors": [
        "Equation 3 is ASCII art",
        "Title font too small"
    ]
}

# IMPROVED feedback format (praise + problems)
{
    "fidelity_score": 78,
    "preserved_correctly": [  # NEW!
        "✓ Two-column layout is CORRECT - do not change",
        "✓ Footer positioning is PERFECT - keep as-is",
        "✓ Arabic RTL text direction is CORRECT",
        "✓ Color scheme matches original"
    ],
    "needs_fixing": [
        "✗ Equation 3: change 'x^2' to LaTeX \\( x^2 \\)",
        "✗ Title: increase font-size from 18px to 24px"
    ]
}
```

**Implementation:**

```python
# In dual_judge.py - Add to GENERAL_JUDGE_PROMPT
IMPROVED_JUDGE_PROMPT = """
...
## Output Format:

{
  "fidelity_score": <0-100>,
  
  "preserved_correctly": [
    "What the generator got RIGHT - be specific!",
    "These items should NOT be changed in refinement"
  ],
  
  "needs_fixing": [
    "ERROR: [description] | FIX: [specific solution]"
  ],
  
  "do_not_touch": [
    "List specific CSS selectors or HTML elements that are correct",
    "e.g., '.header { ... }' - KEEP THIS EXACTLY"
  ]
}
"""

# In generator.py - Update REFINEMENT_PROMPT_TEMPLATE
REFINEMENT_PROMPT_TEMPLATE = """
## ✅ What You Did CORRECTLY (DO NOT CHANGE THESE):
{preserved_correctly}

## ❌ What Needs Fixing:
{needs_fixing}

IMPORTANT: Only modify the items in "needs_fixing". 
Keep everything in "preserved_correctly" EXACTLY as-is.
"""
```

**Impact:** Prevents regression where fixing one thing breaks another.

---

#### 2. **Progressive/Focused Refinement**

**Problem:** Generator receives ALL errors at once and tries to fix everything, often introducing new issues.

**Solution:** Fix ONE category at a time, in priority order:

```
┌─────────────────────────────────────────────────────────────────┐
│              PROGRESSIVE REFINEMENT STRATEGY                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Iteration 1: Fix TEXT CONTENT only                            │
│  ─────────────────────────────────                              │
│  • Missing text                                                 │
│  • Wrong characters                                             │
│  • Text direction (RTL/LTR)                                     │
│  → Judge: "Ignore layout/colors, focus on text"                │
│                                                                 │
│  Iteration 2: Fix LAYOUT only                                  │
│  ─────────────────────────────                                  │
│  • Column structure                                             │
│  • Margins and spacing                                          │
│  • Element positioning                                          │
│  → Judge: "Text is locked, focus on layout"                    │
│                                                                 │
│  Iteration 3: Fix EQUATIONS only                               │
│  ─────────────────────────────────                              │
│  • LaTeX syntax                                                 │
│  • MathJax rendering                                            │
│  • Equation numbering                                           │
│                                                                 │
│  Iteration 4: Fix STYLING only                                 │
│  ─────────────────────────────────                              │
│  • Fonts and sizes                                              │
│  • Colors                                                       │
│  • Borders and backgrounds                                      │
│                                                                 │
│  Iteration 5: Final polish                                     │
│  ─────────────────────────────────                              │
│  • Any remaining issues                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
class FocusedRefinementStrategy:
    PHASES = [
        ("text", "Focus ONLY on text accuracy. Ignore layout and styling."),
        ("layout", "Focus ONLY on layout. Text content is locked."),
        ("equations", "Focus ONLY on equations. Text and layout are locked."),
        ("styling", "Focus ONLY on fonts, colors, spacing."),
        ("polish", "Final refinements. Fix any remaining issues.")
    ]
    
    def get_phase_prompt(self, iteration: int) -> str:
        phase_idx = min(iteration - 1, len(self.PHASES) - 1)
        return self.PHASES[phase_idx]
```

---

#### 3. **Diff-Based Refinement**

**Problem:** Generator rewrites entire HTML each time, risking changes to correct sections.

**Solution:** Generate PATCHES, not full replacements:

```python
# Instead of: "Here's the new HTML"
# Do: "Here are the specific changes to make"

DIFF_REFINEMENT_PROMPT = """
You are given HTML that needs specific fixes.
Do NOT rewrite the entire HTML.
Instead, output a JSON list of surgical edits:

{
  "edits": [
    {
      "selector": "h1.title",
      "property": "font-size",
      "old_value": "18px",
      "new_value": "24px"
    },
    {
      "selector": ".equation-3",
      "action": "replace_content",
      "old_content": "x^2 + y^2",
      "new_content": "\\( x^2 + y^2 \\)"
    }
  ]
}
"""

def apply_patches(html: str, patches: list[dict]) -> str:
    """Apply surgical edits to HTML without full rewrite."""
    soup = BeautifulSoup(html, 'html.parser')
    for patch in patches:
        element = soup.select_one(patch['selector'])
        if patch.get('property'):
            element['style'] = update_style(element.get('style', ''), 
                                           patch['property'], 
                                           patch['new_value'])
        elif patch.get('action') == 'replace_content':
            element.string = patch['new_content']
    return str(soup)
```

---

### 🔧 MEDIUM IMPACT: Generation Quality

#### 4. **Chain-of-Thought Document Analysis**

**Problem:** Generator jumps straight to HTML without explicit reasoning.

**Solution:** Force step-by-step analysis before code generation:

```python
CHAIN_OF_THOUGHT_PROMPT = """
Before generating HTML, analyze the document step by step:

## Step 1: Document Structure
- How many columns? Where do they start/end?
- What are the major sections?
- Are there headers/footers?

## Step 2: Typography Inventory
- List each distinct font style (title, body, captions)
- Note sizes, weights, colors for each

## Step 3: Special Elements
- Count equations and note their complexity
- Identify tables and their structure
- List all figures and their positions

## Step 4: Potential Challenges
- What might be tricky about this page?
- Are there overlapping elements?
- Any unusual layouts?

## Step 5: Implementation Plan
- What CSS approach will you use for layout?
- What font stack for each text type?
- How will you handle equations?

Now generate the HTML based on your analysis:
```html
...
```
"""
```

**Benefit:** LLM is less likely to miss elements when it explicitly catalogs them first.

---

#### 5. **Reference-Anchored Generation**

**Problem:** LLM has no ground truth text to compare against.

**Solution:** Extract text via basic OCR first, then use as reference:

```python
def extract_reference_text(page_image: Path) -> str:
    """Use pytesseract or PyMuPDF to get raw text."""
    import pytesseract
    from PIL import Image
    
    img = Image.open(page_image)
    text = pytesseract.image_to_string(img, lang='eng+ara')
    return text

# Include in generator prompt
GENERATION_PROMPT_WITH_REFERENCE = """
## Reference Text (extracted via OCR - may have errors):
```
{reference_text}
```

Use this as a GUIDE for what text should appear.
The image is the source of truth, but this helps ensure no text is missed.
"""
```

---

#### 6. **Section-by-Section Generation**

**Problem:** Generating entire page at once leads to errors in complex documents.

**Solution:** Divide and conquer:

```
┌─────────────────────────────────────────────────────────────────┐
│              SECTION-BY-SECTION GENERATION                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Original Page                    Generated Sections            │
│  ┌──────────────────┐            ┌──────────────────┐          │
│  │     HEADER       │  ──────▶   │  header.html     │          │
│  ├──────────────────┤            ├──────────────────┤          │
│  │                  │            │                  │          │
│  │  COLUMN 1 │ COL2 │  ──────▶   │  body.html       │          │
│  │           │      │            │                  │          │
│  │           │      │            │                  │          │
│  ├──────────────────┤            ├──────────────────┤          │
│  │     FOOTER       │  ──────▶   │  footer.html     │          │
│  └──────────────────┘            └──────────────────┘          │
│                                           │                     │
│                                           ▼                     │
│                                  ┌──────────────────┐          │
│                                  │  ASSEMBLED HTML  │          │
│                                  │  (combined)      │          │
│                                  └──────────────────┘          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

```python
class SectionBasedGenerator:
    def generate_page(self, page_image: str, analysis: DocumentAnalysis):
        sections = self.detect_sections(page_image)
        
        html_parts = []
        for section in sections:
            # Crop section from image
            section_image = self.crop_section(page_image, section.bbox)
            
            # Generate HTML for just this section
            section_html = self.generate_section(
                section_image, 
                section.type,  # "header", "body", "footer", etc.
                context=analysis
            )
            html_parts.append(section_html)
        
        # Combine with proper structure
        return self.assemble_page(html_parts)
```

---

#### 7. **Few-Shot Examples**

**Problem:** LLM has no examples of what "good output" looks like.

**Solution:** Include curated examples in prompts:

```python
FEW_SHOT_EXAMPLES = """
## Example 1: Two-Column Academic Paper

Input: [Image of academic paper with equations]

Output:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <style>
        .page { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .equation { margin: 1em 0; text-align: center; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
</head>
<body>
    <h1>Paper Title</h1>
    <div class="page">
        <div class="column">
            <p>First column text...</p>
            <div class="equation">\\[ E = mc^2 \\]</div>
        </div>
        <div class="column">
            <p>Second column text...</p>
        </div>
    </div>
</body>
</html>
```

## Example 2: RTL Arabic Document
...
"""
```

---

### 📊 REPRODUCIBILITY: Consistency Improvements

#### 8. **Deterministic Generation Settings**

**Problem:** Same input can produce different outputs due to LLM randomness.

**Solution:** Lock down generation parameters:

```python
# In config.py
GENERATION_CONFIG = {
    "temperature": 0.1,      # Low temperature = more deterministic
    "top_p": 0.95,
    "top_k": 40,
    "seed": 42,              # Fixed seed for reproducibility
}

# In generator.py
response = self.model.generate_content(
    [prompt, image_part],
    generation_config=genai.types.GenerationConfig(
        temperature=GENERATION_CONFIG["temperature"],
        top_p=GENERATION_CONFIG["top_p"],
        top_k=GENERATION_CONFIG["top_k"],
        # Note: seed support varies by API
    )
)
```

---

#### 9. **Caching & Checkpointing**

**Problem:** Re-running pipeline produces different results; no way to resume.

**Solution:** Cache intermediate results:

```python
class CachedPipeline:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        
    def get_or_generate(self, key: str, generator_fn: Callable) -> Any:
        cache_file = self.cache_dir / f"{key}.json"
        
        if cache_file.exists():
            return json.loads(cache_file.read_text())
        
        result = generator_fn()
        cache_file.write_text(json.dumps(result))
        return result
    
    def process_page(self, page_num: int, page_assets: PageAssets):
        # Cache document analysis
        analysis = self.get_or_generate(
            f"analysis_{page_num}",
            lambda: self.analyzer.analyze_page(page_assets.page_image_path)
        )
        
        # Cache each iteration
        for iteration in range(1, self.max_retries + 1):
            html = self.get_or_generate(
                f"page_{page_num}_iter_{iteration}_html",
                lambda: self.generator.generate(...)
            )
            # ...
```

---

#### 10. **Golden Reference Testing**

**Problem:** No way to know if changes improve or regress quality.

**Solution:** Maintain test suite with known-good outputs:

```python
class RegressionTestSuite:
    """Compare outputs against golden references."""
    
    def __init__(self, golden_dir: Path):
        self.golden_dir = golden_dir
        
    def test_page(self, pdf_name: str, page_num: int, generated_html: str):
        golden_html = (self.golden_dir / pdf_name / f"page_{page_num}.html").read_text()
        
        # Structural comparison (ignore whitespace)
        golden_tree = self.parse_html(golden_html)
        generated_tree = self.parse_html(generated_html)
        
        diff = self.compute_tree_diff(golden_tree, generated_tree)
        
        if diff.significant_changes:
            raise RegressionError(f"Output differs from golden: {diff}")
```

---

### 🎨 VISUAL QUALITY: Judge Improvements

#### 11. **Region-Based Scoring**

**Problem:** Single page score doesn't show WHERE problems are.

**Solution:** Score each region separately:

```python
REGION_SCORING_PROMPT = """
Divide the page into regions and score each:

{
  "regions": [
    {
      "name": "header",
      "bbox": [0, 0, 100, 10],  // percentage
      "score": 95,
      "issues": []
    },
    {
      "name": "column_1",
      "bbox": [0, 10, 50, 90],
      "score": 72,
      "issues": ["Equation 3 is ASCII art"]
    },
    {
      "name": "column_2",
      "bbox": [50, 10, 100, 90],
      "score": 88,
      "issues": ["Font slightly too large"]
    },
    {
      "name": "footer",
      "bbox": [0, 90, 100, 100],
      "score": 100,
      "issues": []
    }
  ],
  "overall_score": 82
}
"""
```

**Visualization:**
```
┌─────────────────────────────────────────┐
│           HEADER  [95/100] ✓            │
├───────────────────┬─────────────────────┤
│                   │                     │
│   COLUMN 1        │   COLUMN 2          │
│   [72/100] ⚠️     │   [88/100] ✓        │
│                   │                     │
│   • Eq3 ASCII     │   • Font size       │
│                   │                     │
├───────────────────┴─────────────────────┤
│           FOOTER [100/100] ✓            │
└─────────────────────────────────────────┘
```

---

#### 12. **Visual Diff Overlay**

**Problem:** Hard to see exactly where differences are.

**Solution:** Generate difference heatmap:

```python
from PIL import Image, ImageChops, ImageFilter
import numpy as np

def create_diff_overlay(original: Path, rendered: Path) -> Path:
    """Create visual diff highlighting differences."""
    
    orig_img = Image.open(original).convert('RGB')
    rend_img = Image.open(rendered).convert('RGB')
    
    # Resize to match
    rend_img = rend_img.resize(orig_img.size)
    
    # Compute difference
    diff = ImageChops.difference(orig_img, rend_img)
    
    # Enhance differences
    diff_array = np.array(diff)
    diff_magnitude = np.sqrt(np.sum(diff_array ** 2, axis=2))
    
    # Create heatmap overlay
    heatmap = np.zeros((*diff_magnitude.shape, 3), dtype=np.uint8)
    heatmap[diff_magnitude > 30] = [255, 0, 0]  # Red for differences
    
    # Blend with original
    overlay = Image.blend(orig_img, Image.fromarray(heatmap), alpha=0.3)
    
    output_path = original.parent / "diff_overlay.png"
    overlay.save(output_path)
    return output_path
```

---

#### 13. **Confidence Calibration**

**Problem:** Judge scores are arbitrary; 85 doesn't mean the same thing across documents.

**Solution:** Calibrate against human ratings:

```python
class CalibratedJudge:
    """Adjust LLM scores based on historical human feedback."""
    
    def __init__(self, calibration_data: Path):
        # Load historical LLM score → Human score mappings
        self.calibration = self.load_calibration(calibration_data)
        
    def calibrated_score(self, raw_score: int) -> int:
        """Map raw LLM score to calibrated score."""
        # Example: LLM tends to give 80 when humans rate 70
        # Apply learned correction
        return int(self.calibration.predict([[raw_score]])[0])
    
    def update_calibration(self, llm_score: int, human_score: int):
        """Learn from human feedback."""
        self.calibration.partial_fit([[llm_score]], [human_score])
```

---

### 🔍 ANALYSIS: Document Understanding

#### 14. **Font Detection & Matching**

**Problem:** LLM guesses fonts; often wrong.

**Solution:** Detect actual fonts from PDF:

```python
import fitz

def extract_fonts(pdf_path: Path) -> dict:
    """Extract font information from PDF."""
    doc = fitz.open(pdf_path)
    fonts = {}
    
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        font_name = span["font"]
                        font_size = span["size"]
                        
                        if font_name not in fonts:
                            fonts[font_name] = {
                                "sizes": set(),
                                "css_equivalent": self.map_to_css_font(font_name)
                            }
                        fonts[font_name]["sizes"].add(round(font_size))
    
    return fonts

def map_to_css_font(pdf_font: str) -> str:
    """Map PDF font names to CSS font-family."""
    mappings = {
        "Times": "'Times New Roman', Times, serif",
        "Helvetica": "Helvetica, Arial, sans-serif",
        "Courier": "'Courier New', Courier, monospace",
        "Arial": "Arial, Helvetica, sans-serif",
        "CMMI": "serif",  # Computer Modern (LaTeX)
        "CMR": "serif",
    }
    
    for key, css in mappings.items():
        if key.lower() in pdf_font.lower():
            return css
    
    return "serif"  # Default fallback
```

---

#### 15. **Color Palette Extraction**

**Problem:** LLM guesses colors; often slightly off.

**Solution:** Extract exact colors from PDF:

```python
from PIL import Image
from collections import Counter
import colorsys

def extract_color_palette(page_image: Path, n_colors: int = 10) -> list[str]:
    """Extract dominant colors from page image."""
    img = Image.open(page_image)
    img = img.convert('RGB')
    
    # Reduce to find dominant colors
    img_small = img.resize((100, 100))
    pixels = list(img_small.getdata())
    
    # Count colors, grouping similar ones
    color_counts = Counter(pixels)
    
    # Convert to hex
    palette = []
    for color, count in color_counts.most_common(n_colors):
        hex_color = '#{:02x}{:02x}{:02x}'.format(*color)
        palette.append({
            "hex": hex_color,
            "rgb": color,
            "usage": count / len(pixels),
            "likely_use": classify_color(color)  # "background", "text", "accent"
        })
    
    return palette

def classify_color(rgb: tuple) -> str:
    """Guess what a color is used for."""
    r, g, b = rgb
    brightness = (r + g + b) / 3
    
    if brightness > 240:
        return "background"
    elif brightness < 30:
        return "text"
    else:
        return "accent"
```

---

### 🚀 ARCHITECTURE: Structural Improvements

#### 16. **Ensemble Generation**

**Problem:** Single generation attempt may miss things.

**Solution:** Generate multiple candidates, pick best:

```python
class EnsembleGenerator:
    def generate_with_voting(self, page_image: str, n_candidates: int = 3):
        candidates = []
        
        # Generate multiple versions with slight prompt variations
        for i in range(n_candidates):
            html = self.generator.generate_initial(
                page_image,
                prompt_variant=i  # Slight variations
            )
            
            # Score each candidate
            rendered = self.renderer.render(html)
            feedback = self.judge.compare(page_image, rendered)
            
            candidates.append({
                "html": html,
                "score": feedback.fidelity_score,
                "feedback": feedback
            })
        
        # Return best candidate
        return max(candidates, key=lambda c: c["score"])
```

---

#### 17. **Hybrid OCR + Vision Approach**

**Problem:** Pure vision can miss or misread text.

**Solution:** Combine traditional OCR with vision LLM:

```
┌─────────────────────────────────────────────────────────────────┐
│                    HYBRID OCR ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PDF Page Image                                                 │
│       │                                                         │
│       ├─────────────────────┬───────────────────────┐          │
│       ▼                     ▼                       ▼          │
│  ┌──────────┐        ┌──────────────┐       ┌──────────────┐  │
│  │ PyMuPDF  │        │  Tesseract   │       │ Vision LLM   │  │
│  │ Text     │        │  OCR         │       │ (Gemini)     │  │
│  │ Extract  │        │              │       │              │  │
│  └────┬─────┘        └──────┬───────┘       └──────┬───────┘  │
│       │                     │                      │           │
│       └──────────────┬──────┴──────────────────────┘           │
│                      ▼                                          │
│              ┌───────────────┐                                  │
│              │   RECONCILE   │                                  │
│              │               │                                  │
│              │ • Cross-check │                                  │
│              │ • Fill gaps   │                                  │
│              │ • Fix errors  │                                  │
│              └───────────────┘                                  │
│                      │                                          │
│                      ▼                                          │
│              ┌───────────────┐                                  │
│              │  FINAL HTML   │                                  │
│              │  (verified)   │                                  │
│              └───────────────┘                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

#### 18. **Semantic Validation Layer**

**Problem:** HTML might look right but have wrong content.

**Solution:** Validate text content independently:

```python
class SemanticValidator:
    """Verify generated text matches original."""
    
    def validate(self, original_image: Path, generated_html: str) -> ValidationResult:
        # Extract text from generated HTML
        soup = BeautifulSoup(generated_html, 'html.parser')
        html_text = soup.get_text(separator=' ', strip=True)
        
        # Extract text from original via OCR
        original_text = pytesseract.image_to_string(Image.open(original_image))
        
        # Compare using fuzzy matching
        similarity = fuzz.ratio(html_text, original_text)
        
        # Find missing phrases
        original_words = set(original_text.split())
        html_words = set(html_text.split())
        missing = original_words - html_words
        extra = html_words - original_words
        
        return ValidationResult(
            similarity=similarity,
            missing_words=missing,
            extra_words=extra,
            passed=similarity > 90 and len(missing) < 5
        )
```nv

---

### 📋 SUMMARY: Implementation Priority

| Priority | Improvement | Impact | Effort |
|----------|------------|--------|--------|
| 🔴 P0 | Positive reinforcement in feedback | High | Low |
| 🔴 P0 | Diff-based refinement (patches) | High | Medium |
| 🟠 P1 | Progressive/focused refinement | High | Medium |
| 🟠 P1 | Region-based scoring | Medium | Medium |
| 🟠 P1 | Reference text extraction (OCR) | Medium | Low |
| 🟡 P2 | Chain-of-thought analysis | Medium | Low |
| 🟡 P2 | Deterministic generation settings | Medium | Low |
| 🟡 P2 | Font detection from PDF | Medium | Medium |
| 🟢 P3 | Section-by-section generation | Medium | High |
| 🟢 P3 | Ensemble generation | Medium | High |
| 🟢 P3 | Visual diff overlay | Low | Medium |
| 🟢 P3 | Semantic validation | Medium | Medium |

---

### Quick Win: Implementing Positive Reinforcement

Here's a minimal implementation you could add today:

```python
# In dual_judge.py, update GENERAL_JUDGE_PROMPT:

GENERAL_JUDGE_PROMPT = """
...

## Output Format:

{
  "fidelity_score": <0-100>,
  
  "correct_elements": [
    "Describe what the generator got RIGHT",
    "Be specific: 'Two-column grid layout is correct'",
    "These will be marked as DO NOT CHANGE"
  ],
  
  "critical_errors": [
    "ERROR: [description] | FIX: [specific solution] | KEEP: [what not to change]"
  ]
}
"""

# In generator.py, update REFINEMENT_PROMPT_TEMPLATE:

REFINEMENT_PROMPT_TEMPLATE = """
## ✅ CORRECT - DO NOT MODIFY:
{correct_elements}

## ❌ FIX THESE ONLY:
{critical_errors}

CRITICAL INSTRUCTION:
- Only change what's listed under "FIX THESE ONLY"
- Everything under "CORRECT" must remain EXACTLY as-is
- If you're unsure, leave it unchanged
"""
```

This single change could significantly improve convergence and reduce regressions!

---

*These improvements are based on analysis of the current pipeline architecture and common failure modes in LLM-based document processing systems.*
