"""
Judge Module - Validates OCR output quality

Compares the original page image against the generated HTML
to detect issues like truncated text, flipped columns, 
incorrect extraction, and missing content.
"""

import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import google.generativeai as genai

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import GOOGLE_API_KEY, GENERATOR_MODEL
from .cost_tracker import get_tracker, extract_usage_from_response


genai.configure(api_key=GOOGLE_API_KEY)


@dataclass
class JudgeVerdict:
    """Result from the judge evaluation."""
    passed: bool
    score: float  # 0.0 to 1.0
    issues: list[dict] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    needs_rerun: bool = False
    
    def __str__(self):
        status = "✓ PASS" if self.passed else "✗ FAIL"
        return f"{status} (score: {self.score:.2f}, issues: {len(self.issues)})"


class OCRJudge:
    """
    Validates OCR output by comparing original image to generated HTML.
    
    Detects:
    - Truncated text (content cut off)
    - Flipped/swapped columns
    - Missing content blocks
    - Incorrect text extraction
    - Reading order issues
    """
    
    def __init__(
        self, 
        model_name: str = None, 
        pass_threshold: float = 0.85,
        fail_on_error: bool = False
    ):
        """
        Initialize the judge.
        
        Args:
            model_name: LLM model to use for validation
            pass_threshold: Score threshold for passing (0.0-1.0)
            fail_on_error: If True, raise exception when judge fails. 
                          If False, return cautious pass (legacy behavior).
        """
        self.model_name = model_name or GENERATOR_MODEL
        self.model = genai.GenerativeModel(self.model_name)
        self.pass_threshold = pass_threshold
        self.fail_on_error = fail_on_error
        self.prompt = self._build_prompt()
    
    def _build_prompt(self) -> str:
        return '''You are an OCR quality validator. Compare the original document image to the HTML text output and identify any issues.

## Your Task

Analyze both inputs and check for these specific issues:

### Critical Issues (require re-run)
1. **TRUNCATED_TEXT**: Text that is cut off mid-sentence or mid-word
2. **MISSING_COLUMN**: An entire column of text is missing from the output
3. **SWAPPED_COLUMNS**: Left and right column content is swapped (reading order wrong)
4. **MISSING_SECTION**: A major section (heading + content) is missing
5. **GARBLED_TEXT**: Text is present but completely unreadable/corrupted

### Minor Issues (acceptable)
6. **MINOR_TYPO**: Small spelling differences (1-2 characters)
7. **FORMATTING_DIFF**: Minor formatting differences (bold, spacing)
8. **DIACRITICS_MISSING**: Arabic diacritical marks (tashkeel) missing

## Output Format

Return a JSON object:

```json
{
  "score": 0.95,
  "passed": true,
  "issues": [
    {
      "type": "MINOR_TYPO",
      "severity": "low",
      "location": "paragraph 2",
      "description": "Word 'الماء' appears as 'الما'"
    }
  ],
  "suggestions": [
    "Consider re-extracting the footer section"
  ],
  "needs_rerun": false
}
```

## Scoring Guidelines

- 1.0: Perfect match
- 0.9-0.99: Minor issues only (typos, formatting)
- 0.7-0.89: Some content issues but mostly correct
- 0.5-0.69: Significant issues (missing paragraphs, partial truncation)
- 0.0-0.49: Major issues (missing columns, completely wrong content)

Set `needs_rerun: true` if ANY critical issue is found.

## Important

- Focus on CONTENT accuracy, not visual styling
- For RTL documents, verify right column comes before left column
- Check that all visible text in the image appears in the HTML
- Ignore page numbers and minor header/footer differences

Output ONLY the JSON object, no explanations.'''

    def evaluate(
        self,
        page_image_base64: str,
        html_content: str,
        page_number: int = 0
    ) -> JudgeVerdict:
        """
        Evaluate the quality of OCR output.
        
        Args:
            page_image_base64: Base64-encoded PNG of the original page
            html_content: The generated HTML content
            page_number: Page number for logging
            
        Returns:
            JudgeVerdict with pass/fail and detailed issues
        """
        # Prepare inputs
        image_part = {
            "mime_type": "image/png",
            "data": page_image_base64
        }
        
        # Build evaluation prompt
        eval_prompt = f'''{self.prompt}

## HTML Content to Validate

```html
{html_content}
```

Analyze the image and HTML above. Return your evaluation as JSON.'''

        # Retry logic
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                response = self.model.generate_content(
                    [eval_prompt, image_part],
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
                    raise ValueError("Empty response from API")
                
                # Track cost
                input_tokens, output_tokens = extract_usage_from_response(response)
                get_tracker().add_call(
                    stage="judge",
                    model=self.model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    duration_ms=duration_ms
                )
                
                # Parse response
                verdict = self._parse_response(response.text)
                return verdict
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                if "finish_reason" in error_msg or "safety" in error_msg.lower():
                    print(f"    ⚠ Judge API error, retrying ({attempt + 1}/{max_retries})...")
                    time.sleep(1)
                else:
                    raise
        
        # All retries failed
        if self.fail_on_error:
            raise Exception(f"Judge failed after {max_retries} attempts: {last_error}")
        
        # Legacy behavior: return cautious pass but mark as needing rerun
        print(f"    ⚠ Judge failed after {max_retries} attempts, returning uncertain verdict")
        return JudgeVerdict(
            passed=False,  # Don't assume pass - be conservative
            score=0.5,
            issues=[{"type": "JUDGE_ERROR", "description": str(last_error)}],
            needs_rerun=True  # Flag for retry
        )
    
    def _parse_response(self, response_text: str) -> JudgeVerdict:
        """Parse the JSON response into a JudgeVerdict."""
        text = response_text.strip()
        
        # Clean markdown if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            # Try to repair common JSON issues
            import re
            
            # Try to extract JSON object from response
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                json_text = match.group()
                try:
                    data = json.loads(json_text)
                except json.JSONDecodeError:
                    # Try to fix common issues
                    # 1. Remove trailing commas before }
                    json_text = re.sub(r',\s*}', '}', json_text)
                    json_text = re.sub(r',\s*]', ']', json_text)
                    
                    # 2. Try to close unclosed strings/objects
                    try:
                        data = json.loads(json_text)
                    except json.JSONDecodeError:
                        # Give up and return uncertain verdict
                        print(f"    ⚠ Judge JSON parse failed: {str(e)[:50]}")
                        return JudgeVerdict(
                            passed=False,  # Conservative - don't assume pass
                            score=0.5,
                            issues=[{"type": "PARSE_ERROR", "description": str(e)}],
                            needs_rerun=True  # Flag for retry
                        )
            else:
                # No JSON found - return uncertain verdict
                print(f"    ⚠ No JSON found in judge response")
                return JudgeVerdict(
                    passed=False,  # Conservative - don't assume pass
                    score=0.5,
                    issues=[{"type": "PARSE_ERROR", "description": "No JSON in response"}],
                    needs_rerun=True  # Flag for retry
                )
        
        score = float(data.get("score", 0.8))
        # ALWAYS use our threshold - don't trust LLM's passed field
        passed = score >= self.pass_threshold
        
        return JudgeVerdict(
            passed=passed,
            score=score,
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
            needs_rerun=data.get("needs_rerun", not passed)
        )


class BatchJudge:
    """
    Evaluates multiple pages and identifies which need re-processing.
    """
    
    def __init__(self, pass_threshold: float = 0.85):
        self.judge = OCRJudge(pass_threshold=pass_threshold)
        self.results: dict[int, JudgeVerdict] = {}
    
    def evaluate_batch(
        self,
        pages: list[dict]  # List of {page_num, image_base64, html_content}
    ) -> dict:
        """
        Evaluate a batch of pages.
        
        Returns:
            Dict with 'passed', 'failed', and 'verdicts'
        """
        passed = []
        failed = []
        
        for page_data in pages:
            page_num = page_data["page_num"]
            print(f"  Judging page {page_num + 1}...", end=" ")
            
            verdict = self.judge.evaluate(
                page_image_base64=page_data["image_base64"],
                html_content=page_data["html_content"],
                page_number=page_num
            )
            
            self.results[page_num] = verdict
            print(verdict)
            
            if verdict.needs_rerun:
                failed.append({
                    "page_num": page_num,
                    "verdict": verdict,
                    "issues": verdict.issues
                })
            else:
                passed.append(page_num)
        
        return {
            "total": len(pages),
            "passed": passed,
            "failed": failed,
            "pass_rate": len(passed) / len(pages) if pages else 0,
            "verdicts": self.results
        }
    
    def get_pages_needing_rerun(self) -> list[int]:
        """Get list of page numbers that need re-processing."""
        return [
            page_num 
            for page_num, verdict in self.results.items() 
            if verdict.needs_rerun
        ]
    
    def get_issues_summary(self) -> dict:
        """Get summary of all issues found."""
        issue_counts = {}
        for verdict in self.results.values():
            for issue in verdict.issues:
                issue_type = issue.get("type", "UNKNOWN")
                issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
        return issue_counts
