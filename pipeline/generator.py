"""
HTML Generator Module
Uses Vision LLM to convert PDF page images into HTML/CSS.
"""

import google.generativeai as genai
from pathlib import Path

from config import GOOGLE_API_KEY, GENERATOR_MODEL


# Configure Gemini API
genai.configure(api_key=GOOGLE_API_KEY)


INITIAL_GENERATION_PROMPT = """You are an expert HTML/CSS developer specializing in pixel-perfect document recreation.

Your task is to convert this PDF page image into a single, self-contained HTML file that visually matches the original as closely as possible.

## CRITICAL Requirements:

### 1. Layout & Structure
- Use CSS Grid or Flexbox for multi-column layouts (academic papers often use 2 columns)
- Match the EXACT column structure, spacing, and margins
- Preserve headers, footers, page numbers, and their exact positioning
- Maintain proper spacing between sections, paragraphs, and elements
- Preserve any horizontal or vertical divider lines

### 2. Typography (CRITICAL)
- **Font Family**: Match exactly - use serif fonts (Georgia, 'Times New Roman', Times, serif) for academic/formal documents
- **Font Sizes**: Title should be larger, section headers medium, body text standard (approx 10-12pt)
- **Font Weights**: Bold for titles/headers, normal for body text
- **Line Height**: Match the original line spacing precisely (typically 1.2-1.5 for academic papers)
- **Text Alignment**: Justified text for body paragraphs in academic papers
- **Letter Spacing**: Match any special spacing in headers or titles

### 3. Colors & Backgrounds
- Match background colors for shaded boxes, definitions, theorems, or code blocks
- Use accurate hex color codes (sample from the image)
- Preserve borders, divider lines, and their colors
- Match text colors (usually black #000 for body text)

### 4. Mathematical Equations (ABSOLUTELY CRITICAL)
- Convert ALL mathematical formulas to proper LaTeX syntax
- Wrap INLINE math with \\( ... \\)  Example: \\( x^2 + y^2 = z^2 \\)
- Wrap DISPLAY/BLOCK math with $$ ... $$
- **NEVER use ASCII art, plain text, or Unicode symbols for equations**
- **NEVER write equations like "x^2" or "a/b" - always use LaTeX**

Common LaTeX patterns:
- Fractions: \\frac{numerator}{denominator}
- Subscripts: x_{i}, x_{n+1}
- Superscripts: x^{2}, e^{-x}
- Square roots: \\sqrt{x}, \\sqrt[n]{x}
- Summations: \\sum_{i=1}^{n} x_i
- Integrals: \\int_{a}^{b} f(x) dx
- Greek letters: \\alpha, \\beta, \\gamma, \\theta, \\lambda
- Limits: \\lim_{x \\to \\infty}
- Matrices: \\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}
- Equations with alignment: Use \\begin{align} for multi-line equations

### 5. Tables
- Recreate table structure with proper <table>, <thead>, <tbody>, <tr>, <th>, <td>
- Match border styles (solid, dashed, or none)
- Match cell padding and alignment
- Preserve header row styling (often bold or shaded)

### 6. Lists (Numbered & Bulleted)
- Use proper <ol> for numbered lists, <ul> for bulleted
- Match the numbering style (1., (1), i., a., etc.)
- Match indentation levels exactly
- Preserve spacing between list items

### 7. Images & Figures
- For figures, charts, diagrams, or images: insert a placeholder comment:
  <!-- FIGURE_PLACEHOLDER_0 -->
  <!-- FIGURE_PLACEHOLDER_1 -->
- I will inject the actual images later
- Include figure captions with proper styling (usually smaller, italic or centered)
- Match the figure's position in the layout

### 8. Special Elements
- **Theorems/Definitions/Lemmas**: Often have shaded backgrounds or borders
- **Algorithms**: Use proper formatting with line numbers if present
- **Code Blocks**: Use <pre><code> with monospace font, preserve indentation
- **Footnotes**: Position at bottom of page with proper numbering
- **References/Citations**: Match the citation style and formatting

### 9. RTL/Arabic Text (if present)
- Use dir="rtl" for right-to-left text sections
- Ensure proper Arabic font rendering
- Maintain correct text flow direction

### 10. Headers & Footers
- Match page numbers (position, font size, style)
- Include running headers if present (paper title, author names)
- Match the exact positioning (centered, left, right)

## Output Format:
Return ONLY the complete HTML code, starting with <!DOCTYPE html> and ending with </html>.
Include all CSS in a <style> tag in the <head>.

You MUST include this MathJax configuration in the <head>:

<script>
MathJax = {
  tex: {
    inlineMath: [['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$']],
    processEscapes: true
  },
  svg: { fontCache: 'global' }
};
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>

Do not include any explanation, just the HTML code.
"""


REFINEMENT_PROMPT_TEMPLATE = """You are an expert HTML/CSS developer. You generated an HTML version of this PDF page, and it received quality feedback.

## Quality Feedback from Visual Inspection:

**Fidelity Score:** {score}/100

### What's Working Well:
{correct_elements}

### Issues to Address:
{errors}

---

## Your Task:
Generate an IMPROVED version of the HTML that addresses all the issues mentioned above while maintaining the elements that are working well.

Focus on:
1. **TEXT ACCURACY** - Ensure ALL text is present and correct
2. **TEXT DIRECTION** - If RTL (Arabic/Hebrew), use dir="rtl" and text-align: right
3. **LAYOUT** - Match column structure and positioning exactly
4. **TYPOGRAPHY** - Match fonts, sizes, weights, and spacing
5. **MATHEMATICAL EQUATIONS** - Use proper LaTeX syntax with MathJax
6. **COLORS & STYLING** - Match the original document's appearance
## Remember to include MathJax for equations:
```html
<script>
MathJax = {{
  tex: {{
    inlineMath: [['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$']],
    processEscapes: true
  }},
  svg: {{ fontCache: 'global' }}
}};
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
```

Return ONLY the complete improved HTML code, starting with <!DOCTYPE html> and ending with </html>.
No explanations, no markdown code blocks - just the HTML.
"""


class HTMLGenerator:
    """Generates HTML from PDF page images using Gemini Flash."""
    
    def __init__(self):
        self.model = genai.GenerativeModel(GENERATOR_MODEL)
    
    def generate_initial(
        self, 
        page_image_base64: str, 
        figures: list[dict] = None,
        custom_prompt_additions: str = None
    ) -> str:
        """
        Generate initial HTML from a PDF page image.
        
        Args:
            page_image_base64: Base64-encoded PNG of the PDF page
            figures: List of extracted figures with base64 data
            custom_prompt_additions: Custom prompt additions from document analysis
            
        Returns:
            Generated HTML string
        """
        # Prepare the image for Gemini
        image_part = {
            "mime_type": "image/png",
            "data": page_image_base64
        }
        
        # Build the prompt
        prompt = INITIAL_GENERATION_PROMPT
        
        # Add custom analysis-based instructions if provided
        if custom_prompt_additions:
            prompt += f"\n\n## 📋 Document-Specific Instructions (from pre-analysis):\n{custom_prompt_additions}\n"
        
        # Add figure context if available
        if figures:
            figure_info = "\n\n## Available Figures:\n"
            for fig in figures:
                figure_info += f"- FIGURE_PLACEHOLDER_{fig['index']}: Image at position {fig.get('bbox', 'unknown')}\n"
            prompt += figure_info
        
        # Generate HTML
        response = self.model.generate_content([prompt, image_part])
        html = response.text
        
        # Clean up the response (remove markdown code blocks if present)
        html = self._clean_html_response(html)
        
        # Inject actual figures
        if figures:
            html = self._inject_figures(html, figures)
        
        return html
    
    def refine(self, previous_html: str, feedback: dict, page_image_base64: str) -> str:
        """
        Refine HTML based on Judge feedback.
        
        Uses pure feedback-based regeneration - the judge provides quality feedback,
        and the generator creates an improved version addressing those issues.
        
        Args:
            previous_html: The HTML from the previous iteration (for reference)
            feedback: Judge feedback dictionary with score and errors
            page_image_base64: Original page image for reference
            
        Returns:
            Refined HTML string
        """
        # Format feedback for the prompt
        errors_text = "\n".join(f"- {error}" for error in feedback.get("critical_errors", []))
        if not errors_text:
            errors_text = "- Minor visual discrepancies detected"
        
        correct_elements = feedback.get("correct_elements", [])
        if correct_elements:
            correct_text = "\n".join(f"✓ {element}" for element in correct_elements)
        else:
            correct_text = "✓ Initial analysis in progress"
        
        print("    [🔄 Regenerating HTML with feedback...]")
        
        # Build refinement prompt
        prompt = REFINEMENT_PROMPT_TEMPLATE.format(
            score=feedback.get("fidelity_score", 0),
            correct_elements=correct_text,
            errors=errors_text
        )
        
        # Include original image for reference
        image_part = {
            "mime_type": "image/png",
            "data": page_image_base64
        }
        
        response = self.model.generate_content([prompt, image_part])
        html = response.text
        
        print("    [✅ Regeneration complete]")
        return self._clean_html_response(html)
    
    def _clean_html_response(self, html: str) -> str:
        """Remove markdown code blocks and clean up the HTML response."""
        html = html.strip()
        
        # Remove markdown code block markers
        if html.startswith("```html"):
            html = html[7:]
        elif html.startswith("```"):
            html = html[3:]
        
        if html.endswith("```"):
            html = html[:-3]
        
        return html.strip()
    
    def _inject_figures(self, html: str, figures: list[dict]) -> str:
        """Replace figure placeholders with actual base64 images."""
        for fig in figures:
            placeholder = f"<!-- FIGURE_PLACEHOLDER_{fig['index']} -->"
            img_tag = f'<img src="{fig["data_uri"]}" alt="Figure {fig["index"]}" style="max-width: 100%; height: auto;" />'
            html = html.replace(placeholder, img_tag)
        
        return html
