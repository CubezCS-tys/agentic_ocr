# Staged OCR Pipeline - Product Requirements Document

## Overview

This document outlines an experimental approach to OCR processing that separates concerns into discrete, focused stages. Each stage has a single responsibility, with the final assembly performed by deterministic Python code rather than an LLM.

## Problem Statement

The current unified approach asks the LLM to:
1. Understand the layout
2. Extract all text
3. Format equations in LaTeX
4. Generate correct HTML structure
5. Apply proper RTL/LTR handling
6. Style everything correctly

This creates several issues:
- **Inconsistency**: The LLM may handle similar layouts differently across pages
- **Debugging difficulty**: When output is wrong, it's unclear which aspect failed
- **All-or-nothing**: A small text error requires regenerating the entire page
- **Prompt complexity**: Long, complex prompts are harder for LLMs to follow reliably

## Proposed Solution

### Core Principle: One Job Per LLM Call

Split the OCR process into focused stages where each LLM call does exactly ONE thing:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   IMAGE     │────▶│   LAYOUT    │────▶│    TEXT     │────▶│  ASSEMBLY   │
│             │     │  EXTRACTOR  │     │  EXTRACTOR  │     │  (Python)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                          │                   │                    │
                          ▼                   ▼                    ▼
                    HTML Skeleton       JSON Content          Final HTML
                    with data-refs      per reference
```

---

## Stage 1: Layout Extraction

### Purpose
Analyze the visual structure of the page and produce an HTML skeleton with semantic placeholders.

### Input
- Page image

### Output
An HTML structure with `data-ref` attributes marking content locations:

```html
<div class="page" dir="rtl" lang="ar">
  <header class="page-header">
    <div class="title" data-ref="title_1" data-type="text"></div>
    <div class="author" data-ref="author_1" data-type="text"></div>
  </header>
  
  <main class="two-column-layout">
    <div class="column column-right" data-ref="col_right_1" data-type="text"></div>
    <div class="column column-left" data-ref="col_left_1" data-type="text"></div>
  </main>
  
  <div class="equation-block" data-ref="eq_1" data-type="math"></div>
  
  <div class="paragraph" data-ref="para_1" data-type="text"></div>
  
  <footer class="footnotes">
    <div class="footnote" data-ref="footnote_1" data-type="text"></div>
  </footer>
</div>
```

### Key Attributes
- `data-ref`: Unique identifier for content injection (e.g., `col_right_1`, `eq_3`)
- `data-type`: Content type hint (`text`, `math`, `table`, `figure`)
- `data-reading-order`: Optional numeric order for text flow

### What This Stage Does NOT Do
- Extract actual text content
- Convert equations to LaTeX
- Make styling decisions beyond semantic classes

### Naming Convention for References
| Element Type | Pattern | Example |
|--------------|---------|---------|
| Title | `title_N` | `title_1` |
| Column | `col_{position}_N` | `col_right_1`, `col_left_2` |
| Paragraph | `para_N` | `para_1` |
| Equation (display) | `eq_N` | `eq_1` |
| Inline equation | `inline_eq_N` | `inline_eq_1` |
| Footnote | `footnote_N` | `footnote_1` |
| Table | `table_N` | `table_1` |
| Figure | `figure_N` | `figure_1` |
| Caption | `caption_N` | `caption_1` |
| Header | `header_N` | `header_1` |
| Page number | `page_num` | `page_num` |

---

## Stage 2: Text Extraction

### Purpose
Extract the actual content for each reference identified in the layout.

### Input
- Page image (same as Stage 1)
- List of references from the layout skeleton (e.g., `["title_1", "col_right_1", "eq_1", ...]`)

### Output
A JSON mapping of references to their content:

```json
{
  "title_1": {
    "type": "text",
    "content": "المعادلات التفاضلية الجزئية",
    "direction": "rtl",
    "language": "ar"
  },
  "col_right_1": {
    "type": "text", 
    "content": "في هذا الفصل نناقش المعادلات التفاضلية...",
    "direction": "rtl",
    "language": "ar"
  },
  "col_left_1": {
    "type": "text",
    "content": "ويمكن تصنيف هذه المعادلات إلى عدة أنواع...",
    "direction": "rtl",
    "language": "ar"
  },
  "eq_1": {
    "type": "math",
    "content": "\\frac{\\partial^2 u}{\\partial x^2} + \\frac{\\partial^2 u}{\\partial y^2} = 0",
    "format": "latex",
    "display": "block"
  },
  "footnote_1": {
    "type": "text",
    "content": "١- انظر المرجع السابق، ص ٤٥",
    "direction": "rtl",
    "language": "ar"
  }
}
```

### Content Types

#### Text
```json
{
  "type": "text",
  "content": "The actual text content...",
  "direction": "rtl|ltr|auto",
  "language": "ar|en|mixed"
}
```

#### Math (Display/Block)
```json
{
  "type": "math",
  "content": "\\LaTeX content here",
  "format": "latex",
  "display": "block"
}
```

#### Math (Inline)
For inline equations within text, use a special marker:
```json
{
  "type": "text",
  "content": "Consider the function {{inline_eq_1}} where x > 0",
  "direction": "ltr",
  "language": "en",
  "inline_refs": {
    "inline_eq_1": "f(x) = x^2"
  }
}
```

#### Table
```json
{
  "type": "table",
  "content": {
    "headers": ["العمود ١", "العمود ٢"],
    "rows": [
      ["القيمة ١", "القيمة ٢"],
      ["القيمة ٣", "القيمة ٤"]
    ]
  },
  "direction": "rtl"
}
```

### What This Stage Does NOT Do
- Make layout decisions
- Generate HTML structure
- Apply CSS styling

---

## Stage 3: Assembly (Pure Python)

### Purpose
Merge the layout skeleton with extracted content to produce the final HTML.

### Input
- HTML skeleton from Stage 1
- JSON content from Stage 2
- Base HTML template with styles

### Output
Complete, styled HTML page ready for viewing.

### Assembly Logic (Pseudocode)

```python
def assemble(skeleton_html: str, content: dict, template: str) -> str:
    soup = BeautifulSoup(skeleton_html, 'html.parser')
    
    for element in soup.find_all(attrs={"data-ref": True}):
        ref = element["data-ref"]
        data = content.get(ref, {})
        
        if data["type"] == "text":
            element.string = data["content"]
            if data.get("direction"):
                element["dir"] = data["direction"]
                
        elif data["type"] == "math":
            # Wrap in KaTeX-compatible span
            if data["display"] == "block":
                element.string = f"$${data['content']}$$"
            else:
                element.string = f"${data['content']}$"
                
        elif data["type"] == "table":
            table_html = render_table(data["content"])
            element.replace_with(BeautifulSoup(table_html, 'html.parser'))
        
        # Remove data attributes from final output
        del element["data-ref"]
        del element["data-type"]
    
    return inject_into_template(str(soup), template)
```

### Advantages of Python Assembly
1. **100% Deterministic**: Same inputs always produce same output
2. **Debuggable**: Can step through with a debugger
3. **Testable**: Unit tests can verify assembly logic
4. **Fast**: No LLM latency for this step
5. **Customizable**: Easy to add post-processing rules

---

## Stage 4 (Optional): Validation/Judge

### Purpose
Validate the final assembled output against the original image.

### Input
- Original page image
- Final assembled HTML (rendered as image or raw HTML)

### Output
- Validation score
- List of issues found
- Suggested corrections (if any)

This stage can use the existing judge infrastructure.

---

## File Structure

```
staged_pipeline/
├── PRD.md                    # This document
├── __init__.py
├── layout_extractor.py       # Stage 1: Layout analysis
├── text_extractor.py         # Stage 2: Content extraction  
├── assembler.py              # Stage 3: Pure Python assembly
├── runner.py                 # Orchestrates the full pipeline
├── prompts/
│   ├── layout_prompt.md      # Prompt for layout extraction
│   └── text_prompt.md        # Prompt for text extraction
├── templates/
│   └── base.html             # HTML template for final output
└── output/                   # Pipeline outputs
```

---

## Prompts

### Layout Extraction Prompt (Summary)

```markdown
You are a document layout analyzer. Your ONLY job is to identify the visual 
structure of this document page.

OUTPUT: An HTML skeleton with data-ref placeholders. Do NOT extract any text.

Rules:
1. Use semantic HTML elements (header, main, footer, etc.)
2. Mark each content area with data-ref="unique_id" and data-type="text|math|table"
3. Use the naming convention: col_right_1, eq_1, footnote_1, etc.
4. Set dir="rtl" for Arabic documents, dir="ltr" for English
5. For multi-column layouts, use column-right/column-left classes
6. Preserve reading order with data-reading-order if needed

Do NOT include:
- Actual text content
- LaTeX equations
- Styling beyond semantic classes
```

### Text Extraction Prompt (Summary)

```markdown
You are a text extraction specialist. Given an image and a list of reference 
IDs, extract the content for each reference.

INPUT: Image + List of references ["title_1", "col_right_1", "eq_1", ...]

OUTPUT: JSON mapping each reference to its content.

Rules:
1. For text: Extract exactly as written, preserve all diacritics
2. For math: Convert to LaTeX format
3. For tables: Extract as structured JSON
4. Mark language and direction for each text block
5. For inline equations within text, use {{ref_id}} markers

Do NOT include:
- HTML structure
- CSS styling
- Layout decisions
```

---

## Comparison: Current vs Staged Pipeline

| Aspect | Current Approach | Staged Pipeline |
|--------|-----------------|-----------------|
| LLM Calls per page | 1 (complex) | 2 (simple each) |
| Prompt complexity | High | Low per stage |
| Output consistency | Variable | More consistent |
| Debugging | Difficult | Easy (stage-by-stage) |
| Partial retry | Full regeneration | Retry specific stage |
| Assembly | LLM-generated | Deterministic code |
| Customization | Prompt changes | Code + prompts |

---

## Success Criteria

1. **Layout accuracy**: Skeleton correctly identifies all structural elements
2. **Text accuracy**: Extracted content matches original exactly
3. **Assembly correctness**: Final HTML renders identically to current approach
4. **Consistency**: Same document processed multiple times yields same structure
5. **Performance**: Total time comparable to current approach (2 LLM calls vs 1)

---

## Experiment Plan

### Phase 1: Basic Implementation
1. Implement layout extractor with simple documents
2. Implement text extractor 
3. Build Python assembler
4. Test on single-column Arabic pages

### Phase 2: Complex Layouts
1. Two-column layouts
2. Mixed RTL/LTR content
3. Complex equations
4. Tables

### Phase 3: Comparison
1. Process same documents with both pipelines
2. Compare output quality
3. Compare consistency across runs
4. Measure performance

### Phase 4: Refinement
1. Tune prompts based on findings
2. Add validation stage if needed
3. Handle edge cases

---

## Design Decisions

### 1. Should equations be a separate stage?

**Analysis of Options:**

| Option | Pros | Cons |
|--------|------|------|
| **A: Combined with text** | Fewer LLM calls, lower latency | Math extraction mixed with text, may reduce quality |
| **B: Separate equation stage** | Focused math extraction, better LaTeX quality | 3 LLM calls per page, higher latency/cost |
| **C: Hybrid - extract with text, validate separately** | Best of both, allows targeted retry | More complex orchestration |

**Decision: Option C - Hybrid Approach**

Equations will be extracted in Stage 2 (text extraction) BUT:
- Layout stage marks equation locations with `data-type="math"` and `data-complexity="simple|complex"`
- Text extractor handles simple inline equations directly
- A lightweight **Stage 2.5 (optional)** can be triggered for complex equations only
- This minimizes LLM calls while allowing focused retry for tricky math

**Rationale:** Most equations are straightforward. Only complex multi-line equations or matrices need special attention. This way we get 2 calls for simple pages, 3 only when needed.

---

### 2. How to handle inline equations?

**Analysis of Options:**

| Option | Pros | Cons |
|--------|------|------|
| **A: Markers in text `{{eq_id}}`** | Clean separation, easy to assemble | Requires tracking positions, more complex extraction |
| **B: Inline LaTeX directly in text** | Simple extraction, natural flow | Harder to validate/retry just the equation |
| **C: Segment-based extraction** | Each text block is array of segments | Most flexible, but complex JSON structure |

**Decision: Option C - Segment-based extraction**

Each text block will be an array of segments, each with a type:

```json
{
  "col_right_1": {
    "type": "mixed",
    "direction": "rtl",
    "language": "ar",
    "segments": [
      {"type": "text", "content": "نعتبر الدالة "},
      {"type": "math", "content": "f(x) = x^2", "display": "inline"},
      {"type": "text", "content": " حيث "},
      {"type": "math", "content": "x > 0", "display": "inline"},
      {"type": "text", "content": " وهي دالة متصلة."}
    ]
  }
}
```

**Rationale:** This preserves the exact position and context of inline equations, makes assembly straightforward, and allows for targeted equation validation. The assembler simply iterates through segments and wraps math in `$...$`.

For pure text blocks (no equations), a simplified format is allowed:
```json
{
  "para_1": {
    "type": "text",
    "content": "هذه فقرة نصية بدون معادلات.",
    "direction": "rtl",
    "language": "ar"
  }
}
```

---

### 3. What about figures/images?

**Analysis of Options:**

| Option | Pros | Cons |
|--------|------|------|
| **A: Ignore figures entirely** | Simple, focused on text/math | Incomplete reproduction |
| **B: Extract captions only** | Captures important text, simple | Loses figure positioning |
| **C: Placeholder with metadata** | Preserves layout, captures captions | Need to handle figure display later |

**Decision: Option C - Placeholder with metadata**

Layout stage will create placeholders:
```html
<figure class="figure-block" data-ref="figure_1" data-type="figure">
  <div class="figure-placeholder" data-original-position="center"></div>
  <figcaption data-ref="caption_1" data-type="text"></figcaption>
</figure>
```

Text extraction outputs:
```json
{
  "figure_1": {
    "type": "figure",
    "description": "Graph showing relationship between x and y variables",
    "position": {"x": "center", "width": "80%"}
  },
  "caption_1": {
    "type": "text",
    "content": "الشكل ١: العلاقة بين المتغيرين",
    "direction": "rtl"
  }
}
```

**Rationale:** This preserves the document structure and captures caption text. Figure images can be handled in a future enhancement (cropping from original, re-embedding, etc.).

---

### 4. Reading order for complex layouts?

**Analysis of Options:**

| Option | Pros | Cons |
|--------|------|------|
| **A: Implicit via DOM order** | Simple, natural HTML flow | May not match visual reading order |
| **B: `data-reading-order` attribute** | Explicit control | Extra complexity in layout stage |
| **C: Separate reading order map** | Flexible, can reorder without changing structure | Extra data structure to maintain |

**Decision: Option B - Explicit `data-reading-order` attribute**

Layout stage will include reading order for all content elements:

```html
<div class="two-column-layout">
  <div class="column-right" data-ref="col_right_1" data-type="text" data-reading-order="1"></div>
  <div class="column-left" data-ref="col_left_1" data-type="text" data-reading-order="2"></div>
</div>
<div class="equation-block" data-ref="eq_1" data-type="math" data-reading-order="3"></div>
```

For RTL Arabic documents with two columns:
- Right column typically reads first (order=1)
- Left column reads second (order=2)
- Content below both columns follows (order=3, 4, ...)

**Rationale:** This gives explicit control over reading flow, essential for accessibility and text-to-speech. The text extractor can use this order to understand context flow.

---

### 5. Additional Decision: Error Handling Strategy

**Decision: Graceful degradation with fallback markers**

If text extraction fails for a reference:
```json
{
  "col_right_1": {
    "type": "error",
    "error": "Could not extract text - image quality too low",
    "fallback": "[EXTRACTION_FAILED: col_right_1]"
  }
}
```

Assembler will insert a visible marker that can be manually corrected:
```html
<div class="column-right extraction-error">
  <span class="error-marker">[EXTRACTION_FAILED: col_right_1]</span>
</div>
```

---

### 6. Additional Decision: Validation Hooks

Each stage will output a confidence indicator:

**Layout stage:**
```json
{
  "skeleton": "<html>...</html>",
  "confidence": 0.95,
  "warnings": ["Detected possible table, marked as generic content block"]
}
```

**Text stage:**
```json
{
  "content": {...},
  "confidence": 0.87,
  "low_confidence_refs": ["eq_3", "footnote_2"],
  "warnings": ["eq_3: Complex nested fractions, verify LaTeX"]
}
```

This allows the runner to decide if validation/retry is needed.

---

## Final Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              STAGED PIPELINE                                 │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌──────────┐
     │  IMAGE   │
     └────┬─────┘
          │
          ▼
┌─────────────────────┐
│  STAGE 1: LAYOUT    │  LLM Call #1
│  ─────────────────  │
│  Input: Image       │
│  Output: HTML       │
│  skeleton with      │
│  data-ref markers   │
└─────────┬───────────┘
          │
          │ Extracts list of refs:
          │ ["title_1", "col_right_1", "eq_1", ...]
          │
          ▼
┌─────────────────────┐
│  STAGE 2: TEXT      │  LLM Call #2
│  ─────────────────  │
│  Input: Image +     │
│  Reference list     │
│  Output: JSON       │
│  content mapping    │
└─────────┬───────────┘
          │
          │ Check confidence scores
          │
          ▼
    ┌─────────────┐
    │ Low         │──────────────────────┐
    │ confidence  │                      │
    │ equations?  │                      ▼
    └──────┬──────┘            ┌─────────────────────┐
           │ No                │  STAGE 2.5: MATH    │  LLM Call #3 (optional)
           │                   │  ─────────────────  │
           │                   │  Input: Image +     │
           │                   │  Specific eq refs   │
           │                   │  Output: Refined    │
           │                   │  LaTeX for flagged  │
           │                   │  equations          │
           │                   └─────────┬───────────┘
           │                             │
           │◀────────────────────────────┘
           │
           ▼
┌─────────────────────┐
│  STAGE 3: ASSEMBLY  │  Pure Python (No LLM)
│  ─────────────────  │
│  Input: Skeleton +  │
│  Content JSON +     │
│  Template           │
│  Output: Final HTML │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  STAGE 4: VALIDATE  │  LLM Call (optional)
│  ─────────────────  │
│  Input: Image +     │
│  Rendered HTML      │
│  Output: Score +    │
│  Issues list        │
└─────────┬───────────┘
          │
          ▼
     ┌──────────┐
     │  FINAL   │
     │  OUTPUT  │
     └──────────┘
```

---

## Updated Content Schema

### Text Block (Simple)
```json
{
  "type": "text",
  "content": "النص الكامل هنا",
  "direction": "rtl",
  "language": "ar"
}
```

### Text Block with Inline Math (Segmented)
```json
{
  "type": "mixed",
  "direction": "rtl",
  "language": "ar",
  "segments": [
    {"type": "text", "content": "نعتبر "},
    {"type": "math", "content": "f(x)", "display": "inline"},
    {"type": "text", "content": " دالة متصلة"}
  ]
}
```

### Display Equation
```json
{
  "type": "math",
  "content": "\\int_0^\\infty e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}",
  "display": "block",
  "equation_number": "1"
}
```

### Table
```json
{
  "type": "table",
  "direction": "rtl",
  "headers": ["العمود ١", "العمود ٢", "العمود ٣"],
  "rows": [
    ["قيمة", "قيمة", "قيمة"],
    ["قيمة", "قيمة", "قيمة"]
  ],
  "caption": "جدول ١: وصف الجدول"
}
```

### Figure
```json
{
  "type": "figure",
  "description": "Description of what the figure shows",
  "position": "center",
  "width": "80%"
}
```

### Error/Fallback
```json
{
  "type": "error",
  "error": "Extraction failed: [reason]",
  "fallback": "[FAILED: ref_id]"
}
```

---

## Next Steps

1. ✅ Create PRD (this document)
2. ✅ Implement `layout_extractor.py`
3. ✅ Implement `text_extractor.py`
4. ✅ Implement `assembler.py`
5. ✅ Implement `runner.py`
6. ⬜ Test on sample documents
7. ⬜ Compare with existing pipeline
8. ⬜ Iterate and refine

---

## Implementation Complete

The staged pipeline has been implemented with the following structure:

```
staged_pipeline/
├── PRD.md                           # This document
├── __init__.py                      # Package exports
├── layout_extractor.py              # Stage 1: Layout analysis
├── text_extractor.py                # Stage 2 + 2.5: Text & math extraction
├── assembler.py                     # Stage 3: Pure Python assembly
├── runner.py                        # Orchestrates the full pipeline
├── run_staged.py                    # Quick test script
└── prompts/
    ├── layout_prompt.md             # Prompt for layout extraction
    ├── text_prompt.md               # Prompt for text extraction
    └── math_refinement_prompt.md    # Prompt for equation refinement
```

### Usage

```bash
# From project root with venv activated
cd /home/yassine/agentic_ocr
source venv/bin/activate

# Process a PDF (first page)
python staged_pipeline/run_staged.py path/to/document.pdf

# Process specific pages
python -m staged_pipeline.runner path/to/document.pdf --pages 0,1,2

# Process an image
python staged_pipeline/run_staged.py path/to/page.png
```

### Output Files

For each page processed, the pipeline saves:
- `skeleton.html` - The layout structure from Stage 1
- `content.json` - Extracted content from Stage 2
- `references.json` - List of all content references
- `final.html` - The assembled final output
- `summary.json` - Pipeline execution summary
