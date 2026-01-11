"""
Assembler Module (Stage 3)

Pure Python module that merges the layout skeleton with extracted content
to produce the final HTML output. No LLM calls - fully deterministic.
"""

import re
from pathlib import Path
from dataclasses import dataclass
from bs4 import BeautifulSoup, NavigableString
from typing import Optional


# Patterns that indicate LLM reasoning leaked into content
LLM_REASONING_PATTERNS = [
    r"^(?:Wait|Let me|I'll|I should|I need to|I will|I can|I'm going to)",
    r"^(?:Here is|Here's|This is|Output:|Result:|Final|The example shows)",
    r"^(?:Looking at|Based on|According to|Now I|First,|Next,|Finally,)",
    r"^(?:Hmm|Ok,|Okay,|Alright|Sure|Yes,|No,)",
    r"(?:Let me|I'll|I should|I need to) (?:check|verify|confirm|look|see|try)",
    r"^```(?:html|json)?",
    r"```$",
    r"^\s*#.*(?:check|verify|note|todo|fixme)",
]

# Compile patterns for efficiency
LLM_REASONING_REGEX = re.compile(
    "|".join(LLM_REASONING_PATTERNS), 
    re.IGNORECASE | re.MULTILINE
)


def is_llm_reasoning(text: str) -> bool:
    """Check if text appears to be LLM reasoning rather than actual content."""
    if not text or not isinstance(text, str):
        return False
    
    # Check against known patterns
    if LLM_REASONING_REGEX.search(text):
        return True
    
    return False


def sanitize_content(content: str) -> str:
    """
    Remove any LLM reasoning that leaked into content.
    
    Returns cleaned content or empty string if content is entirely reasoning.
    """
    if not content or not isinstance(content, str):
        return content
    
    # Check if entire content is LLM reasoning
    if is_llm_reasoning(content.strip()):
        return ""
    
    # Remove markdown code block markers
    content = re.sub(r'^```(?:html|json)?\s*\n?', '', content, flags=re.MULTILINE)
    content = re.sub(r'\n?```\s*$', '', content, flags=re.MULTILINE)
    
    # Remove lines that are clearly LLM thoughts
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        if not is_llm_reasoning(line.strip()):
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines).strip()


@dataclass
class AssemblyResult:
    """Result from assembly stage."""
    html: str
    success: bool = True
    errors: list[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class Assembler:
    """
    Stage 3: Assemble final HTML from skeleton and content.
    
    This is a pure Python module - no LLM calls.
    Takes the layout skeleton and content mapping and produces final HTML.
    """
    
    def __init__(self, template_path: Optional[Path] = None):
        """
        Initialize the assembler.
        
        Args:
            template_path: Path to base HTML template (optional)
        """
        self.template_path = template_path
        self.base_template = self._load_template()
    
    def _load_template(self) -> str:
        """Load the base HTML template."""
        if self.template_path and self.template_path.exists():
            return self.template_path.read_text(encoding="utf-8")
        
        # Default template
        return '''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Staged OCR Output</title>
    
    <!-- MathJax for LaTeX rendering -->
    <script>
        MathJax = {
            tex: {
                inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
                displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
                processEscapes: true,
                processEnvironments: true
            },
            options: {
                skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
            }
        };
    </script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    
    <style>
        /* Base Reset */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Traditional Arabic', 'Amiri', 'Times New Roman', serif;
            font-size: 14pt;
            line-height: 1.6;
            color: #000;
            background: #fff;
            padding: 1in;
            max-width: 8.5in;
            margin: 0 auto;
        }
        
        /* Page container */
        .page {
            position: relative;
        }
        
        .page[dir="rtl"] {
            text-align: right;
        }
        
        /* Typography */
        .title, h1 {
            font-size: 18pt;
            font-weight: bold;
            text-align: center;
            margin-bottom: 12pt;
        }
        
        .authors {
            text-align: center;
            margin-bottom: 12pt;
        }
        
        .section-heading, h2 {
            font-size: 14pt;
            font-weight: bold;
            margin-top: 16pt;
            margin-bottom: 8pt;
        }
        
        /* Two-column layout */
        .two-column-layout {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.4in;
            margin: 12pt 0;
        }
        
        .page[dir="rtl"] .two-column-layout {
            direction: rtl;
        }
        
        .column {
            text-align: justify;
        }
        
        /* Equations */
        .equation-block {
            margin: 16pt 0;
            text-align: center;
            direction: ltr;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 20px;
            flex-wrap: wrap;
        }
        
        .equation-number {
            order: -1;
        }
        
        .page[dir="rtl"] .equation-block {
            flex-direction: row-reverse;
        }
        
        /* Equation labels (Arabic text next to equations) */
        .equation-label {
            direction: rtl;
            text-align: right;
            font-size: 12pt;
        }
        
        /* Tables */
        .table-container {
            margin: 16pt 0;
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 8pt 0;
        }
        
        th, td {
            border: 1px solid #000;
            padding: 6pt 8pt;
            text-align: right;
        }
        
        th {
            background: #f0f0f0;
            font-weight: bold;
        }
        
        /* Figures */
        .figure-block {
            margin: 16pt 0;
            text-align: center;
        }
        
        .figure-placeholder {
            background: #f5f5f5;
            border: 2px dashed #ccc;
            padding: 40px;
            margin: 8pt 0;
            color: #666;
            font-style: italic;
        }
        
        figcaption {
            font-size: 11pt;
            margin-top: 8pt;
        }
        
        /* Footnotes */
        .footnotes {
            margin-top: 24pt;
            padding-top: 12pt;
            border-top: 1px solid #000;
            font-size: 10pt;
        }
        
        .footnote {
            margin-bottom: 4pt;
        }
        
        /* Abstract */
        .abstract-section {
            margin: 16pt 0;
            padding: 12pt;
            background: #fafafa;
            border: 1px solid #ddd;
        }
        
        .abstract {
            text-align: justify;
        }
        
        /* Page number */
        .page-number {
            text-align: center;
            margin-top: 24pt;
            font-size: 11pt;
        }
        
        /* Error markers */
        .extraction-error {
            background: #ffebee;
            border: 2px dashed #f44336;
            padding: 8pt;
            color: #c62828;
        }
        
        .error-marker {
            font-family: monospace;
            font-size: 10pt;
        }
        
        /* Mixed content (inline math) */
        .mixed-content {
            display: inline;
        }
    </style>
    
    {{CUSTOM_STYLES}}
</head>
<body>
    {{CONTENT}}
</body>
</html>'''
    
    def assemble(
        self, 
        skeleton_html: str, 
        content: dict,
        custom_styles: str = ""
    ) -> AssemblyResult:
        """
        Assemble final HTML from skeleton and content.
        
        Args:
            skeleton_html: HTML skeleton from layout stage
            content: Content mapping from text extraction stage
            custom_styles: Additional CSS styles
            
        Returns:
            AssemblyResult with final HTML
        """
        errors = []
        
        # Parse skeleton
        soup = BeautifulSoup(skeleton_html, 'html.parser')
        
        # Process each element with data-ref
        for element in soup.find_all(attrs={"data-ref": True}):
            ref = element.get("data-ref")
            data = content.get(ref)
            
            if data is None:
                # Missing content - add error marker
                errors.append(f"Missing content for ref: {ref}")
                self._add_error_marker(soup, element, ref)
                continue
            
            if isinstance(data, dict) and data.get("type") == "error":
                # Error in extraction - add error marker
                errors.append(f"Extraction failed for ref: {ref}")
                self._add_error_marker(soup, element, ref, data.get("error", "Unknown error"))
                continue
            
            # Process based on content type
            try:
                self._inject_content(soup, element, data)
            except Exception as e:
                errors.append(f"Error processing ref {ref}: {e}")
                self._add_error_marker(soup, element, ref, str(e))
        
        # Clean up data attributes
        for element in soup.find_all(attrs={"data-ref": True}):
            del element["data-ref"]
            if element.has_attr("data-type"):
                del element["data-type"]
            if element.has_attr("data-reading-order"):
                del element["data-reading-order"]
            if element.has_attr("data-complexity"):
                del element["data-complexity"]
        
        # Inject into template
        final_html = self.base_template.replace("{{CONTENT}}", str(soup))
        final_html = final_html.replace("{{CUSTOM_STYLES}}", custom_styles)
        
        return AssemblyResult(
            html=final_html,
            success=len(errors) == 0,
            errors=errors
        )
    
    def _inject_content(self, soup, element, data: dict):
        """Inject content into an element based on content type."""
        content_type = data.get("type", "text")
        ref = element.get("data-ref", "unknown")
        
        if content_type == "text":
            self._inject_text(element, data)
        elif content_type == "mixed":
            self._inject_mixed(soup, element, data)
        elif content_type == "math":
            self._inject_math(soup, element, data)
        elif content_type == "table":
            self._inject_table(soup, element, data)
        elif content_type == "figure":
            self._inject_figure(soup, element, data)
        elif content_type == "error":
            # Explicit error type - already handled by caller
            pass
        else:
            # Unknown type - log warning and treat as text
            print(f"  ⚠ Unknown content type '{content_type}' for ref '{ref}', treating as text")
            self._inject_text(element, data)
    
    def _inject_text(self, element, data: dict):
        """
        Inject text content. 
        
        Supports new Markdown format where inline math uses $...$ delimiters directly.
        The content is rendered as-is since KaTeX/MathJax will handle the math.
        """
        content = data.get("content", "")
        direction = data.get("direction")
        language = data.get("language")
        
        # Sanitize content to remove any LLM reasoning
        content = sanitize_content(content)
        
        if not content:
            # Content was entirely LLM reasoning - mark as error
            element.string = "[SANITIZED: LLM reasoning detected]"
            element["class"] = element.get("class", []) + ["extraction-error"]
            return
        
        # Content now uses Markdown-style $...$ for inline math
        # Just inject as-is - KaTeX/MathJax will render the math
        element.string = content
        
        if direction:
            element["dir"] = direction
        if language:
            element["lang"] = language
    
    def _inject_mixed(self, soup, element, data: dict):
        """
        Inject mixed content (legacy format with segments).
        
        Note: New format uses $...$ directly in text content. This method
        is kept for backward compatibility with older extraction results.
        """
        segments = data.get("segments", [])
        direction = data.get("direction")
        language = data.get("language")
        
        if direction:
            element["dir"] = direction
        if language:
            element["lang"] = language
        
        # Clear existing content
        element.clear()
        
        for segment in segments:
            seg_type = segment.get("type", "text")
            seg_content = segment.get("content", "")
            
            # Sanitize text content
            if seg_type == "text":
                seg_content = sanitize_content(seg_content)
                if seg_content:  # Only add non-empty content
                    element.append(NavigableString(seg_content))
            elif seg_type == "math":
                # Wrap math in appropriate delimiters
                display = segment.get("display", "inline")
                if display == "inline":
                    math_text = f"${seg_content}$"
                else:
                    math_text = f"$${seg_content}$$"
                element.append(NavigableString(math_text))
            else:
                # Unknown segment type - treat as text and sanitize
                seg_content = sanitize_content(seg_content)
                if seg_content:
                    element.append(NavigableString(seg_content))
    
    def _inject_math(self, soup, element, data: dict):
        """Inject display/block math content."""
        content = data.get("content", "")
        display = data.get("display", "block")
        equation_number = data.get("equation_number")
        label = data.get("label")  # Arabic label to render separately
        
        # Build math HTML
        if display == "block":
            math_html = f"$${content}$$"
        else:
            math_html = f"${content}$"
        
        element.clear()
        
        # Add equation number if present
        if equation_number:
            num_span = soup.new_tag("span")
            num_span["class"] = "equation-number"
            num_span.string = f"({equation_number})"
            element.append(num_span)
        
        element.append(NavigableString(math_html))
        
        # Add label if present (for text that shouldn't be in LaTeX)
        if label:
            label_span = soup.new_tag("span")
            label_span["class"] = "equation-label"
            # Inherit direction from data, default to rtl for Arabic
            label_direction = data.get("label_direction") or data.get("direction", "rtl")
            label_lang = data.get("label_language") or data.get("language", "ar")
            label_span["dir"] = label_direction
            label_span["lang"] = label_lang
            label_span.string = sanitize_content(label) or label
            element.append(label_span)
    
    def _inject_table(self, soup, element, data: dict):
        """Inject table content."""
        headers = data.get("headers", [])
        rows = data.get("rows", [])
        caption = data.get("caption")
        direction = data.get("direction", "rtl")
        
        element.clear()
        
        # Create table
        table = soup.new_tag("table")
        table["dir"] = direction
        
        # Add headers
        if headers:
            thead = soup.new_tag("thead")
            tr = soup.new_tag("tr")
            for header in headers:
                th = soup.new_tag("th")
                # Sanitize header content
                th.string = sanitize_content(str(header)) or str(header)
                tr.append(th)
            thead.append(tr)
            table.append(thead)
        
        # Add rows
        tbody = soup.new_tag("tbody")
        for row in rows:
            tr = soup.new_tag("tr")
            for cell in row:
                td = soup.new_tag("td")
                # Sanitize cell content
                td.string = sanitize_content(str(cell)) or str(cell)
                tr.append(td)
            tbody.append(tr)
        table.append(tbody)
        
        element.append(table)
        
        # Add caption
        if caption:
            cap_div = soup.new_tag("div")
            cap_div["class"] = "table-caption"
            cap_div.string = caption
            element.append(cap_div)
    
    def _inject_figure(self, soup, element, data: dict):
        """Inject figure placeholder with description."""
        description = data.get("description", "Figure")
        position = data.get("position", "center")
        
        # Sanitize description to remove LLM reasoning
        description = sanitize_content(description) or "Figure"
        
        # Find or create placeholder
        placeholder = element.find(class_="figure-placeholder")
        if placeholder:
            placeholder.string = f"[{description}]"
        else:
            element.clear()
            placeholder = soup.new_tag("div")
            placeholder["class"] = "figure-placeholder"
            placeholder.string = f"[{description}]"
            element.append(placeholder)
    
    def _add_error_marker(self, soup, element, ref: str, error_msg: str = None):
        """Add an error marker for failed extraction."""
        element["class"] = element.get("class", [])
        if isinstance(element["class"], str):
            element["class"] = [element["class"]]
        element["class"].append("extraction-error")
        
        error_text = f"[EXTRACTION_FAILED: {ref}]"
        if error_msg:
            error_text += f" - {error_msg}"
        
        element.clear()
        span = soup.new_tag("span")
        span["class"] = "error-marker"
        span.string = error_text
        element.append(span)
