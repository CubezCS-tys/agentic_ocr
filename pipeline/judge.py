"""
Visual Judge Module
Compares original PDF page with rendered HTML using Vision LLM.
"""

import json
import base64
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import google.generativeai as genai

from config import (
    GOOGLE_API_KEY, 
    OPENAI_API_KEY,
    JUDGE_MODEL,
    GEMINI_JUDGE_MODEL,
    OPENAI_JUDGE_MODEL,
)


# Configure Gemini API
genai.configure(api_key=GOOGLE_API_KEY)


@dataclass
class JudgeFeedback:
    """Structured feedback from the visual judge."""
    fidelity_score: int
    critical_errors: list[str]
    correct_elements: list[str]  # What the generator did correctly (positive reinforcement)
    layout_score: int
    text_accuracy_score: int
    color_match_score: int
    equation_score: int
    raw_response: str
    
    @property
    def passed(self) -> bool:
        """Check if the fidelity score meets the target."""
        from config import TARGET_SCORE
        return self.fidelity_score >= TARGET_SCORE
    
    def to_dict(self) -> dict:
        """Convert to dictionary for the generator."""
        return {
            "fidelity_score": self.fidelity_score,
            "critical_errors": self.critical_errors,
            "correct_elements": self.correct_elements,
            "layout_score": self.layout_score,
            "text_accuracy_score": self.text_accuracy_score,
            "color_match_score": self.color_match_score,
            "equation_score": self.equation_score,
        }


JUDGE_PROMPT = """You are an EXTREMELY CRITICAL QA Visual Engineer specializing in document fidelity assessment. Your standards are exceptionally high - you reject anything less than near-perfect reproduction. Compare these two images:

1. **Original**: A PDF page rendered as an image (the ground truth)
2. **Rendered**: An HTML page rendered as an image (the attempt to recreate the PDF)

**YOUR ROLE**: Be HARSH and UNFORGIVING. Nitpick every detail. Only award high scores for truly exceptional work.

## Detailed Evaluation Criteria:

### 1. Layout Score (0-100) - CRITICAL - BE MERCILESS
Evaluate the structural accuracy with ZERO TOLERANCE for errors:
- **Column Structure**: Does the HTML match the number of columns? Are column widths proportional? Even 5% difference is unacceptable.
- **COLUMN ORDERING (CRITICAL)**: Are columns in the correct order? For LTR documents, left-to-right. For RTL documents, right-to-left. Content must flow naturally. ANY column flip = automatic failure.
- **Content Placement**: Is text in the correct column? Check that content hasn't been flipped or swapped between columns. Zero tolerance.
- **TEXT BLOCK POSITIONING (CRITICAL)**: Are paragraphs, headings, and text blocks positioned EXACTLY where they appear in the original? Shifts of more than 5px are UNACCEPTABLE.
- **LINE BREAKS (CRITICAL)**: Do lines of text break at the SAME words as the original? Text must wrap identically - not just similar.
- **PARAGRAPH BOUNDARIES (CRITICAL)**: Are paragraph breaks in the exact same locations? Check spacing between paragraphs - must be within 3px.
- **VERTICAL SPACING (CRITICAL)**: Is the spacing between sections, paragraphs, and elements accurate? Text should not be compressed or stretched even slightly.
- **Margins & Padding**: Are page margins, section spacing, and paragraph gaps correct? Within 5px tolerance only.
- **Header/Footer**: Are page numbers, running headers positioned correctly? Exact positioning required.
- **Element Positioning**: Are all elements (text blocks, figures, tables) in the right location? No exceptions.
- **Aspect Ratio**: Does the overall page shape and proportion match? Must be identical.
- **Whitespace**: Is the whitespace distribution similar (not too cramped or too spread out)? Match within 10%.

**HARSH PENALTY**: If text appears in wrong positions (>5px), columns are flipped, or line breaks don't match → MAXIMUM 35/100 on layout score.

### 2. Text Accuracy Score (0-100) - CRITICAL - BE STRICT
Evaluate typography fidelity with PIXEL-LEVEL PRECISION - NO COMPROMISES:
- **Font Family**: Does it use the correct font type (serif like Times for academic papers vs sans-serif)? Arabic text MUST use proper Arabic fonts. Wrong font family = major penalty.
- **Font Size Hierarchy**: Is the title largest, then section headers, then body text? Sizes must be PROPORTIONALLY PERFECT - not just close.
- **Font Weight**: Are bold elements (titles, headers, keywords) correctly bolded? Half-bold or missing bold = penalty.
- **Line Spacing**: Does line height match the original? Text should not appear compressed or stretched vertically at all.
- **Text Alignment**: Is justified/left/right/center alignment preserved? For RTL, text MUST be right-aligned. Wrong alignment = major failure.
- **TEXT WRAPPING (CRITICAL)**: Do lines break at approximately the same points? Words should wrap at identical locations - not just similar.
- **Character Spacing**: Is letter-spacing and word-spacing similar to the original? Must look identical.
- **TEXT DENSITY**: Is the text density (characters per line, lines per paragraph) comparable to the original?
- **Special Styling**: Are italics, underlines, small caps preserved where used?

**HARSH PENALTY**: If text layout doesn't match original positioning → MAXIMUM 45/100 on text accuracy score. If fonts are completely wrong type (serif vs sans-serif) → MAX 55/100.

### 3. Color Match Score (0-100) - BE CRITICAL
Evaluate color accuracy - colors must be nearly identical:
- **Background Colors**: Are shaded boxes, theorem backgrounds, code blocks the right color? Must match within 10% color variance.
- **Text Colors**: Is the text color correct (usually black, but check for colored elements)? Black must be true black, not gray.
- **Border/Line Colors**: Are dividers, table borders, box outlines the right color? Must match closely.
- **Accent Colors**: Are any highlighted or colored sections matched? Highlight colors must be accurate.
- **Color Consistency**: Are color choices consistent throughout? No random color changes allowed.

### 4. Equation Score (0-100) - CRITICAL - ZERO TOLERANCE
This is one of the most important criteria - be EXTREMELY harsh:
- **Rendering Method**: Are equations rendered as proper mathematical notation (MathJax/LaTeX)? Anything else is unacceptable.
- **ASCII Art Detection**: SEVERE PENALTY if equations appear as plain text like "x^2" or "a/b" instead of proper rendered math. This is a critical failure.
- **Subscripts/Superscripts**: Are they properly positioned (small, raised/lowered)? Must be perfect, not just close.
- **Fractions**: Are fractions displayed with horizontal bar, not as "a/b"? Plain text fractions = major failure.
- **Greek Letters**: Are α, β, θ, etc. rendered correctly? Must use actual Greek symbols, not Latin approximations.
- **Operators**: Are summation (Σ), integral (∫), product (Π) symbols correct? Must be proper math symbols.
- **Matrices/Arrays**: Are matrix brackets and alignment correct? Structure must be exact.
- **Equation Numbering**: Are equation numbers (1), (2), etc. present and positioned? Must match original.
- **ANY plain text equation = automatic score below 40/100 for equation score**

### 5. Table Score (0-100) - BE STRICT
If tables are present - tables must be structurally perfect:
- **Structure**: Correct number of rows and columns? Must be exact, no missing/extra rows.
- **CONTENT ORDERING (CRITICAL)**: Are table cells in the correct order? Check for flipped rows or columns. Verify header row is at top, data flows correctly. Any swap = major penalty.
- **Cell Content**: Is the data in each cell correct and not swapped with adjacent cells? Zero tolerance for swaps.
- **Borders**: Are border styles (solid, none, partial) matched? Must look identical.
- **Cell Alignment**: Is content aligned correctly within cells? Must match original alignment.
- **Header Styling**: Are header rows distinguished (bold, shaded)? Styling must be accurate.
- **Cell Spacing**: Is padding and spacing within cells correct? Must look identical.

### 6. Figure Score (0-100) - BE THOROUGH
If figures/images are present - must be handled properly:
- **Presence**: Are all figures included? Missing figures = severe penalty.
- **Position**: Are they in the correct location? Within 10px tolerance only.
- **Size**: Are dimensions proportional to the original? Must match within 10%.
- **Captions**: Are figure captions present with correct styling? Must be accurate.

### 7. List Score (0-100)
If lists are present:
- **Numbering Style**: Does (1), 1., i., a. match the original?
- **Indentation**: Are nested levels properly indented?
- **Alignment**: Do list items align correctly with numbers/bullets?

## Scoring Guidelines (EXTREMELY STRICT - BE HARSH):
- **95-100**: ABSOLUTELY PERFECT - pixel-perfect match in every dimension, completely indistinguishable from original. Reserved for exceptional cases only.
- **90-94**: Near perfect with only microscopic differences (1-2px font size variation, tiny spacing differences under 5px)
- **80-89**: Very good but has minor noticeable issues (slight font mismatches, small spacing inconsistencies, minor positioning shifts)
- **65-79**: Decent attempt with clear problems (text positioning noticeably off, wrong line breaks, spacing issues)
- **50-64**: Major structural issues (columns flipped, significant spacing problems, wrong text positions, missing styling)
- **Below 50**: Severe failures (content missing, completely wrong layout, unreadable, critical errors)

**CRITICAL REQUIREMENTS FOR 90+ SCORE (BE UNFORGIVING):**
- Text must be positioned EXACTLY where it appears in original (zero tolerance for shifts)
- Line breaks must match PRECISELY - same words breaking at same positions
- Column ordering must be PERFECT (no flipped columns, correct reading flow)
- Paragraph spacing must be ACCURATE within 2-3px
- Font sizes must be PROPORTIONALLY PERFECT (not just close)
- Font families must MATCH the original style exactly
- Equations must render with PROPER LaTeX formatting (no plain text allowed)
- Colors must MATCH closely (no significant color differences)
- Tables/lists must have EXACT structure and ordering

## Critical Error Detection:
List specific, actionable errors. Be VERY specific:

❌ BAD: "Fonts are wrong"
✅ GOOD: "The main title uses Arial (sans-serif) but should use Times New Roman (serif)"

❌ BAD: "Equations broken"
✅ GOOD: "Equation 3 shows 'x^2 + y^2' as plain text instead of proper LaTeX rendering with superscripts"

❌ BAD: "Layout issues"
✅ GOOD: "The second column starts 50px too far right, causing text to wrap prematurely"

❌ BAD: "Columns wrong"
✅ GOOD: "Column content is flipped - left column content appears in right column and vice versa. For LTR document, content should flow left-to-right."

❌ BAD: "Table broken"
✅ GOOD: "Table row 2 and row 3 are swapped - 'John Smith' data should appear before 'Jane Doe' data"

❌ BAD: "Text positioning wrong"
✅ GOOD: "The abstract paragraph is positioned 30px higher than in original, causing misalignment with adjacent column"

❌ BAD: "Spacing off"
✅ GOOD: "Line spacing in body text is 1.2 but should be 1.5 - text appears compressed compared to original"

❌ BAD: "Text wrong"
✅ GOOD: "Section heading breaks after 'Analysis' but should break after 'Statistical' - line wrapping doesn't match original"

## Positive Feedback (IMPORTANT):
In addition to errors, you MUST also identify what is CORRECT about the rendered HTML.
This helps the generator know what NOT to change during refinement.

Examples of correct_elements:
- "Two-column layout is correctly implemented with proper spacing"
- "Arabic text direction (RTL) is correctly applied throughout"
- "Mathematical equations are properly rendered with MathJax"
- "Font hierarchy is correct - title largest, then headers, then body"
- "Page margins and whitespace distribution match the original"

## Output Format (STRICT JSON):
You MUST return ONLY valid JSON in this exact format:

{
  "fidelity_score": <0-100>,
  "layout_score": <0-100>,
  "text_accuracy_score": <0-100>,
  "color_match_score": <0-100>,
  "equation_score": <0-100>,
  "correct_elements": [
    "<what is working well 1>",
    "<what is working well 2>",
    "<what is working well 3>"
  ],
  "critical_errors": [
    "<specific actionable error 1>",
    "<specific actionable error 2>",
    "<specific actionable error 3>"
  ]
}

The fidelity_score should be a weighted average emphasizing equations and layout.
Limit critical_errors to the TOP 5 most important issues to fix.
Include 3-5 correct_elements to reinforce what should NOT be changed.

Return ONLY the JSON, no additional text or markdown.
"""


class VisualJudge:
    """Compares original PDF with rendered HTML using vision models."""
    
    def __init__(self):
        self.use_openai = JUDGE_MODEL == "openai" and OPENAI_API_KEY
        
        if self.use_openai:
            import openai
            self.openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
            self.model_name = OPENAI_JUDGE_MODEL
        else:
            self.gemini_model = genai.GenerativeModel(GEMINI_JUDGE_MODEL)
            self.model_name = GEMINI_JUDGE_MODEL
    
    def compare(
        self, 
        original_image: str | Path, 
        rendered_image: str | Path
    ) -> JudgeFeedback:
        """
        Compare original PDF page with rendered HTML.
        
        Args:
            original_image: Path or base64 string of original PDF page
            rendered_image: Path or base64 string of rendered HTML
            
        Returns:
            JudgeFeedback with scores and error list
        """
        # Load images as base64 if paths provided
        original_b64 = self._load_image(original_image)
        rendered_b64 = self._load_image(rendered_image)
        
        if self.use_openai:
            response_text = self._compare_openai(original_b64, rendered_b64)
        else:
            response_text = self._compare_gemini(original_b64, rendered_b64)
        
        return self._parse_response(response_text)
    
    def _load_image(self, image: str | Path) -> str:
        """Load image as base64 string."""
        if isinstance(image, Path) or (isinstance(image, str) and Path(image).exists()):
            path = Path(image)
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        return image  # Already base64
    
    def _compare_gemini(self, original_b64: str, rendered_b64: str) -> str:
        """Use Gemini for visual comparison."""
        original_part = {"mime_type": "image/png", "data": original_b64}
        rendered_part = {"mime_type": "image/png", "data": rendered_b64}
        
        response = self.gemini_model.generate_content([
            "Here is the ORIGINAL PDF page:",
            original_part,
            "Here is the RENDERED HTML page:",
            rendered_part,
            JUDGE_PROMPT
        ])
        
        return response.text
    
    def _compare_openai(self, original_b64: str, rendered_b64: str) -> str:
        """Use OpenAI GPT-4o for visual comparison."""
        response = self.openai_client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Here is the ORIGINAL PDF page:"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{original_b64}"}
                        },
                        {"type": "text", "text": "Here is the RENDERED HTML page:"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{rendered_b64}"}
                        },
                        {"type": "text", "text": JUDGE_PROMPT}
                    ]
                }
            ],
            max_tokens=1000,
        )
        
        return response.choices[0].message.content
    
    def _parse_response(self, response_text: str) -> JudgeFeedback:
        """Parse JSON response from the judge."""
        # Clean up response
        text = response_text.strip()
        
        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        try:
            data = json.loads(text)
            return JudgeFeedback(
                fidelity_score=int(data.get("fidelity_score", 0)),
                critical_errors=data.get("critical_errors", []),
                correct_elements=data.get("correct_elements", []),
                layout_score=int(data.get("layout_score", 0)),
                text_accuracy_score=int(data.get("text_accuracy_score", 0)),
                color_match_score=int(data.get("color_match_score", 0)),
                equation_score=int(data.get("equation_score", 0)),
                raw_response=response_text,
            )
        except json.JSONDecodeError as e:
            # Return a failure feedback if parsing fails
            return JudgeFeedback(
                fidelity_score=0,
                critical_errors=[f"Failed to parse judge response: {e}", response_text[:500]],
                correct_elements=[],
                layout_score=0,
                text_accuracy_score=0,
                color_match_score=0,
                equation_score=0,
                raw_response=response_text,
            )
