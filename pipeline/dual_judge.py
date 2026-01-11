"""
Dual Judge Module
Combines multiple judges for more accurate and robust evaluation.

Strategies:
1. Cross-Model: Uses both Gemini and GPT-4o to reduce model-specific biases
2. Specialist: Primary judge for general fidelity, secondary for equations
3. Consensus: Averages scores from both judges
4. Verification: Secondary judge validates when primary says "pass"
"""

import json
import base64
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import google.generativeai as genai

from config import (
    GOOGLE_API_KEY, 
    OPENAI_API_KEY,
    GEMINI_JUDGE_MODEL,
    OPENAI_JUDGE_MODEL,
    TARGET_SCORE,
)


# Configure Gemini API
genai.configure(api_key=GOOGLE_API_KEY)


# =============================================================================
# Prompts
# =============================================================================

GENERAL_JUDGE_PROMPT = """You are an expert QA Visual Engineer specializing in document fidelity assessment. Your task is to compare two images:

1. **Original**: A PDF page rendered as an image (the ground truth)
2. **Rendered**: An HTML page rendered as an image (the attempt to recreate the PDF)

## ⚠️ CRITICAL: VERIFY BEFORE CLAIMING ERRORS

Before reporting ANY error, you MUST:
1. **LOOK CAREFULLY** at BOTH images
2. **VERIFY** the issue actually exists in the rendered image
3. **DO NOT** assume something is wrong - check first!

Common FALSE POSITIVES to avoid:
- Claiming "single-column layout" when two columns ARE visible
- Claiming "missing header styling" when the header IS styled
- Claiming "text is missing" when the text IS present
- Reporting color issues when colors are actually similar

**If you're unsure, err on the side of scoring HIGHER and NOT reporting the error.**

## CRITICAL INSTRUCTIONS:
- TEXT ACCURACY IS THE MOST IMPORTANT CRITERION - all text must be present and correct
- Focus on ACTUAL visual differences, not imagined ones
- RTL (Right-to-Left) languages like Arabic are valid - text flowing right-to-left is CORRECT
- **IMPORTANT**: Identify what is CORRECT so it is not changed during refinement!

## ⚠️ IMPORTANT: Avoid False Positives
- The images may be at DIFFERENT RESOLUTIONS - this is expected, don't penalize for it
- If the rendered HTML shows ALL the text content, even at different scale, TEXT IS CORRECT
- Look at the CONTENT, not pixel-perfect matching
- DO NOT claim text is "missing" if you can see it in the rendered image
- DO NOT hallucinate errors - only report issues you can CLEARLY see

## ⚠️ CALIBRATED SCORING GUIDELINES (READ CAREFULLY):

### Text Accuracy (MOST IMPORTANT - weight 40%):
- **95-100**: All text present, correctly extracted, proper direction
- **85-94**: Minor issues (1-2 words unclear)
- **Below 85**: Missing text or significant errors

### Layout Score (weight 25%):
- **95-100**: Structure matches (same columns, sections in order, headers positioned)
- **90-94**: Minor spacing/positioning differences (ACCEPTABLE - don't penalize harshly)
- **85-89**: Noticeable but acceptable layout differences
- **Below 85**: Wrong column count, sections out of order, major structural issues

**IMPORTANT FOR LAYOUT**: If the structure is correct (right number of columns, sections in order, 
readable), score 90+. Don't penalize for:
- Slightly different margins
- Minor font size variations
- Resolution differences between images
- Small spacing differences
These are ACCEPTABLE variations.

### Color Match Score (weight 15%):
- **95-100**: Colors visually match (doesn't need to be exact hex match)
- **90-94**: Similar colors, readable, looks professional
- **85-89**: Some color differences but acceptable
- **Below 85**: Only if colors make text unreadable or look completely wrong

**IMPORTANT FOR COLORS**: If it looks professional and readable, score 90+. 
- Light blue header vs slightly different light blue = 95+
- White background with black text = 100 if original is same
- Don't penalize for minor shade differences!

### Equation Score (weight 20%):
- If NO mathematical equations exist → 100
- Regular text in any language is NOT equations

## Detailed Evaluation Criteria:

### 1. Text Accuracy Score (0-100) - MOST IMPORTANT
- Is ALL text from the original present in the HTML?
- Is the text correctly extracted (no missing words, paragraphs, or sections)?
- Is text direction correct? (RTL for Arabic/Hebrew/Farsi, LTR for English)
- Are there any OCR-like errors (wrong characters, merged words)?
- TEXT MUST BE PERFECT - this is the primary goal of the system

### 2. Layout Score (0-100)
- Does the HTML have the same column structure? (If yes → 90+ baseline)
- Are headers/titles positioned correctly?
- Are sections in the right order?
- Is the document READABLE and STRUCTURED correctly?
- **DO NOT** penalize for minor spacing or margin differences

### 3. Color Match Score (0-100)
- As long as colors are approximately similar, score 90+
- Only penalize significantly if colors make text unreadable
- Shade differences are ACCEPTABLE (score 95+ for minor shade differences)

### 4. Equation Score (0-100)
- If NO mathematical equations exist, score 100
- Regular text in any language is NOT equations

## CRITICAL: Identify What Is CORRECT (Positive Reinforcement)

You MUST identify elements that are working well. These should NOT be changed during refinement.
Be specific about what is correct:

Examples of correct_elements:
- "✓ Two-column layout structure is CORRECT - columns are properly aligned"
- "✓ Text direction (RTL) is CORRECT - Arabic text flows right-to-left properly"
- "✓ Header/title styling is CORRECT - font size and weight match original"
- "✓ Footer positioning is CORRECT - page numbers aligned properly"
- "✓ Font family choice is CORRECT - serif fonts match academic paper style"
- "✓ Equation rendering is CORRECT - MathJax properly displaying formulas"
- "✓ Color scheme is CORRECT - background and text colors match"

## CRITICAL: Provide Actionable Solutions for Errors

For each error, you MUST provide a specific CSS/HTML fix. Format:

"ERROR: [description] | FIX: [specific code solution]"

Examples:
- "ERROR: Text is left-to-right but should be RTL | FIX: Add dir='rtl' to the main container div and use text-align: right"
- "ERROR: Two-column layout is missing | FIX: Use CSS grid with grid-template-columns: 1fr 1fr or flexbox with flex-wrap"
- "ERROR: Header text is too small | FIX: Increase font-size to 24px for h1 elements"
- "ERROR: Arabic text not rendering correctly | FIX: Add lang='ar' attribute and use font-family: 'Arabic Typesetting', 'Traditional Arabic', serif"

## Output Format (STRICT JSON):
{
  "fidelity_score": <0-100>,
  "text_accuracy_score": <0-100>,
  "layout_score": <0-100>,
  "color_match_score": <0-100>,
  "equation_score": <0-100>,
  "correct_elements": [
    "✓ [what is working well - be specific]",
    "✓ [another correct element - be specific]"
  ],
  "critical_errors": [
    "ERROR: [problem description] | FIX: [specific HTML/CSS solution]",
    "ERROR: [problem description] | FIX: [specific HTML/CSS solution]"
  ]
}

## BEFORE SUBMITTING, DOUBLE-CHECK EACH ERROR:
For each error in critical_errors, ask yourself:
1. "Can I ACTUALLY see this issue in the rendered image, or am I assuming?"
2. "Is this a real problem or just a minor difference?"

If you cannot clearly point to the issue in the rendered image, REMOVE IT from the list.

**If the rendered HTML looks good overall (text present, layout reasonable, colors fine), 
set critical_errors to an EMPTY LIST [] and score 90+ in all categories.**

Return ONLY the JSON, no additional text.
"""


EQUATION_SPECIALIST_PROMPT = """You are a MATHEMATICS SPECIALIST QA Engineer. Your ONLY task is to evaluate how well mathematical equations are rendered.

## FIRST: Check if the document contains mathematical equations
Look for: formulas, fractions, integrals, summations, Greek letters in math context, algebraic expressions.

**If the document has NO mathematical equations (just regular text, even in Arabic or other languages), return:**
{
  "equation_fidelity_score": 100,
  "rendering_quality": 100,
  "symbol_accuracy": 100,
  "structure_accuracy": 100,
  "completeness": 100,
  "equation_errors": [],
  "ascii_art_detected": false,
  "equations_count_original": 0,
  "equations_count_rendered": 0,
  "has_equations": false
}

## If equations ARE present, evaluate:

### 1. Rendering Quality (0-100)
- Are equations rendered as proper typeset mathematics (like LaTeX/MathJax)?
- Or are they displayed as plain ASCII text (like "x^2" or "a/b")?

### 2. Symbol Accuracy (0-100)
- Subscripts, superscripts, fractions, Greek letters, operators

### 3. Structure Accuracy (0-100)
- Matrices aligned? Multi-line equations correct?

### 4. Completeness (0-100)
- Are ALL equations from the original present?

## Output Format (STRICT JSON):
{
  "equation_fidelity_score": <0-100>,
  "rendering_quality": <0-100>,
  "symbol_accuracy": <0-100>,
  "structure_accuracy": <0-100>,
  "completeness": <0-100>,
  "equation_errors": ["<error 1>", "<error 2>"],
  "ascii_art_detected": <true/false>,
  "equations_count_original": <number>,
  "equations_count_rendered": <number>,
  "has_equations": <true/false>
}

Return ONLY the JSON, no additional text.
"""


VERIFICATION_PROMPT = """You are a FINAL VERIFICATION judge. The document has already passed initial review.

Your job is a quick sanity check. Be REASONABLE - minor imperfections are acceptable.

## Scoring Guide:
- If the document looks 90%+ similar to original: verified=true, recommend "accept"
- If there are minor issues but it's usable: verified=true, recommend "accept"  
- Only recommend "reject" if there are MAJOR problems (missing sections, completely wrong layout)

Look for MAJOR issues only:
1. Missing large sections of content
2. Completely wrong layout (e.g., single column when should be two)
3. Unreadable text
4. Major color problems

## Output Format (STRICT JSON):
{
  "verified": <true/false>,
  "confidence": <0-100>,
  "issues_found": ["<issue 1>", "<issue 2>"],
  "recommendation": "accept" | "reject" | "needs_refinement"
}

Be LENIENT. If it looks reasonably close, accept it.
Return ONLY the JSON, no additional text.
"""


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class JudgeFeedback:
    """Structured feedback from a single judge."""
    fidelity_score: int
    critical_errors: list[str]
    layout_score: int
    text_accuracy_score: int
    color_match_score: int
    equation_score: int
    raw_response: str
    judge_name: str = "unknown"
    correct_elements: list[str] = field(default_factory=list)  # NEW: What's working well
    
    @property
    def passed(self) -> bool:
        from config import TARGET_SCORE
        return self.fidelity_score >= TARGET_SCORE
    
    def to_dict(self) -> dict:
        return {
            "fidelity_score": self.fidelity_score,
            "critical_errors": self.critical_errors,
            "correct_elements": self.correct_elements,  # NEW: Include positive feedback
            "layout_score": self.layout_score,
            "text_accuracy_score": self.text_accuracy_score,
            "color_match_score": self.color_match_score,
            "equation_score": self.equation_score,
            "judge_name": self.judge_name,
        }


@dataclass
class EquationFeedback:
    """Specialized feedback for equation evaluation."""
    equation_fidelity_score: int
    rendering_quality: int
    symbol_accuracy: int
    structure_accuracy: int
    completeness: int
    equation_errors: list[str]
    ascii_art_detected: bool
    raw_response: str
    has_equations: bool = True  # False if document has no equations
    
    def to_dict(self) -> dict:
        return {
            "equation_fidelity_score": self.equation_fidelity_score,
            "rendering_quality": self.rendering_quality,
            "ascii_art_detected": self.ascii_art_detected,
            "equation_errors": self.equation_errors,
            "has_equations": self.has_equations,
        }


@dataclass
class VerificationResult:
    """Result from verification judge."""
    verified: bool
    confidence: int
    issues_found: list[str]
    recommendation: str  # "accept", "reject", "needs_refinement"
    raw_response: str


@dataclass
class DualJudgeFeedback:
    """Combined feedback from dual-judge system."""
    # Combined scores (weighted average)
    fidelity_score: int
    layout_score: int
    text_accuracy_score: int
    color_match_score: int
    equation_score: int
    
    # All critical errors from all judges
    critical_errors: list[str]
    
    # NEW: Elements that are correct (positive reinforcement)
    correct_elements: list[str] = field(default_factory=list)
    
    # Individual judge results
    primary_feedback: Optional[JudgeFeedback] = None
    secondary_feedback: Optional[JudgeFeedback] = None
    equation_feedback: Optional[EquationFeedback] = None
    verification_result: Optional[VerificationResult] = None
    
    # Meta info
    judges_used: list[str] = field(default_factory=list)
    consensus_reached: bool = False
    
    @property
    def passed(self) -> bool:
        from config import TARGET_SCORE
        # Must pass fidelity AND not have ASCII art detected
        if self.equation_feedback and self.equation_feedback.ascii_art_detected:
            return False
        # If verification was done, respect its recommendation
        if self.verification_result:
            return self.verification_result.recommendation == "accept"
        return self.fidelity_score >= TARGET_SCORE
    
    def to_dict(self) -> dict:
        return {
            "fidelity_score": self.fidelity_score,
            "layout_score": self.layout_score,
            "text_accuracy_score": self.text_accuracy_score,
            "color_match_score": self.color_match_score,
            "equation_score": self.equation_score,
            "critical_errors": self.critical_errors,
            "correct_elements": self.correct_elements,  # NEW: Include positive feedback
            "judges_used": self.judges_used,
            "consensus_reached": self.consensus_reached,
            "ascii_art_detected": self.equation_feedback.ascii_art_detected if self.equation_feedback else False,
        }


# =============================================================================
# Dual Judge Implementation
# =============================================================================

class DualJudge:
    """
    Comprehensive dual-judge system combining multiple strategies:
    
    1. Cross-Model: Uses both Gemini and GPT-4o
    2. Specialist: Dedicated equation evaluator
    3. Consensus: Averages scores with configurable weights
    4. Verification: Final gate before accepting
    """
    
    def __init__(
        self,
        use_cross_model: bool = True,
        use_equation_specialist: bool = True,
        use_verification: bool = True,
        gemini_weight: float = 0.5,
        openai_weight: float = 0.5,
        equation_weight: float = 0.3,  # Extra weight for equation score
    ):
        self.use_cross_model = use_cross_model and OPENAI_API_KEY
        self.use_equation_specialist = use_equation_specialist
        self.use_verification = use_verification
        self.gemini_weight = gemini_weight
        self.openai_weight = openai_weight
        self.equation_weight = equation_weight
        
        # Initialize models
        self.gemini_model = genai.GenerativeModel(GEMINI_JUDGE_MODEL)
        
        if OPENAI_API_KEY:
            import openai
            self.openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        else:
            self.openai_client = None
            self.use_cross_model = False
    
    def compare(
        self, 
        original_image: str | Path, 
        rendered_image: str | Path
    ) -> DualJudgeFeedback:
        """
        Run comprehensive dual-judge evaluation.
        
        Args:
            original_image: Path or base64 of original PDF page
            rendered_image: Path or base64 of rendered HTML
            
        Returns:
            DualJudgeFeedback with combined scores and all feedback
        """
        original_b64 = self._load_image(original_image)
        rendered_b64 = self._load_image(rendered_image)
        
        judges_used = []
        
        # Step 1: Run primary judges (potentially in parallel)
        primary_feedback = self._run_gemini_judge(original_b64, rendered_b64, GENERAL_JUDGE_PROMPT)
        primary_feedback.judge_name = "gemini_primary"
        judges_used.append("gemini_primary")
        
        secondary_feedback = None
        if self.use_cross_model and self.openai_client:
            secondary_feedback = self._run_openai_judge(original_b64, rendered_b64, GENERAL_JUDGE_PROMPT)
            secondary_feedback.judge_name = "openai_secondary"
            judges_used.append("openai_secondary")
        
        # Step 2: Run equation specialist
        equation_feedback = None
        if self.use_equation_specialist:
            equation_feedback = self._run_equation_specialist(original_b64, rendered_b64)
            judges_used.append("equation_specialist")
        
        # Step 3: Calculate combined scores
        combined = self._combine_scores(primary_feedback, secondary_feedback, equation_feedback)
        
        # Step 4: Verification gate (if scores are high enough)
        verification_result = None
        preliminary_pass = combined["fidelity_score"] >= TARGET_SCORE
        
        if self.use_verification and preliminary_pass:
            verification_result = self._run_verification(original_b64, rendered_b64)
            judges_used.append("verification")
        
        # Step 5: Collect all critical errors
        all_errors = list(primary_feedback.critical_errors)
        if secondary_feedback:
            all_errors.extend([e for e in secondary_feedback.critical_errors if e not in all_errors])
        if equation_feedback:
            all_errors.extend([e for e in equation_feedback.equation_errors if e not in all_errors])
        if verification_result:
            all_errors.extend([e for e in verification_result.issues_found if e not in all_errors])
        
        # Step 6: Collect all correct elements (positive reinforcement)
        all_correct = list(primary_feedback.correct_elements)
        if secondary_feedback:
            all_correct.extend([c for c in secondary_feedback.correct_elements if c not in all_correct])
        
        # Check consensus
        consensus = True
        if secondary_feedback:
            score_diff = abs(primary_feedback.fidelity_score - secondary_feedback.fidelity_score)
            consensus = score_diff <= 15  # Within 15 points = consensus
        
        return DualJudgeFeedback(
            fidelity_score=combined["fidelity_score"],
            layout_score=combined["layout_score"],
            text_accuracy_score=combined["text_accuracy_score"],
            color_match_score=combined["color_match_score"],
            equation_score=combined["equation_score"],
            critical_errors=all_errors[:7],  # Limit to top 7
            correct_elements=all_correct,  # NEW: Include positive feedback
            primary_feedback=primary_feedback,
            secondary_feedback=secondary_feedback,
            equation_feedback=equation_feedback,
            verification_result=verification_result,
            judges_used=judges_used,
            consensus_reached=consensus,
        )
    
    def _combine_scores(
        self, 
        primary: JudgeFeedback, 
        secondary: Optional[JudgeFeedback],
        equation: Optional[EquationFeedback]
    ) -> dict:
        """Combine scores from all judges with weights."""
        
        if secondary:
            # Weighted average of both general judges
            w1, w2 = self.gemini_weight, self.openai_weight
            total = w1 + w2
            
            layout = int((primary.layout_score * w1 + secondary.layout_score * w2) / total)
            text = int((primary.text_accuracy_score * w1 + secondary.text_accuracy_score * w2) / total)
            color = int((primary.color_match_score * w1 + secondary.color_match_score * w2) / total)
            eq_general = int((primary.equation_score * w1 + secondary.equation_score * w2) / total)
        else:
            layout = primary.layout_score
            text = primary.text_accuracy_score
            color = primary.color_match_score
            eq_general = primary.equation_score
        
        # Handle equation scoring
        if equation:
            # If no equations in document, score is 100 (not applicable)
            if hasattr(equation, 'has_equations') and not equation.has_equations:
                eq_score = 100
            elif equation.equation_fidelity_score >= 95:
                # Specialist says equations are good
                eq_score = equation.equation_fidelity_score
            else:
                # Use specialist score, penalize ASCII art
                eq_score = equation.equation_fidelity_score
                if equation.ascii_art_detected:
                    eq_score = min(eq_score, 40)
        else:
            # No specialist, use general judge scores
            # If general judges give high scores, probably no complex equations
            eq_score = eq_general if eq_general > 0 else 100
        
        # If equation score seems wrong (low but no actual equation errors), boost it
        if equation and not equation.equation_errors and eq_score < 80:
            eq_score = 100  # No errors = no equations or equations are fine
        
        # Calculate fidelity with TEXT as highest priority
        # Text extraction is the primary goal - must be perfect
        # Layout is important but be reasonable
        # Color and equations are secondary
        fidelity = int(
            text * 0.50 +    # TEXT IS MOST IMPORTANT - 50%
            layout * 0.30 +  # Layout is important but reasonable - 30%
            color * 0.05 +   # Color is least important - 5%
            eq_score * 0.15  # Equations only matter if present - 15%
        )
        
        return {
            "fidelity_score": fidelity,
            "layout_score": layout,
            "text_accuracy_score": text,
            "color_match_score": color,
            "equation_score": eq_score,
        }
    
    def _run_gemini_judge(self, original_b64: str, rendered_b64: str, prompt: str) -> JudgeFeedback:
        """Run Gemini as a judge."""
        original_part = {"mime_type": "image/png", "data": original_b64}
        rendered_part = {"mime_type": "image/png", "data": rendered_b64}
        
        response = self.gemini_model.generate_content([
            "Here is the ORIGINAL PDF page:",
            original_part,
            "Here is the RENDERED HTML page:",
            rendered_part,
            prompt
        ])
        
        return self._parse_general_response(response.text)
    
    def _run_openai_judge(self, original_b64: str, rendered_b64: str, prompt: str) -> JudgeFeedback:
        """Run OpenAI GPT-4o as a judge."""
        response = self.openai_client.chat.completions.create(
            model=OPENAI_JUDGE_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Here is the ORIGINAL PDF page:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{original_b64}"}},
                    {"type": "text", "text": "Here is the RENDERED HTML page:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{rendered_b64}"}},
                    {"type": "text", "text": prompt}
                ]
            }],
            max_tokens=1000,
        )
        
        return self._parse_general_response(response.choices[0].message.content)
    
    def _run_equation_specialist(self, original_b64: str, rendered_b64: str) -> EquationFeedback:
        """Run equation specialist judge."""
        original_part = {"mime_type": "image/png", "data": original_b64}
        rendered_part = {"mime_type": "image/png", "data": rendered_b64}
        
        response = self.gemini_model.generate_content([
            "Here is the ORIGINAL PDF page:",
            original_part,
            "Here is the RENDERED HTML page:",
            rendered_part,
            EQUATION_SPECIALIST_PROMPT
        ])
        
        return self._parse_equation_response(response.text)
    
    def _run_verification(self, original_b64: str, rendered_b64: str) -> VerificationResult:
        """Run final verification judge."""
        # Use OpenAI for verification if available (different model = different perspective)
        if self.openai_client:
            response = self.openai_client.chat.completions.create(
                model=OPENAI_JUDGE_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Here is the ORIGINAL PDF page:"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{original_b64}"}},
                        {"type": "text", "text": "Here is the RENDERED HTML page:"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{rendered_b64}"}},
                        {"type": "text", "text": VERIFICATION_PROMPT}
                    ]
                }],
                max_tokens=500,
            )
            response_text = response.choices[0].message.content
        else:
            original_part = {"mime_type": "image/png", "data": original_b64}
            rendered_part = {"mime_type": "image/png", "data": rendered_b64}
            response = self.gemini_model.generate_content([
                "Here is the ORIGINAL PDF page:",
                original_part,
                "Here is the RENDERED HTML page:",
                rendered_part,
                VERIFICATION_PROMPT
            ])
            response_text = response.text
        
        return self._parse_verification_response(response_text)
    
    def _load_image(self, image: str | Path) -> str:
        """Load image as base64 string."""
        if isinstance(image, Path) or (isinstance(image, str) and Path(image).exists()):
            path = Path(image)
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        return image
    
    def _clean_json(self, text: str) -> str:
        """Clean JSON response from markdown."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
    
    def _parse_general_response(self, response_text: str) -> JudgeFeedback:
        """Parse general judge response."""
        try:
            data = json.loads(self._clean_json(response_text))
            return JudgeFeedback(
                fidelity_score=int(data.get("fidelity_score", 0)),
                critical_errors=data.get("critical_errors", []),
                correct_elements=data.get("correct_elements", []),  # NEW: Parse positive feedback
                layout_score=int(data.get("layout_score", 0)),
                text_accuracy_score=int(data.get("text_accuracy_score", 0)),
                color_match_score=int(data.get("color_match_score", 0)),
                equation_score=int(data.get("equation_score", 0)),
                raw_response=response_text,
            )
        except json.JSONDecodeError as e:
            return JudgeFeedback(
                fidelity_score=0,
                critical_errors=[f"Parse error: {e}"],
                correct_elements=[],  # NEW: Empty list on error
                layout_score=0,
                text_accuracy_score=0,
                color_match_score=0,
                equation_score=0,
                raw_response=response_text,
            )
    
    def _parse_equation_response(self, response_text: str) -> EquationFeedback:
        """Parse equation specialist response."""
        try:
            data = json.loads(self._clean_json(response_text))
            has_equations = data.get("has_equations", True)
            
            # If no equations, return perfect score
            if not has_equations:
                return EquationFeedback(
                    equation_fidelity_score=100,
                    rendering_quality=100,
                    symbol_accuracy=100,
                    structure_accuracy=100,
                    completeness=100,
                    equation_errors=[],
                    ascii_art_detected=False,
                    raw_response=response_text,
                    has_equations=False,
                )
            
            return EquationFeedback(
                equation_fidelity_score=int(data.get("equation_fidelity_score", 0)),
                rendering_quality=int(data.get("rendering_quality", 0)),
                symbol_accuracy=int(data.get("symbol_accuracy", 0)),
                structure_accuracy=int(data.get("structure_accuracy", 0)),
                completeness=int(data.get("completeness", 0)),
                equation_errors=data.get("equation_errors", []),
                ascii_art_detected=bool(data.get("ascii_art_detected", False)),
                raw_response=response_text,
                has_equations=True,
            )
        except json.JSONDecodeError:
            # On parse error, assume no equations (be lenient)
            return EquationFeedback(
                equation_fidelity_score=100,
                rendering_quality=100,
                symbol_accuracy=100,
                structure_accuracy=100,
                completeness=100,
                equation_errors=[],
                ascii_art_detected=False,
                raw_response=response_text,
                has_equations=False,
            )
    
    def _parse_verification_response(self, response_text: str) -> VerificationResult:
        """Parse verification response."""
        try:
            data = json.loads(self._clean_json(response_text))
            return VerificationResult(
                verified=bool(data.get("verified", False)),
                confidence=int(data.get("confidence", 0)),
                issues_found=data.get("issues_found", []),
                recommendation=data.get("recommendation", "needs_refinement"),
                raw_response=response_text,
            )
        except json.JSONDecodeError:
            return VerificationResult(
                verified=False,
                confidence=0,
                issues_found=["Failed to parse verification response"],
                recommendation="needs_refinement",
                raw_response=response_text,
            )
