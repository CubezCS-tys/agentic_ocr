Product Requirements Document: Recursive Augmentation OCR (RA-OCR)

1. Executive Summary

Project Name: Recursive Augmentation OCR (RA-OCR)
Objective: Create an autonomous OCR pipeline that converts PDF documents into "pixel-perfect" HTML/CSS.
Core Mechanism: An Agentic Feedback Loop.

Generator: An LLM converts a visual PDF page into HTML code.

renderer: The system renders that HTML into an image.

Judge: A second LLM visually compares the Original PDF vs. The Rendered HTML.

Loop: If the visual fidelity is not perfect (e.g., < 99% match), the Judge's feedback is fed back to the Generator to fix specific errors (fonts, columns, equations). This repeats until the score is maximized.

2. Technical Stack Requirements

The coding agent should utilize the following stack:

Language: Python 3.10+

Vision/Generator Model: Google Gemini 2.5-flash.

Judge Model: Google Gemini 1.5 Pro / GPT-4o.

PDF Processing: pymupdf (fitz) - for extracting page images and coordinate data.

HTML Rendering: playwright or html2image - to take screenshots of the generated HTML for the Judge.

Math Rendering: MathJax (via CDN) within the generated HTML for LaTeX equations.

3. System Architecture & Workflow

Phase 1: Ingestion

Input: A path to a local .pdf file.

Preprocessing: Convert the specific PDF page into a High-DPI Image (PNG, minimum 300 DPI).

Asset Extraction: (Critical) Identify non-text regions (images/charts) and crop them as separate image files or base64 strings to be referenced later.

Phase 2: The Generation Loop (Recursive Step)

This is the core logic. It requires a while loop constrained by MAX_RETRIES (e.g., 5) and TARGET_SCORE (e.g., 98/100).

Step A: Generation

Input: The high-res image of the PDF page.

Prompt: "Convert this image into a single HTML file using Tailwind CSS or internal CSS. Mimic the layout, font families (serif/sans), background colors, and column structure exactly. Render all math equations using LaTeX wrapped in $$."

Output: draft.html

Step B: Rendering

The Python script opens draft.html in a headless browser and takes a screenshot: rendered_view.png.

Step C: The Judge (Evaluation)

Input: Side-by-side comparison of original_pdf_page.png and rendered_view.png.

Prompt: "You are a QA Visual Engineer. Compare these two images. Rate the similarity from 0-100. List specific defects in JSON format (e.g., 'Title font is too small', 'Column 2 is misaligned', 'Equation 3 is missing a generic term')."

Output: JSON Object (Score + Feedback).

Step D: Decision

IF Score >= 98: Save draft.html as final. Break loop.

IF Score < 98: Pass the original HTML code AND the Judge's JSON feedback back to the Generator.

Refinement Prompt: "Here is your previous attempt. The QA Engineer pointed out these errors: [JSON Feedback]. Please rewrite the code to fix these specific issues while keeping the correct parts."

4. Specific Functional Requirements

4.1 Layout & Styling

Multi-Column: The system must use CSS Grid or Flexbox to perfectly match multi-column academic paper layouts.

Fonts: The LLM must approximate fonts. If the PDF uses a Serif font (like Times New Roman), the CSS must reflect font-family: 'Times New Roman', serif;.

Colors: Background colors (e.g., shaded boxes for code or definitions) must be preserved using correct Hex codes.

4.2 Equation Handling

The system must identify mathematical formulas.

It must not attempt to use ASCII art.

It must convert visual formulas into valid LaTeX syntax (e.g., \frac{a}{b}) and wrap them in MathJax delimiters ($$...$$ or \(...\)) so they render perfectly in the HTML.

4.3 Image & Asset Preservation

Strict Constraint: The LLM cannot "draw" images.

Strategy: The LLM should be instructed to place <img> tags where figures belong.

Implementation: The Python script should crop the figure from the original PDF (based on coordinates) and inject it as a Base64 string into the src attribute of the generated HTML.

5. Data Structure: The Judge's Feedback

The Judge LLM must return strict JSON to be parsed by the Python script.

{
  "fidelity_score": 88,
  "critical_errors": [
    "The main title font weight is too light.",
    "The second column text wraps prematurely.",
    "Equation 4 is rendered as plain text, not LaTeX."
  ],
  "layout_score": 90,
  "text_accuracy_score": 95,
  "color_match_score": 80
}


6. Success Criteria

The project is successful if:

Inputting a complex 2-column academic PDF results in an HTML file that, when opened in Chrome, looks indistinguishable from the PDF.

The text in the HTML is selectable and searchable (unlike the original image).

Equations are rendered as vector math (MathJax).

The system automatically iterates at least once to fix a visual error detected by the Judge.