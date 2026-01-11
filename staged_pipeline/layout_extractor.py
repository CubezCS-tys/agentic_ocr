"""
Layout Extractor Module (Stage 1)

Analyzes page images and extracts the visual structure as an HTML skeleton
with data-ref placeholders for content injection.
"""

import json
import re
import time
from pathlib import Path
from dataclasses import dataclass, field
from bs4 import BeautifulSoup
import google.generativeai as genai

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import GOOGLE_API_KEY, GENERATOR_MODEL
from .cost_tracker import get_tracker, extract_usage_from_response


# Configure Gemini API
genai.configure(api_key=GOOGLE_API_KEY)


@dataclass
class LayoutResult:
    """Result from layout extraction."""
    skeleton_html: str
    references: list[dict]  # List of {ref: str, type: str, reading_order: int}
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)


class LayoutExtractor:
    """
    Stage 1: Extract document layout structure.
    
    Analyzes a page image and produces an HTML skeleton with data-ref
    placeholders marking where content should be injected.
    """
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name or GENERATOR_MODEL
        self.model = genai.GenerativeModel(self.model_name)
        self.prompt = self._load_prompt()
    
    def _load_prompt(self) -> str:
        """Load the layout extraction prompt from file."""
        prompt_path = Path(__file__).parent / "prompts" / "layout_prompt.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        else:
            raise FileNotFoundError(f"Layout prompt not found: {prompt_path}")
    
    def extract(self, page_image_base64: str) -> LayoutResult:
        """
        Extract layout structure from a page image.
        
        Args:
            page_image_base64: Base64-encoded PNG of the page
            
        Returns:
            LayoutResult with HTML skeleton and reference list
        """
        # Prepare image for Gemini
        image_part = {
            "mime_type": "image/png",
            "data": page_image_base64
        }
        
        # Retry logic for safety filter errors
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Call the model with timing and timeout
                start_time = time.time()
                response = self.model.generate_content(
                    [self.prompt, image_part],
                    generation_config={
                        "temperature": 0.0,  # Zero temperature for maximum consistency
                        "max_output_tokens": 16384,  # Enough for complex layouts
                    },
                    request_options={"timeout": 120}  # 2 minute timeout
                )
                duration_ms = (time.time() - start_time) * 1000
                
                # Check for valid response
                if not response.candidates or not response.candidates[0].content.parts:
                    finish_reason = response.candidates[0].finish_reason if response.candidates else "UNKNOWN"
                    raise ValueError(f"Empty response from API (finish_reason: {finish_reason})")
                
                # Track cost
                input_tokens, output_tokens = extract_usage_from_response(response)
                get_tracker().add_call(
                    stage="layout_extraction",
                    model=self.model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    duration_ms=duration_ms
                )
                
                # Extract HTML from response
                skeleton_html = self._clean_response(response.text)
                
                # Validate the cleaned HTML is actually HTML
                if not skeleton_html.strip().startswith("<"):
                    raise ValueError(f"Layout response is not valid HTML. Got: {skeleton_html[:100]}...")
                
                # Parse and extract references
                references = self._extract_references(skeleton_html)
                
                # Validate we got at least one reference
                if not references:
                    raise ValueError("Layout extraction produced no references - likely invalid output")
                
                # Validate the skeleton
                warnings = self._validate_skeleton(skeleton_html, references)
                
                return LayoutResult(
                    skeleton_html=skeleton_html,
                    references=references,
                    confidence=1.0 if not warnings else 0.9,
                    warnings=warnings
                )
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                if "finish_reason" in error_msg or "safety" in error_msg.lower():
                    print(f"    ⚠ Safety filter triggered, retrying ({attempt + 1}/{max_retries})...")
                    time.sleep(1)  # Brief pause before retry
                else:
                    # Non-retryable error
                    raise
        
        # All retries failed
        raise Exception(f"Layout extraction failed after {max_retries} attempts: {last_error}")
    
    def _clean_response(self, response_text: str) -> str:
        """Clean up the LLM response to extract just the HTML."""
        text = response_text.strip()
        
        # Remove markdown code blocks if present
        if text.startswith("```html"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        
        if text.endswith("```"):
            text = text[:-3]
        
        text = text.strip()
        
        # Remove any LLM reasoning that might precede the HTML
        # Common patterns to remove
        llm_reasoning_patterns = [
            r'^(?:Here is|Here\'s|Output:|Result:|The HTML:).*?\n',
            r'^(?:I\'ll|Let me|I will|I should|Wait,|Ok,|Okay,).*?\n',
            r'^(?:Looking at|Based on|First,|The page).*?\n',
        ]
        for pattern in llm_reasoning_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        text = text.strip()
        
        # Ensure it starts with the page div
        if not text.startswith("<div"):
            # Try to find the start of HTML
            match = re.search(r'<div\s+class=["\']page["\']', text, re.IGNORECASE)
            if match:
                text = text[match.start():]
            else:
                # Look for any div start
                match = re.search(r'<div', text, re.IGNORECASE)
                if match:
                    text = text[match.start():]
        
        # Remove any trailing text after the last </div>
        last_div_close = text.rfind("</div>")
        if last_div_close != -1:
            text = text[:last_div_close + 6]
        
        return text
    
    def _extract_references(self, skeleton_html: str) -> list[dict]:
        """
        Extract all data-ref elements from the skeleton.
        
        Returns list of dicts with ref, type, bbox, and complexity.
        Order is determined by DOM position (visual order).
        """
        soup = BeautifulSoup(skeleton_html, 'html.parser')
        references = []
        
        # find_all returns elements in DOM order, which reflects visual order
        for idx, element in enumerate(soup.find_all(attrs={"data-ref": True})):
            ref_data = {
                "ref": element.get("data-ref"),
                "type": element.get("data-type", "text"),
                "reading_order": idx + 1,  # Assign based on DOM position
                "complexity": element.get("data-complexity", "simple"),
                "bbox": element.get("data-bbox"),  # Extract bounding box if present
            }
            references.append(ref_data)
        
        # Already in DOM order, no need to sort
        return references
    
    def _validate_skeleton(self, skeleton_html: str, references: list[dict]) -> list[str]:
        """Validate the skeleton structure and return warnings."""
        warnings = []
        
        # Check for empty references
        if not references:
            warnings.append("No data-ref elements found in skeleton")
        
        # Check for duplicate refs
        refs = [r["ref"] for r in references]
        duplicates = [r for r in refs if refs.count(r) > 1]
        if duplicates:
            warnings.append(f"Duplicate references found: {set(duplicates)}")
        
        # Check for basic structure
        soup = BeautifulSoup(skeleton_html, 'html.parser')
        page_div = soup.find("div", class_="page")
        if not page_div:
            warnings.append("Missing root <div class='page'> element")
        
        # Check for RTL/LTR direction
        if page_div and not page_div.get("dir"):
            warnings.append("No dir attribute on page element - direction unclear")
        
        return warnings
    
    def get_reference_list_for_extraction(self, references: list[dict]) -> str:
        """
        Format the reference list for the text extraction prompt.
        
        Returns a formatted string listing all refs and their types.
        """
        lines = ["The following references need content extraction:\n"]
        for ref in references:
            complexity = f" (complexity: {ref['complexity']})" if ref['type'] == 'math' else ""
            lines.append(f"- `{ref['ref']}`: {ref['type']}{complexity}")
        return "\n".join(lines)
