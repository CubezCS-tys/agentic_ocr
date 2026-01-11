"""
Document Analyzer - Research phase before OCR generation.

Analyzes the PDF to understand its characteristics and generates
a customized prompt for the generator.
"""

import base64
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import google.generativeai as genai

from config import GOOGLE_API_KEY, GENERATOR_MODEL


@dataclass
class DocumentAnalysis:
    """Results from analyzing the document."""
    
    # Language & Text Direction
    primary_language: str = "English"
    text_direction: str = "ltr"  # ltr or rtl
    has_mixed_directions: bool = False
    
    # Content Types
    has_equations: bool = False
    equation_complexity: str = "none"  # none, simple, complex
    has_tables: bool = False
    has_figures: bool = False
    has_code_blocks: bool = False
    
    # Layout
    layout_type: str = "single-column"  # single-column, multi-column, mixed
    column_count: int = 1
    has_headers: bool = False
    has_footers: bool = False
    has_footnotes: bool = False
    has_margin_notes: bool = False
    
    # Typography
    font_styles: list = field(default_factory=lambda: ["regular"])
    has_bold: bool = False
    has_italic: bool = False
    has_underline: bool = False
    estimated_font_sizes: list = field(default_factory=lambda: ["medium"])
    
    # Colors
    background_color: str = "white"
    text_colors: list = field(default_factory=lambda: ["black"])
    has_colored_elements: bool = False
    header_color: str = ""  # Color of headers/titles (e.g., blue banner)
    
    # Special Elements
    has_lists: bool = False
    list_types: list = field(default_factory=list)  # bullet, numbered, etc.
    has_blockquotes: bool = False
    has_borders: bool = False
    has_boxes: bool = False
    
    # Document Type
    document_type: str = "general"  # academic, legal, technical, letter, form, etc.
    
    # Raw observations for the prompt
    observations: str = ""
    
    # Recommended CSS strategies
    css_recommendations: list = field(default_factory=list)
    
    # ===== NEW: Document-Wide Style Guide for Cross-Page Consistency =====
    style_guide: dict = field(default_factory=lambda: {
        "title_font": "Georgia, 'Times New Roman', serif",
        "body_font": "Georgia, 'Times New Roman', serif",
        "header_font": "Georgia, 'Times New Roman', serif",
        "title_size": "24px",
        "header_size": "18px",
        "body_size": "12px",
        "line_height": "1.5",
        "header_bg_color": "",  # e.g., "#4A90D9" for blue headers
        "header_text_color": "#000000",
        "body_text_color": "#000000",
        "background_color": "#FFFFFF",
    })
    
    # ===== NEW: Repeating Elements for Cross-Page Consistency =====
    repeating_elements: dict = field(default_factory=lambda: {
        "page_header": {
            "present": False,
            "content": "",  # e.g., "Document Title - Author Name"
            "description": "",  # Describe styling without CSS
        },
        "page_footer": {
            "present": False,
            "content": "",  # e.g., "Page {n}" or specific text
            "description": "",
        },
        "column_divider": {
            "present": False,
            "description": "",  # e.g., "thin gray vertical line"
        },
        "section_divider": {
            "present": False,
            "description": "",  # e.g., "2px solid black horizontal line"
        },
        "page_border": {
            "present": False,
            "description": "",
        },
    })


ANALYSIS_PROMPT = """You are a document analysis expert specializing in multilingual documents. 

TASK: You are given MULTIPLE SAMPLE PAGES from a single PDF document. Analyze them TOGETHER to understand the overall document characteristics. Pay VERY close attention to the script/alphabet used.

## SCRIPT DETECTION (MOST IMPORTANT):

Look at the TEXT CHARACTERS carefully across ALL pages:

**Arabic Script** (indicates Arabic, Persian, or Urdu language):
- Connected cursive letters flowing right-to-left
- Characters like: ا ب ت ث ج ح خ د ذ ر ز س ش ص ض ط ظ ع غ ف ق ك ل م ن ه و ي ء
- Dots above/below letters
- If you see ANY Arabic script in the body text on ANY page → primary_language: "Arabic", text_direction: "rtl"

**Latin Script** (indicates English, French, Spanish, etc.):
- Characters A-Z, a-z
- Separate disconnected letters
- Left-to-right flow

**CRITICAL**: Mathematical equations (x, y, z, α, β, ∫, Σ, etc.) use Latin/Greek symbols regardless of document language! 
A document with Arabic prose and Latin math symbols is STILL an Arabic RTL document.

## WHAT TO ANALYZE (across all pages):

1. **Language Detection**
   - What script is used for the PROSE/BODY text? (Not equations!)
   - Arabic script on ANY page → Arabic language, RTL
   - Note: First page may be a cover with different content than body pages

2. **Mathematical Content**
   - Are there equations, formulas, or mathematical expressions on ANY page?
   - Complexity: none, simple (basic fractions), complex (integrals, matrices)

3. **Layout** (CRITICAL - Look carefully at column structure!)
   - How many columns of text are there? Count them carefully!
   - If 2 columns: layout_type = "two-column", column_count = 2
   - If 1 column: layout_type = "single-column", column_count = 1
   - If mixed/varies: layout_type = "mixed"
   - Headers/footers present?

4. **Document Type**
   - Academic paper, textbook, form, letter, etc.

5. **Style Guide (IMPORTANT for cross-page consistency)**
   - Identify the EXACT styling that should be consistent across ALL pages
   - Header/banner colors (sample hex codes if colored headers exist)
   - Font families used (serif vs sans-serif)
   - Approximate font sizes for title, headers, and body

6. **Repeating Elements (CRITICAL for consistency across pages)**
   - Look for elements that appear in the SAME POSITION on MULTIPLE pages
   - Page headers: Running header text at top (e.g., document title, chapter name)
   - Page footers: Footer text at bottom (e.g., "Page X", journal name, date)
   - Column dividers: Vertical lines between columns (if two-column layout)
   - Section dividers: Horizontal lines separating sections
   - Page borders: Decorative borders around content

## RESPONSE FORMAT:

Return ONLY valid JSON (no markdown code blocks):

{
    "primary_language": "Arabic",
    "text_direction": "rtl",
    "has_mixed_directions": true,
    "has_equations": true,
    "equation_complexity": "complex",
    "has_tables": false,
    "has_figures": false,
    "has_code_blocks": false,
    "layout_type": "single-column",
    "column_count": 1,
    "has_headers": true,
    "has_footers": true,
    "has_footnotes": false,
    "has_margin_notes": false,
    "font_styles": ["serif"],
    "has_bold": true,
    "has_italic": false,
    "has_underline": false,
    "estimated_font_sizes": ["large", "medium"],
    "background_color": "white",
    "text_colors": ["black"],
    "has_colored_elements": true,
    "header_color": "#4A90D9",
    "has_lists": false,
    "list_types": [],
    "has_blockquotes": false,
    "has_borders": false,
    "has_boxes": true,
    "document_type": "academic",
    "observations": "Arabic academic paper with blue header banner. Body text is Arabic script (RTL).",
    "css_recommendations": ["direction: rtl", "font-family: Amiri, serif", "text-align: right"],
    "style_guide": {
        "title_font": "'Traditional Arabic', 'Amiri', serif",
        "body_font": "'Traditional Arabic', 'Amiri', serif",
        "header_font": "'Traditional Arabic', 'Amiri', serif",
        "title_size": "28px",
        "header_size": "20px",
        "body_size": "14px",
        "line_height": "1.6",
        "header_bg_color": "#4A90D9",
        "header_text_color": "#FFFFFF",
        "body_text_color": "#000000",
        "background_color": "#FFFFFF"
    },
    "repeating_elements": {
        "page_header": {
            "present": true,
            "content": "المعادلات التفاضلية الجزئية وتطبيقاتها",
            "description": "Blue banner (#31859C background) with white text, centered, moderate padding"
        },
        "page_footer": {
            "present": true,
            "content": "مجلة المنتدى الجامعي - Page {n}",
            "description": "Blue banner matching header, white text, split layout with journal name on one side and page number on other"
        },
        "column_divider": {
            "present": false,
            "description": ""
        },
        "section_divider": {
            "present": false,
            "description": ""
        },
        "page_border": {
            "present": false,
            "description": ""
        }
    }
}

Be THOROUGH. Analyze ALL provided pages together. If you see Arabic script on ANY page, the document is Arabic (RTL).
The style_guide is CRITICAL for ensuring consistent styling across all pages of the document.
The repeating_elements field ensures headers, footers, and dividers look IDENTICAL on every page.
"""


class DocumentAnalyzer:
    """Analyzes PDF pages to understand document characteristics."""
    
    def __init__(self, debug: bool = True):
        genai.configure(api_key=GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(GENERATOR_MODEL)
        self.debug = debug
    
    def _detect_arabic_in_text(self, text: str) -> bool:
        """Check if text contains Arabic characters."""
        import unicodedata
        arabic_count = 0
        latin_count = 0
        for char in text:
            try:
                name = unicodedata.name(char, '')
                if 'ARABIC' in name:
                    arabic_count += 1
                elif 'LATIN' in name:
                    latin_count += 1
            except:
                pass
        # If significant Arabic characters, it's Arabic
        return arabic_count > 10 or (arabic_count > 0 and arabic_count >= latin_count * 0.3)
    
    def _extract_text_from_image(self, image_path: Path) -> str:
        """Try to extract text using OCR for fallback language detection."""
        try:
            import fitz  # PyMuPDF has basic OCR capability
            # For now, we'll rely on the Vision LLM
            return ""
        except:
            return ""
    
    def analyze_page(self, image_path: Path) -> DocumentAnalysis:
        """Analyze a single page image."""
        
        if self.debug:
            print(f"    [ANALYZER] Analyzing: {image_path}")
        
        # Read and encode image
        with open(image_path, "rb") as f:
            image_data = f.read()
        
        if self.debug:
            print(f"    [ANALYZER] Image size: {len(image_data)} bytes")
        
        image_part = {
            "mime_type": "image/png",
            "data": base64.b64encode(image_data).decode("utf-8")
        }
        
        try:
            response = self.model.generate_content(
                [ANALYSIS_PROMPT, image_part],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=2000,
                )
            )
            
            if self.debug:
                print(f"    [ANALYZER] Raw response length: {len(response.text)} chars")
                print(f"    [ANALYZER] Raw response preview: {response.text[:500]}...")
            
            result = self._parse_response(response.text)
            
            if self.debug:
                print(f"    [ANALYZER] Parsed: lang={result.primary_language}, dir={result.text_direction}, equations={result.has_equations}")
            
            return result
            
        except Exception as e:
            print(f"    [ANALYZER] ERROR: {e}")
            import traceback
            traceback.print_exc()
            return DocumentAnalysis()
    
    def analyze_document(self, image_paths: list[Path]) -> DocumentAnalysis:
        """Analyze multiple pages in a SINGLE LLM call for holistic view."""
        
        if not image_paths:
            return DocumentAnalysis()
        
        if self.debug:
            print(f"    [ANALYZER] Analyzing {len(image_paths)} pages together in one call")
        
        # Build content with all images
        content = [ANALYSIS_PROMPT]
        
        for i, image_path in enumerate(image_paths):
            with open(image_path, "rb") as f:
                image_data = f.read()
            
            if self.debug:
                print(f"    [ANALYZER] Page {i+1}: {image_path.name} ({len(image_data)} bytes)")
            
            content.append(f"\n--- PAGE {i+1} of {len(image_paths)} ---\n")
            content.append({
                "mime_type": "image/png",
                "data": base64.b64encode(image_data).decode("utf-8")
            })
        
        try:
            response = self.model.generate_content(
                content,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=2000,
                )
            )
            
            if self.debug:
                print(f"    [ANALYZER] Raw response length: {len(response.text)} chars")
                print(f"    [ANALYZER] Raw response preview: {response.text[:500]}...")
            
            result = self._parse_response(response.text)
            
            if self.debug:
                print(f"    [ANALYZER] Parsed: lang={result.primary_language}, dir={result.text_direction}, equations={result.has_equations}")
            
            return result
            
        except Exception as e:
            print(f"    [ANALYZER] ERROR: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to single page analysis
            if image_paths:
                print(f"    [ANALYZER] Falling back to single page analysis...")
                return self.analyze_page(image_paths[0])
            return DocumentAnalysis()
    
    def _parse_response(self, text: str) -> DocumentAnalysis:
        """Parse the LLM response into a DocumentAnalysis object."""
        import json
        import re
        
        # Extract JSON from response
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON - use greedy match to get full object
            json_match = re.search(r'\{[\s\S]*\}', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                print(f"    [ANALYZER] ERROR: Could not find JSON in response")
                return DocumentAnalysis()
        
        try:
            data = json.loads(json_str)
            
            # Debug: Show what we actually parsed
            print(f"    [ANALYZER] Successfully parsed JSON with {len(data)} keys")
            print(f"    [ANALYZER] Parsed language: {data.get('primary_language')}, direction: {data.get('text_direction')}, columns: {data.get('column_count')}")
            
            # Parse style_guide if present
            style_guide_data = data.get("style_guide", {})
            default_style_guide = {
                "title_font": "Georgia, 'Times New Roman', serif",
                "body_font": "Georgia, 'Times New Roman', serif",
                "header_font": "Georgia, 'Times New Roman', serif",
                "title_size": "24px",
                "header_size": "18px",
                "body_size": "12px",
                "line_height": "1.5",
                "header_bg_color": "",
                "header_text_color": "#000000",
                "body_text_color": "#000000",
                "background_color": "#FFFFFF",
            }
            # Merge with defaults
            for key in default_style_guide:
                if key not in style_guide_data:
                    style_guide_data[key] = default_style_guide[key]
            
            # Parse repeating_elements if present
            repeating_elements_data = data.get("repeating_elements", {})
            default_repeating_elements = {
                "page_header": {"present": False, "content": "", "css": ""},
                "page_footer": {"present": False, "content": "", "css": ""},
                "column_divider": {"present": False, "style": ""},
                "section_divider": {"present": False, "style": ""},
                "page_border": {"present": False, "style": ""},
            }
            # Merge with defaults
            for key in default_repeating_elements:
                if key not in repeating_elements_data:
                    repeating_elements_data[key] = default_repeating_elements[key]
            
            # ===== Normalize layout_type values =====
            layout_type_raw = data.get("layout_type", "single-column")
            column_count = data.get("column_count", 1)
            
            # Normalize various layout_type values the LLM might return
            layout_type_normalized = layout_type_raw.lower().strip()
            if "two" in layout_type_normalized or "2" in layout_type_normalized or "double" in layout_type_normalized:
                layout_type = "two-column"
                column_count = max(column_count, 2)  # Ensure column_count matches
            elif "multi" in layout_type_normalized or column_count > 2:
                layout_type = "multi-column"
            elif "single" in layout_type_normalized or "one" in layout_type_normalized or column_count == 1:
                layout_type = "single-column"
            elif "mixed" in layout_type_normalized:
                layout_type = "mixed"
            else:
                layout_type = layout_type_raw  # Keep original if unrecognized
            
            # Also infer from column_count if layout_type seems wrong
            if column_count >= 2 and layout_type == "single-column":
                layout_type = "two-column" if column_count == 2 else "multi-column"
                print(f"    [ANALYZER] Fixed layout_type mismatch: column_count={column_count} -> layout_type={layout_type}")
            
            print(f"    [ANALYZER] Layout: {layout_type} ({column_count} columns)")
            
            return DocumentAnalysis(
                primary_language=data.get("primary_language", "English"),
                text_direction=data.get("text_direction", "ltr"),
                has_mixed_directions=data.get("has_mixed_directions", False),
                has_equations=data.get("has_equations", False),
                equation_complexity=data.get("equation_complexity", "none"),
                has_tables=data.get("has_tables", False),
                has_figures=data.get("has_figures", False),
                has_code_blocks=data.get("has_code_blocks", False),
                layout_type=layout_type,
                column_count=column_count,
                has_headers=data.get("has_headers", False),
                has_footers=data.get("has_footers", False),
                has_footnotes=data.get("has_footnotes", False),
                has_margin_notes=data.get("has_margin_notes", False),
                font_styles=data.get("font_styles", ["regular"]),
                has_bold=data.get("has_bold", False),
                has_italic=data.get("has_italic", False),
                has_underline=data.get("has_underline", False),
                estimated_font_sizes=data.get("estimated_font_sizes", ["medium"]),
                background_color=data.get("background_color", "white"),
                text_colors=data.get("text_colors", ["black"]),
                has_colored_elements=data.get("has_colored_elements", False),
                header_color=data.get("header_color", ""),
                has_lists=data.get("has_lists", False),
                list_types=data.get("list_types", []),
                has_blockquotes=data.get("has_blockquotes", False),
                has_borders=data.get("has_borders", False),
                has_boxes=data.get("has_boxes", False),
                document_type=data.get("document_type", "general"),
                observations=data.get("observations", ""),
                css_recommendations=data.get("css_recommendations", []),
                style_guide=style_guide_data,
                repeating_elements=repeating_elements_data,
            )
        except json.JSONDecodeError as e:
            print(f"    [ANALYZER] ERROR: JSON parse failed: {e}")
            print(f"    [ANALYZER] JSON string was: {json_str[:500]}...")
            return DocumentAnalysis()
    
    def generate_custom_prompt(self, analysis: DocumentAnalysis) -> str:
        """Generate a customized generator prompt based on the analysis."""
        
        sections = []
        
        # Document overview
        sections.append(f"""## Document Analysis Results

This document has been analyzed and identified as: **{analysis.document_type}**
Primary Language: **{analysis.primary_language}**
Text Direction: **{analysis.text_direction.upper()}**
""")
        
        # Critical RTL handling
        if analysis.text_direction == "rtl":
            mixed_note = ""
            if analysis.has_mixed_directions or analysis.has_equations:
                mixed_note = """
**MIXED DIRECTION HANDLING (Arabic + Math/English):**
- Mathematical equations use Latin characters (x, y, z, α, β) - this is normal!
- Wrap equations in `<span dir="ltr">` or let MathJax handle them
- English words/citations should be wrapped in `<span dir="ltr">`
- The overall document direction remains RTL
- Use CSS: `unicode-bidi: embed;` for LTR spans within RTL context

Example for inline equation in Arabic text:
```html
<p dir="rtl">نستخدم المعادلة <span dir="ltr">\\( x^2 + y^2 = r^2 \\)</span> لحساب...</p>
```
"""
            
            sections.append(f"""
## ⚠️ CRITICAL: Right-to-Left (RTL) Document

This is an RTL document. You MUST:
1. Add `dir="rtl"` to the `<html>` tag
2. Add `direction: rtl;` to the body CSS
3. Use `text-align: right;` for text blocks
4. Use an appropriate Arabic/RTL font (Amiri, Scheherazade, Noto Naskh Arabic, Traditional Arabic)
5. Ensure all Arabic text flows correctly from right to left
{mixed_note}
```css
html {{
    direction: rtl;
}}
body {{
    font-family: 'Amiri', 'Traditional Arabic', 'Arabic Typesetting', serif;
    text-align: right;
}}
```
""")
        
        # Equations handling
        if analysis.has_equations:
            complexity_guide = {
                "simple": "Use HTML/CSS for simple fractions and subscripts where possible.",
                "complex": "Use MathJax for all equations. Include the MathJax CDN.",
            }
            sections.append(f"""
## Mathematical Equations

This document contains **{analysis.equation_complexity}** equations.
{complexity_guide.get(analysis.equation_complexity, '')}

Include MathJax:
```html
<script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
```

Use LaTeX notation: `\\( ... \\)` for inline, `\\[ ... \\]` for display equations.
""")
        
        # Layout handling - check for any multi-column variants
        is_multi_column = (
            analysis.column_count > 1 or 
            analysis.layout_type in ("multi-column", "two-column", "2-column")
        )
        if is_multi_column:
            sections.append(f"""
## Multi-Column Layout

This document has **{analysis.column_count} columns** (layout_type: {analysis.layout_type}).
Use CSS Grid or Flexbox:

```css
.columns {{
    display: grid;
    grid-template-columns: repeat({analysis.column_count}, 1fr);
    gap: 20px;
}}
```
""")
        
        # Tables
        if analysis.has_tables:
            sections.append("""
## Tables

This document contains tables. Use proper HTML `<table>` elements with:
- `<thead>` for headers
- `<tbody>` for body
- Appropriate borders and padding
- Match the original styling exactly
""")
        
        # Typography
        typography_notes = []
        if analysis.has_bold:
            typography_notes.append("Use `<strong>` or `font-weight: bold` for bold text")
        if analysis.has_italic:
            typography_notes.append("Use `<em>` or `font-style: italic` for italic text")
        if analysis.has_underline:
            typography_notes.append("Use `text-decoration: underline` for underlined text")
        
        if typography_notes:
            sections.append(f"""
## Typography

{chr(10).join('- ' + note for note in typography_notes)}
""")
        
        # Colors
        if analysis.has_colored_elements:
            sections.append(f"""
## Colors

Background: {analysis.background_color}
Text colors detected: {', '.join(analysis.text_colors)}

Match these colors exactly. Use a color picker if needed.
""")
        
        # Lists
        if analysis.has_lists:
            list_guidance = ", ".join(analysis.list_types) if analysis.list_types else "bullet and numbered"
            sections.append(f"""
## Lists

Document contains lists ({list_guidance}).
Use `<ul>` for bullets, `<ol>` for numbered lists.
Match the exact bullet/number style.
""")
        
        # Special elements
        special = []
        if analysis.has_borders:
            special.append("borders around sections")
        if analysis.has_boxes:
            special.append("boxed content areas")
        if analysis.has_blockquotes:
            special.append("blockquotes or indented sections")
        if analysis.has_footnotes:
            special.append("footnotes")
        if analysis.has_margin_notes:
            special.append("margin notes")
        
        if special:
            sections.append(f"""
## Special Elements

This document has: {', '.join(special)}.
Replicate these exactly using CSS borders, padding, and positioning.
""")
        
        # Observations and recommendations
        if analysis.observations:
            sections.append(f"""
## Key Observations

{analysis.observations}
""")
        
        if analysis.css_recommendations:
            sections.append(f"""
## Recommended CSS Strategies

{chr(10).join('- ' + rec for rec in analysis.css_recommendations)}
""")
        
        # ===== NEW: Document-Wide Style Guide for Cross-Page Consistency =====
        sg = analysis.style_guide
        sections.append(f"""
## 🎨 DOCUMENT STYLE GUIDE (MUST USE FOR CONSISTENCY)

**CRITICAL**: Use these EXACT styles on EVERY page to ensure consistent appearance:

### Fonts (USE EXACTLY):
```css
/* Title/Main Heading */
.title, h1 {{
    font-family: {sg.get('title_font', 'Georgia, serif')};
    font-size: {sg.get('title_size', '24px')};
}}

/* Section Headers */
h2, h3, .section-header {{
    font-family: {sg.get('header_font', 'Georgia, serif')};
    font-size: {sg.get('header_size', '18px')};
}}

/* Body Text */
body, p {{
    font-family: {sg.get('body_font', 'Georgia, serif')};
    font-size: {sg.get('body_size', '12px')};
    line-height: {sg.get('line_height', '1.5')};
    color: {sg.get('body_text_color', '#000000')};
}}
```

### Colors (USE EXACTLY):
- Background: `{sg.get('background_color', '#FFFFFF')}`
- Body text: `{sg.get('body_text_color', '#000000')}`
- Header text: `{sg.get('header_text_color', '#000000')}`
{f"- Header/Banner background: `{sg.get('header_bg_color')}`" if sg.get('header_bg_color') else ""}

**DO NOT deviate from these styles. Consistency across pages is essential.**
""")
        
        # ===== NEW: Repeating Elements for Cross-Page Consistency =====
        re = analysis.repeating_elements
        repeating_sections = []
        
        if re.get('page_header', {}).get('present'):
            header_info = re['page_header']
            repeating_sections.append(f"""
### Page Header (SAME ON EVERY PAGE):
Content: "{header_info.get('content', '')}"
Description: {header_info.get('description', 'Replicate styling from original')}
""")
        
        if re.get('page_footer', {}).get('present'):
            footer_info = re['page_footer']
            repeating_sections.append(f"""
### Page Footer (SAME ON EVERY PAGE):
Content pattern: "{footer_info.get('content', '')}"
Description: {footer_info.get('description', 'Replicate styling from original')}
""")
        
        if re.get('column_divider', {}).get('present'):
            divider_info = re['column_divider']
            repeating_sections.append(f"""
### Column Divider (between columns):
Description: {divider_info.get('description', 'thin vertical line')}
""")
        
        if re.get('section_divider', {}).get('present'):
            divider_info = re['section_divider']
            repeating_sections.append(f"""
### Section Divider (horizontal line):
Description: {divider_info.get('description', 'horizontal line separator')}
""")
        
        if repeating_sections:
            sections.append(f"""
## 🔁 REPEATING ELEMENTS (MUST BE IDENTICAL ON EVERY PAGE)

**CRITICAL**: These elements appear on multiple pages and MUST look exactly the same each time:
{''.join(repeating_sections)}
**Replicate these elements with matching colors, sizes, and positioning on every page.**
""")
        
        return "\n".join(sections)


def analyze_and_get_prompt(image_paths: list[Path]) -> tuple[DocumentAnalysis, str]:
    """Convenience function to analyze document and get custom prompt."""
    analyzer = DocumentAnalyzer()
    analysis = analyzer.analyze_document(image_paths)
    custom_prompt = analyzer.generate_custom_prompt(analysis)
    return analysis, custom_prompt
