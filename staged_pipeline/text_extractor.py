"""
Text Extractor Module (Stage 2)

Extracts actual content for each reference identified in the layout skeleton.
Returns a JSON mapping of references to their content.
"""

import json
import re
import time
from pathlib import Path
from dataclasses import dataclass, field
import google.generativeai as genai

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import GOOGLE_API_KEY, GENERATOR_MODEL
from .cost_tracker import get_tracker, extract_usage_from_response


# Configure Gemini API
genai.configure(api_key=GOOGLE_API_KEY)


@dataclass
class TextExtractionResult:
    """Result from text extraction."""
    content: dict  # Mapping of ref -> content data
    confidence: float = 1.0
    low_confidence_refs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class TextExtractor:
    """
    Stage 2: Extract content for each reference.
    
    Takes the list of references from the layout stage and extracts
    the actual text/math/table content for each.
    """
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name or GENERATOR_MODEL
        self.model = genai.GenerativeModel(self.model_name)
        self.prompt_template = self._load_prompt()
    
    def _load_prompt(self) -> str:
        """Load the text extraction prompt from file."""
        prompt_path = Path(__file__).parent / "prompts" / "text_prompt.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        else:
            raise FileNotFoundError(f"Text prompt not found: {prompt_path}")
    
    def extract(
        self, 
        page_image_base64: str, 
        references: list[dict]
    ) -> TextExtractionResult:
        """
        Extract content for each reference from the page image.
        
        Args:
            page_image_base64: Base64-encoded PNG of the page
            references: List of reference dicts from layout stage
            
        Returns:
            TextExtractionResult with content mapping
        """
        # Format the reference list for the prompt
        reference_list = self._format_reference_list(references)
        
        # Build the full prompt
        prompt = self.prompt_template.replace("{reference_list}", reference_list)
        
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
                    [prompt, image_part],
                    generation_config={
                        "temperature": 0.0,  # Zero temperature for maximum consistency
                        "max_output_tokens": 65536,  # Max for gemini-3-flash-preview
                        "response_mime_type": "application/json",  # Force JSON output (no reasoning)
                    },
                    request_options={"timeout": 180}  # 3 minute timeout for large pages
                )
                duration_ms = (time.time() - start_time) * 1000
                
                # Check for valid response
                if not response.candidates or not response.candidates[0].content.parts:
                    finish_reason = response.candidates[0].finish_reason if response.candidates else "UNKNOWN"
                    raise ValueError(f"Empty response from API (finish_reason: {finish_reason})")
                
                # Check for truncation
                response_text = response.text
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'finish_reason'):
                        finish_reason = str(candidate.finish_reason)
                        if 'MAX_TOKENS' in finish_reason or 'LENGTH' in finish_reason:
                            print(f"  ⚠ Response was truncated (finish_reason: {finish_reason})")
                
                # Track cost
                input_tokens, output_tokens = extract_usage_from_response(response)
                get_tracker().add_call(
                    stage="text_extraction",
                    model=self.model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    duration_ms=duration_ms
                )
                
                # Parse the JSON response
                content = self._parse_response(response_text)
                
                # Identify low-confidence extractions
                low_confidence_refs = self._identify_low_confidence(content)
                
                # Validate coverage
                warnings = self._validate_coverage(content, references)
                
                # Calculate overall confidence
                confidence = self._calculate_confidence(content, low_confidence_refs, warnings)
                
                return TextExtractionResult(
                    content=content,
                    confidence=confidence,
                    low_confidence_refs=low_confidence_refs,
                    warnings=warnings
                )
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                if "finish_reason" in error_msg or "safety" in error_msg.lower() or "Empty response" in error_msg:
                    print(f"    ⚠ API error, retrying ({attempt + 1}/{max_retries})...")
                    time.sleep(1)  # Brief pause before retry
                else:
                    # Non-retryable error
                    raise
        
        # All retries failed
        raise Exception(f"Text extraction failed after {max_retries} attempts: {last_error}")
    
    def _format_reference_list(self, references: list[dict]) -> str:
        """Format references for the prompt, including spatial context."""
        lines = []
        for ref in references:
            complexity = f" [complex]" if ref.get('complexity') == 'complex' else ""
            bbox = ref.get('bbox')
            location = f" at bbox={bbox}" if bbox else ""
            lines.append(f"- `{ref['ref']}`: type={ref['type']}{complexity}{location}")
        return "\n".join(lines)
    
    def _parse_response(self, response_text: str) -> dict:
        """Parse the JSON response from the LLM."""
        text = response_text.strip()
        
        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        
        if text.endswith("```"):
            text = text[:-3]
        
        text = text.strip()
        
        # Remove any LLM reasoning that might precede the JSON
        # Look for common patterns
        llm_prefixes = [
            r'^(?:Here is|Here\'s|Output:|Result:|The JSON:).*?\n',
            r'^(?:I\'ll|Let me|I will|I should).*?\n',
            r'^.*?(?=\{)',  # Anything before the first {
        ]
        for pattern in llm_prefixes[:2]:  # Don't apply the greedy one first
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        text = text.strip()
        
        # Find JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        
        if start != -1 and end > start:
            json_str = text[start:end]
            try:
                content = json.loads(json_str)
                # Sanitize all text content immediately after parsing
                return self._sanitize_extracted_content(content)
            except json.JSONDecodeError as e:
                # Try to fix common JSON issues
                return self._attempt_json_repair(json_str, e)
        
        return {"_error": "Failed to parse JSON response", "_raw": response_text}
    
    def _attempt_json_repair(self, json_str: str, error: json.JSONDecodeError) -> dict:
        """Attempt to repair common JSON issues."""
        original_str = json_str
        
        # Check if response was truncated (no closing brace)
        if not json_str.rstrip().endswith("}"):
            # Try to close the JSON properly
            # Count open braces and brackets
            open_braces = json_str.count("{") - json_str.count("}")
            open_brackets = json_str.count("[") - json_str.count("]")
            
            # Check if we're inside a string (look for unclosed quotes)
            # Simple heuristic: if odd number of unescaped quotes, add one
            quote_count = len(re.findall(r'(?<!\\)"', json_str))
            if quote_count % 2 == 1:
                json_str += '"'
            
            # Close any open structures
            json_str += "]" * open_brackets
            json_str += "}" * open_braces
            
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        
        # Try fixing unescaped backslashes (common with LaTeX)
        fixed = json_str.replace("\\", "\\\\")
        # But don't double-escape already escaped ones
        fixed = fixed.replace("\\\\\\\\", "\\\\")
        
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass
        
        # Try to extract whatever valid entries we can
        partial_content = self._extract_partial_json(original_str)
        if partial_content:
            partial_content["_warning"] = "Partial extraction - some content may be missing"
            return partial_content
        
        # Return error dict with more context
        return {
            "_error": f"JSON parse error: {error}",
            "_raw": original_str[:1000]
        }
    
    def _extract_partial_json(self, json_str: str) -> dict:
        """Try to extract valid entries from a partially valid JSON."""
        result = {}
        
        # Pattern to match complete JSON entries
        # Matches: "key": { ... }
        pattern = r'"([^"]+)":\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        
        matches = re.findall(pattern, json_str)
        
        # Try to extract each matched block
        for match in re.finditer(r'"([^"]+)":\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', json_str):
            key = match.group(1)
            value_str = match.group(2)
            try:
                value = json.loads(value_str)
                result[key] = value
            except json.JSONDecodeError:
                continue
        
        return result if result else None
    
    def _sanitize_extracted_content(self, content: dict) -> dict:
        """
        Sanitize all text content to remove LLM reasoning.
        
        This catches reasoning at extraction time, before it gets saved.
        """
        # Import sanitization function
        from .assembler import sanitize_content
        
        for ref, data in content.items():
            if ref.startswith("_"):
                continue
            
            if not isinstance(data, dict):
                continue
            
            # Sanitize main content field
            if "content" in data and isinstance(data["content"], str):
                sanitized = sanitize_content(data["content"])
                if sanitized != data["content"]:
                    data["content"] = sanitized
                    data["_sanitized"] = True  # Mark that we cleaned it
            
            # Sanitize segments in mixed content
            if "segments" in data and isinstance(data["segments"], list):
                for segment in data["segments"]:
                    if isinstance(segment, dict) and "content" in segment:
                        if segment.get("type") == "text":
                            segment["content"] = sanitize_content(segment["content"]) or ""
            
            # Sanitize label field (for equations)
            if "label" in data and isinstance(data["label"], str):
                data["label"] = sanitize_content(data["label"]) or data["label"]
            
            # Sanitize description field (for figures)
            if "description" in data and isinstance(data["description"], str):
                data["description"] = sanitize_content(data["description"]) or data["description"]
        
        return content
    
    def _identify_low_confidence(self, content: dict) -> list[str]:
        """Identify references with low confidence scores."""
        low_confidence = []
        
        for ref, data in content.items():
            if ref.startswith("_"):
                continue
                
            if isinstance(data, dict):
                conf = data.get("confidence", 1.0)
                if conf < 0.8:
                    low_confidence.append(ref)
        
        return low_confidence
    
    def _validate_coverage(self, content: dict, references: list[dict]) -> list[str]:
        """Check that all references have content."""
        warnings = []
        
        expected_refs = {r["ref"] for r in references}
        actual_refs = {k for k in content.keys() if not k.startswith("_")}
        
        missing = expected_refs - actual_refs
        if missing:
            warnings.append(f"Missing content for references: {missing}")
        
        extra = actual_refs - expected_refs
        if extra:
            warnings.append(f"Unexpected references in output: {extra}")
        
        return warnings
    
    def _calculate_confidence(
        self, 
        content: dict, 
        low_confidence_refs: list[str],
        warnings: list[str]
    ) -> float:
        """Calculate overall extraction confidence."""
        if "_error" in content:
            return 0.0
        
        # Start with base confidence
        confidence = 1.0
        
        # Reduce for low-confidence refs
        if low_confidence_refs:
            ref_count = len([k for k in content.keys() if not k.startswith("_")])
            if ref_count > 0:
                confidence -= 0.1 * (len(low_confidence_refs) / ref_count)
        
        # Reduce for warnings
        confidence -= 0.05 * len(warnings)
        
        return max(0.0, min(1.0, confidence))


class MathRefiner:
    """
    Stage 2.5 (Optional): Refine complex equations.
    
    Re-examines equations that received low confidence scores
    and provides refined LaTeX.
    """
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name or GENERATOR_MODEL
        self.model = genai.GenerativeModel(self.model_name)
        self.prompt_template = self._load_prompt()
    
    def _load_prompt(self) -> str:
        """Load the math refinement prompt."""
        prompt_path = Path(__file__).parent / "prompts" / "math_refinement_prompt.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        else:
            raise FileNotFoundError(f"Math refinement prompt not found: {prompt_path}")
    
    def refine(
        self,
        page_image_base64: str,
        equation_refs: list[str],
        initial_content: dict
    ) -> dict:
        """
        Refine equations that need improvement.
        
        Args:
            page_image_base64: Base64-encoded PNG of the page
            equation_refs: List of equation refs to refine
            initial_content: Initial extraction results
            
        Returns:
            Dict with refined equation content
        """
        # Format equation refs and initial extraction
        eq_refs_str = "\n".join([f"- `{ref}`" for ref in equation_refs])
        
        initial_str = json.dumps(
            {ref: initial_content.get(ref, {}) for ref in equation_refs},
            indent=2,
            ensure_ascii=False
        )
        
        # Build prompt
        prompt = self.prompt_template.replace("{equation_refs}", eq_refs_str)
        prompt = prompt.replace("{initial_extraction}", initial_str)
        
        # Prepare image
        image_part = {
            "mime_type": "image/png",
            "data": page_image_base64
        }
        
        # Retry logic for math refinement
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Call model with timing and timeout
                start_time = time.time()
                response = self.model.generate_content(
                    [prompt, image_part],
                    generation_config={
                        "temperature": 0.0,  # Zero for consistency
                        "max_output_tokens": 4096,
                        "response_mime_type": "application/json",
                    },
                    request_options={"timeout": 120}  # 2 minute timeout
                )
                duration_ms = (time.time() - start_time) * 1000
                
                # Check for valid response
                if not response.candidates or not response.candidates[0].content.parts:
                    raise ValueError("Empty response from math refinement API")
                
                # Track cost
                input_tokens, output_tokens = extract_usage_from_response(response)
                get_tracker().add_call(
                    stage="math_refinement",
                    model=self.model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    duration_ms=duration_ms
                )
                
                # Parse response
                return self._parse_response(response.text)
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                if "finish_reason" in error_msg or "safety" in error_msg.lower() or "Empty response" in error_msg:
                    print(f"      ⚠ Math refinement error, retrying ({attempt + 1}/{max_retries})...")
                    time.sleep(1)
                else:
                    raise
        
        # All retries failed - return empty dict (refinement is optional)
        print(f"      ⚠ Math refinement failed after {max_retries} attempts, skipping")
        return {}
    
    def _parse_response(self, response_text: str) -> dict:
        """Parse the JSON response."""
        text = response_text.strip()
        
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        text = text.strip()
        
        start = text.find("{")
        end = text.rfind("}") + 1
        
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        
        return {}
