"""
Staged Pipeline Runner

Orchestrates the full staged OCR pipeline:
1. Layout Extraction
2. Text Extraction  
3. Math Refinement (optional)
4. Assembly
5. Validation (optional)
"""

import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import base64

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import OUTPUT_DIR
from pipeline.ingestion import PDFIngestion

from .layout_extractor import LayoutExtractor, LayoutResult
from .text_extractor import TextExtractor, TextExtractionResult, MathRefiner
from .assembler import Assembler, AssemblyResult
from .judge import OCRJudge, JudgeVerdict, BatchJudge
from .cost_tracker import get_tracker, reset_tracker, CostTracker


@dataclass
class StageOutput:
    """Output from a single stage."""
    stage: str
    success: bool
    data: any
    duration_ms: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Complete result from the staged pipeline."""
    success: bool
    final_html: str
    stages: list[StageOutput]
    output_dir: Path
    total_duration_ms: float
    
    # Intermediate artifacts
    skeleton_html: str = ""
    content_json: dict = field(default_factory=dict)
    references: list[dict] = field(default_factory=list)
    
    # Cost tracking
    cost_usd: float = 0.0
    total_tokens: int = 0
    cost_breakdown: dict = field(default_factory=dict)


class StagedPipelineRunner:
    """
    Orchestrates the complete staged OCR pipeline.
    
    Stages:
    1. Layout Extraction - Analyze structure, output HTML skeleton
    2. Text Extraction - Extract content for each reference
    3. Math Refinement - Re-extract low-confidence equations (optional)
    4. Assembly - Merge skeleton + content into final HTML
    5. Validation - Compare against original (optional)
    """
    
    def __init__(
        self,
        output_dir: Optional[Path] = None,
        enable_math_refinement: bool = True,
        math_confidence_threshold: float = 0.8,
        enable_validation: bool = False,
    ):
        """
        Initialize the pipeline runner.
        
        Args:
            output_dir: Directory for outputs (default: config.OUTPUT_DIR)
            enable_math_refinement: Whether to refine low-confidence equations
            math_confidence_threshold: Threshold for triggering refinement
            enable_validation: Whether to run validation stage
        """
        self.output_dir = output_dir or OUTPUT_DIR
        self.enable_math_refinement = enable_math_refinement
        self.math_confidence_threshold = math_confidence_threshold
        self.enable_validation = enable_validation
        
        # Initialize components
        self.layout_extractor = LayoutExtractor()
        self.text_extractor = TextExtractor()
        self.math_refiner = MathRefiner() if enable_math_refinement else None
        self.assembler = Assembler()
    
    def process_pdf(
        self,
        pdf_path: str | Path,
        pages: Optional[list[int]] = None,
        run_name: Optional[str] = None,
    ) -> list[PipelineResult]:
        """
        Process a PDF document through the staged pipeline.
        
        Args:
            pdf_path: Path to the PDF file
            pages: List of page numbers to process (0-indexed), or None for all
            run_name: Optional name for this run
            
        Returns:
            List of PipelineResult, one per page
        """
        pdf_path = Path(pdf_path)
        
        # Create output directory
        run_suffix = run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self.output_dir / f"staged_{pdf_path.stem}_{run_suffix}"
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize PDF ingestion
        ingestion = PDFIngestion(pdf_path)
        
        # Determine pages to process
        if pages is None:
            pages = list(range(ingestion.page_count))
        
        results = []
        
        for page_num in pages:
            print(f"\n{'='*60}")
            print(f"Processing page {page_num + 1}/{len(pages)}")
            print(f"{'='*60}")
            
            # Extract page assets
            page_assets = ingestion.extract_page(page_num)
            
            # Save original page image at run level (for viewer compatibility)
            original_png_path = run_dir / f"page_{page_num:03d}.png"
            original_png_path.write_bytes(base64.b64decode(page_assets.page_image_base64))
            print(f"  ✓ Saved original page image: {original_png_path.name}")
            
            # Create page output directory
            page_dir = run_dir / f"page_{page_num:03d}"
            page_dir.mkdir(parents=True, exist_ok=True)
            
            # Run pipeline
            result = self.process_page(
                page_image_base64=page_assets.page_image_base64,
                output_dir=page_dir,
            )
            
            # Save outputs
            self._save_outputs(page_dir, result)
            
            results.append(result)
        
        return results
    
    def _process_single_page_job(
        self,
        job: dict,
    ) -> dict:
        """
        Process a single page job. Used for parallel execution.
        
        Args:
            job: Dict with page_num, page_image_base64, page_dir, run_dir
            
        Returns:
            Dict with page_num and result
        """
        page_num = job["page_num"]
        page_image_base64 = job["page_image_base64"]
        page_dir = job["page_dir"]
        run_dir = job["run_dir"]
        
        print(f"\n{'='*60}")
        print(f"[Page {page_num}] Starting processing...")
        print(f"{'='*60}")
        
        # Save original page image at run level
        original_png_path = run_dir / f"page_{page_num:03d}.png"
        if not original_png_path.exists():
            original_png_path.write_bytes(base64.b64decode(page_image_base64))
        
        # Create page output directory
        page_dir.mkdir(parents=True, exist_ok=True)
        
        # Run pipeline
        result = self.process_page(
            page_image_base64=page_image_base64,
            output_dir=page_dir,
        )
        
        # Save outputs
        self._save_outputs(page_dir, result)
        
        print(f"\n[Page {page_num}] ✓ Complete")
        
        return {"page_num": page_num, "result": result}
    
    async def process_pdf_async(
        self,
        pdf_path: str | Path,
        pages: Optional[list[int]] = None,
        run_name: Optional[str] = None,
        max_concurrent: int = 4,
    ) -> list[PipelineResult]:
        """
        Process a PDF document through the staged pipeline ASYNCHRONOUSLY.
        
        Pages are processed in parallel for speed, but results are returned
        in the correct page order.
        
        Args:
            pdf_path: Path to the PDF file
            pages: List of page numbers to process (0-indexed), or None for all
            run_name: Optional name for this run
            max_concurrent: Maximum number of pages to process concurrently
            
        Returns:
            List of PipelineResult, one per page (in order)
        """
        pdf_path = Path(pdf_path)
        
        # Create output directory
        run_suffix = run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self.output_dir / f"staged_{pdf_path.stem}_{run_suffix}"
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize PDF ingestion
        ingestion = PDFIngestion(pdf_path)
        
        # Determine pages to process
        if pages is None:
            pages = list(range(ingestion.page_count))
        
        print(f"\n{'='*60}")
        print(f"ASYNC PROCESSING: {len(pages)} pages (max {max_concurrent} concurrent)")
        print(f"{'='*60}")
        
        # Prepare all jobs upfront
        jobs = []
        for page_num in pages:
            page_assets = ingestion.extract_page(page_num)
            page_dir = run_dir / f"page_{page_num:03d}"
            
            jobs.append({
                "page_num": page_num,
                "page_image_base64": page_assets.page_image_base64,
                "page_dir": page_dir,
                "run_dir": run_dir,
            })
        
        # Process pages concurrently using ThreadPoolExecutor
        loop = asyncio.get_event_loop()
        results_dict = {}
        
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            # Submit all jobs
            futures = [
                loop.run_in_executor(executor, self._process_single_page_job, job)
                for job in jobs
            ]
            
            # Wait for all to complete
            completed = await asyncio.gather(*futures)
            
            # Collect results by page number
            for item in completed:
                results_dict[item["page_num"]] = item["result"]
        
        # Return results in correct page order
        results = [results_dict[page_num] for page_num in pages]
        
        print(f"\n{'='*60}")
        print(f"ASYNC COMPLETE: {len(results)} pages processed")
        print(f"{'='*60}")
        
        return results
    
    def process_pdf_with_validation(
        self,
        pdf_path: str | Path,
        pages: Optional[list[int]] = None,
        run_name: Optional[str] = None,
        max_retries: int = 2,
        pass_threshold: float = 0.85,
    ) -> dict:
        """
        Process a PDF with validation and automatic retry for failed pages.
        
        Args:
            pdf_path: Path to the PDF file
            pages: List of page numbers to process (0-indexed), or None for all
            run_name: Optional name for this run
            max_retries: Maximum retries for failed pages
            pass_threshold: Score threshold for passing validation
            
        Returns:
            Dict with results, validation stats, and retry info
        """
        pdf_path = Path(pdf_path)
        
        # Create output directory
        run_suffix = run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self.output_dir / f"staged_{pdf_path.stem}_{run_suffix}"
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        ingestion = PDFIngestion(pdf_path)
        judge = OCRJudge(pass_threshold=pass_threshold)
        
        # Determine pages to process
        if pages is None:
            pages = list(range(ingestion.page_count))
        
        # Track results and retries
        results = {}  # page_num -> PipelineResult
        verdicts = {}  # page_num -> JudgeVerdict
        retry_counts = {p: 0 for p in pages}
        page_images = {}  # Cache page images for validation
        
        # Process all pages first
        pages_to_process = list(pages)
        
        while pages_to_process:
            current_round = list(pages_to_process)
            pages_to_process = []  # Will be filled with failed pages
            
            for page_num in current_round:
                attempt = retry_counts[page_num] + 1
                attempt_str = f" (attempt {attempt})" if attempt > 1 else ""
                
                print(f"\n{'='*60}")
                print(f"Processing page {page_num + 1}{attempt_str}")
                print(f"{'='*60}")
                
                # Extract page assets (cache for validation)
                if page_num not in page_images:
                    page_assets = ingestion.extract_page(page_num)
                    page_images[page_num] = page_assets.page_image_base64
                    
                    # Save original page image
                    original_png_path = run_dir / f"page_{page_num:03d}.png"
                    original_png_path.write_bytes(base64.b64decode(page_assets.page_image_base64))
                
                page_image = page_images[page_num]
                
                # Create page output directory
                page_dir = run_dir / f"page_{page_num:03d}"
                page_dir.mkdir(parents=True, exist_ok=True)
                
                # Run pipeline
                result = self.process_page(
                    page_image_base64=page_image,
                    output_dir=page_dir,
                )
                
                # Save outputs
                self._save_outputs(page_dir, result)
                results[page_num] = result
                
                # Validate with judge
                print(f"\n[Validation] Judging page {page_num + 1}...", end=" ")
                verdict = judge.evaluate(
                    page_image_base64=page_image,
                    html_content=result.final_html,
                    page_number=page_num
                )
                verdicts[page_num] = verdict
                print(verdict)
                
                # Check if retry needed
                if verdict.needs_rerun and retry_counts[page_num] < max_retries:
                    retry_counts[page_num] += 1
                    pages_to_process.append(page_num)
                    print(f"    → Scheduling retry ({retry_counts[page_num]}/{max_retries})")
                    
                    # Log issues for debugging
                    for issue in verdict.issues:
                        print(f"    Issue: {issue.get('type', 'UNKNOWN')} - {issue.get('description', '')[:50]}")
        
        # Compile final stats
        passed_pages = [p for p, v in verdicts.items() if v.passed]
        failed_pages = [p for p, v in verdicts.items() if not v.passed]
        
        summary = {
            "run_dir": str(run_dir),
            "total_pages": len(pages),
            "passed": len(passed_pages),
            "failed": len(failed_pages),
            "pass_rate": len(passed_pages) / len(pages) if pages else 0,
            "passed_pages": passed_pages,
            "failed_pages": failed_pages,
            "retry_counts": {p: c for p, c in retry_counts.items() if c > 0},
            "results": results,
            "verdicts": verdicts,
        }
        
        # Print summary
        print(f"\n{'='*60}")
        print("VALIDATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total pages: {summary['total_pages']}")
        print(f"Passed: {summary['passed']} ({summary['pass_rate']*100:.1f}%)")
        print(f"Failed: {summary['failed']}")
        if failed_pages:
            print(f"Failed pages: {[p+1 for p in failed_pages]}")
        if summary['retry_counts']:
            print(f"Retries: {summary['retry_counts']}")
        
        # Save validation report
        report_path = run_dir / "validation_report.json"
        report_data = {
            "total_pages": summary["total_pages"],
            "passed": summary["passed"],
            "failed": summary["failed"],
            "pass_rate": summary["pass_rate"],
            "passed_pages": passed_pages,
            "failed_pages": failed_pages,
            "retry_counts": summary["retry_counts"],
            "verdicts": {
                str(p): {
                    "passed": v.passed,
                    "score": v.score,
                    "issues": v.issues,
                    "needs_rerun": v.needs_rerun
                }
                for p, v in verdicts.items()
            }
        }
        report_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False))
        print(f"\nValidation report saved: {report_path.name}")
        
        return summary

    def _process_page_with_validation_job(
        self,
        job: dict,
    ) -> dict:
        """
        Process a single page with validation. Used for parallel execution.
        
        Args:
            job: Dict with page_num, page_image_base64, page_dir, run_dir, judge, pass_threshold
            
        Returns:
            Dict with page_num, result, verdict
        """
        page_num = job["page_num"]
        page_image_base64 = job["page_image_base64"]
        page_dir = job["page_dir"]
        run_dir = job["run_dir"]
        judge = job["judge"]
        
        print(f"\n{'='*60}")
        print(f"[Page {page_num}] Starting processing...")
        print(f"{'='*60}")
        
        # Save original page image at run level
        original_png_path = run_dir / f"page_{page_num:03d}.png"
        if not original_png_path.exists():
            original_png_path.write_bytes(base64.b64decode(page_image_base64))
        
        # Create page output directory
        page_dir.mkdir(parents=True, exist_ok=True)
        
        # Run pipeline
        result = self.process_page(
            page_image_base64=page_image_base64,
            output_dir=page_dir,
        )
        
        # Save outputs
        self._save_outputs(page_dir, result)
        
        # Validate with judge
        print(f"[Page {page_num}] Validating...", end=" ")
        verdict = judge.evaluate(
            page_image_base64=page_image_base64,
            html_content=result.final_html,
            page_number=page_num
        )
        print(verdict)
        
        return {
            "page_num": page_num,
            "result": result,
            "verdict": verdict,
            "page_image_base64": page_image_base64,
        }

    async def process_pdf_with_validation_async(
        self,
        pdf_path: str | Path,
        pages: Optional[list[int]] = None,
        run_name: Optional[str] = None,
        max_retries: int = 2,
        pass_threshold: float = 0.85,
        max_concurrent: int = 4,
    ) -> dict:
        """
        Process a PDF with validation ASYNCHRONOUSLY.
        
        Pages are processed in parallel for speed. Failed pages are retried
        sequentially after the initial parallel pass.
        
        Args:
            pdf_path: Path to the PDF file
            pages: List of page numbers to process (0-indexed), or None for all
            run_name: Optional name for this run
            max_retries: Maximum retries for failed pages
            pass_threshold: Score threshold for passing validation
            max_concurrent: Maximum number of pages to process concurrently
            
        Returns:
            Dict with results, validation stats, and retry info
        """
        pdf_path = Path(pdf_path)
        
        # Create output directory
        run_suffix = run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self.output_dir / f"staged_{pdf_path.stem}_{run_suffix}"
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        ingestion = PDFIngestion(pdf_path)
        judge = OCRJudge(pass_threshold=pass_threshold)
        
        # Determine pages to process
        if pages is None:
            pages = list(range(ingestion.page_count))
        
        print(f"\n{'='*60}")
        print(f"ASYNC VALIDATED PROCESSING: {len(pages)} pages (max {max_concurrent} concurrent)")
        print(f"{'='*60}")
        
        # Track results and retries
        results = {}  # page_num -> PipelineResult
        verdicts = {}  # page_num -> JudgeVerdict
        retry_counts = {p: 0 for p in pages}
        page_images = {}  # Cache page images for validation
        
        # Prepare all jobs upfront
        jobs = []
        for page_num in pages:
            page_assets = ingestion.extract_page(page_num)
            page_images[page_num] = page_assets.page_image_base64
            page_dir = run_dir / f"page_{page_num:03d}"
            
            jobs.append({
                "page_num": page_num,
                "page_image_base64": page_assets.page_image_base64,
                "page_dir": page_dir,
                "run_dir": run_dir,
                "judge": judge,
            })
        
        # PHASE 1: Process all pages concurrently
        print(f"\n[Phase 1] Processing {len(jobs)} pages in parallel...")
        
        loop = asyncio.get_event_loop()
        
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = [
                loop.run_in_executor(executor, self._process_page_with_validation_job, job)
                for job in jobs
            ]
            completed = await asyncio.gather(*futures)
            
            for item in completed:
                page_num = item["page_num"]
                results[page_num] = item["result"]
                verdicts[page_num] = item["verdict"]
        
        # PHASE 2: Retry failed pages (sequentially to avoid overwhelming the API)
        failed_pages = [p for p, v in verdicts.items() if v.needs_rerun]
        
        for retry_round in range(max_retries):
            if not failed_pages:
                break
                
            print(f"\n[Phase 2] Retry round {retry_round + 1}: {len(failed_pages)} pages")
            
            pages_to_retry = list(failed_pages)
            failed_pages = []
            
            for page_num in pages_to_retry:
                retry_counts[page_num] += 1
                
                print(f"\n{'='*60}")
                print(f"[Page {page_num}] Retry {retry_counts[page_num]}/{max_retries}")
                print(f"{'='*60}")
                
                page_dir = run_dir / f"page_{page_num:03d}"
                
                # Re-process
                result = self.process_page(
                    page_image_base64=page_images[page_num],
                    output_dir=page_dir,
                )
                self._save_outputs(page_dir, result)
                results[page_num] = result
                
                # Re-validate
                verdict = judge.evaluate(
                    page_image_base64=page_images[page_num],
                    html_content=result.final_html,
                    page_number=page_num
                )
                verdicts[page_num] = verdict
                print(f"  Verdict: {verdict}")
                
                if verdict.needs_rerun:
                    failed_pages.append(page_num)
        
        # Compile final stats
        passed_pages = [p for p, v in verdicts.items() if v.passed]
        failed_pages = [p for p, v in verdicts.items() if not v.passed]
        
        summary = {
            "run_dir": str(run_dir),
            "total_pages": len(pages),
            "passed": len(passed_pages),
            "failed": len(failed_pages),
            "pass_rate": len(passed_pages) / len(pages) if pages else 0,
            "passed_pages": passed_pages,
            "failed_pages": failed_pages,
            "retry_counts": {p: c for p, c in retry_counts.items() if c > 0},
            "results": results,
            "verdicts": verdicts,
        }
        
        # Print summary
        print(f"\n{'='*60}")
        print("ASYNC VALIDATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total pages: {summary['total_pages']}")
        print(f"Passed: {summary['passed']} ({summary['pass_rate']*100:.1f}%)")
        print(f"Failed: {summary['failed']}")
        if failed_pages:
            print(f"Failed pages: {[p+1 for p in failed_pages]}")
        if summary['retry_counts']:
            print(f"Retries: {summary['retry_counts']}")
        
        # Save validation report
        report_path = run_dir / "validation_report.json"
        report_data = {
            "total_pages": summary["total_pages"],
            "passed": summary["passed"],
            "failed": summary["failed"],
            "pass_rate": summary["pass_rate"],
            "passed_pages": passed_pages,
            "failed_pages": failed_pages,
            "retry_counts": summary["retry_counts"],
            "verdicts": {
                str(p): {
                    "passed": v.passed,
                    "score": v.score,
                    "issues": v.issues,
                    "needs_rerun": v.needs_rerun
                }
                for p, v in verdicts.items()
            }
        }
        report_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False))
        print(f"\nValidation report saved: {report_path.name}")
        
        return summary

    def process_page(
        self,
        page_image_base64: str,
        output_dir: Optional[Path] = None,
    ) -> PipelineResult:
        """
        Process a single page through the staged pipeline.
        
        Args:
            page_image_base64: Base64-encoded PNG of the page
            output_dir: Optional directory for outputs
            
        Returns:
            PipelineResult with all stage outputs
        """
        import time
        
        # Reset cost tracker for this page
        reset_tracker()
        
        stages = []
        total_start = time.time()
        
        # ================================================================
        # STAGE 1: Layout Extraction
        # ================================================================
        print("\n[Stage 1] Layout Extraction...")
        stage_start = time.time()
        
        try:
            layout_result = self.layout_extractor.extract(page_image_base64)
            layout_success = True
            print(f"  ✓ Found {len(layout_result.references)} content references")
            if layout_result.warnings:
                print(f"  ⚠ Warnings: {layout_result.warnings}")
        except Exception as e:
            layout_result = LayoutResult(
                skeleton_html="<div class='page'><p class='error'>Layout extraction failed</p></div>",
                references=[],
                confidence=0.0,
                warnings=[str(e)]
            )
            layout_success = False
            print(f"  ✗ Error: {e}")
        
        stages.append(StageOutput(
            stage="layout_extraction",
            success=layout_success,
            data=layout_result,
            duration_ms=(time.time() - stage_start) * 1000,
            warnings=layout_result.warnings
        ))
        
        if not layout_success:
            return self._create_failed_result(stages, output_dir, total_start)
        
        # ================================================================
        # STAGE 2: Text Extraction
        # ================================================================
        print("\n[Stage 2] Text Extraction...")
        stage_start = time.time()
        
        try:
            text_result = self.text_extractor.extract(
                page_image_base64,
                layout_result.references
            )
            text_success = "_error" not in text_result.content
            print(f"  ✓ Extracted content for {len(text_result.content)} references")
            print(f"  ✓ Confidence: {text_result.confidence:.2f}")
            if text_result.low_confidence_refs:
                print(f"  ⚠ Low confidence: {text_result.low_confidence_refs}")
        except Exception as e:
            text_result = TextExtractionResult(
                content={"_error": str(e)},
                confidence=0.0,
                warnings=[str(e)]
            )
            text_success = False
            print(f"  ✗ Error: {e}")
        
        stages.append(StageOutput(
            stage="text_extraction",
            success=text_success,
            data=text_result,
            duration_ms=(time.time() - stage_start) * 1000,
            warnings=text_result.warnings
        ))
        
        # ================================================================
        # STAGE 2.5: Math Refinement (Optional)
        # ================================================================
        if self.enable_math_refinement and text_success:
            # Find equations needing refinement
            equations_to_refine = self._identify_equations_for_refinement(
                layout_result.references,
                text_result
            )
            
            if equations_to_refine:
                print(f"\n[Stage 2.5] Math Refinement for {len(equations_to_refine)} equations...")
                stage_start = time.time()
                
                try:
                    refined = self.math_refiner.refine(
                        page_image_base64,
                        equations_to_refine,
                        text_result.content
                    )
                    
                    # Merge refined equations back into content
                    for ref, data in refined.items():
                        text_result.content[ref] = data
                    
                    print(f"  ✓ Refined {len(refined)} equations")
                    
                    stages.append(StageOutput(
                        stage="math_refinement",
                        success=True,
                        data=refined,
                        duration_ms=(time.time() - stage_start) * 1000,
                    ))
                except Exception as e:
                    print(f"  ⚠ Refinement failed: {e}")
                    stages.append(StageOutput(
                        stage="math_refinement",
                        success=False,
                        data={},
                        duration_ms=(time.time() - stage_start) * 1000,
                        warnings=[str(e)]
                    ))
        
        # ================================================================
        # STAGE 2.9: Validate Reference Coverage
        # ================================================================
        print("\n[Stage 2.9] Validating extraction coverage...")
        expected_refs = {r["ref"] for r in layout_result.references}
        actual_refs = {k for k in text_result.content.keys() if not k.startswith("_")}
        
        missing_refs = expected_refs - actual_refs
        extra_refs = actual_refs - expected_refs
        
        if missing_refs:
            print(f"  ⚠ Missing content for: {missing_refs}")
            # Add placeholder error entries for missing refs
            for ref in missing_refs:
                text_result.content[ref] = {
                    "type": "error",
                    "error": f"Content not extracted for {ref}"
                }
        
        if extra_refs:
            print(f"  ⚠ Unexpected refs in content: {extra_refs}")
        
        coverage_pct = len(actual_refs & expected_refs) / len(expected_refs) * 100 if expected_refs else 100
        print(f"  ✓ Coverage: {coverage_pct:.0f}% ({len(actual_refs & expected_refs)}/{len(expected_refs)} refs)")
        
        # ================================================================
        # STAGE 3: Assembly
        # ================================================================
        print("\n[Stage 3] Assembly...")
        stage_start = time.time()
        
        try:
            assembly_result = self.assembler.assemble(
                layout_result.skeleton_html,
                text_result.content
            )
            print(f"  ✓ Assembly complete")
            if assembly_result.errors:
                print(f"  ⚠ Errors: {assembly_result.errors}")
        except Exception as e:
            assembly_result = AssemblyResult(
                html="<html><body><p>Assembly failed</p></body></html>",
                success=False,
                errors=[str(e)]
            )
            print(f"  ✗ Error: {e}")
        
        stages.append(StageOutput(
            stage="assembly",
            success=assembly_result.success,
            data=assembly_result,
            duration_ms=(time.time() - stage_start) * 1000,
            warnings=assembly_result.errors
        ))
        
        # ================================================================
        # Calculate total time and return result
        # ================================================================
        total_duration = (time.time() - total_start) * 1000
        
        # Get cost tracking data
        tracker = get_tracker()
        cost_data = tracker.to_dict()
        
        print(f"\n{'='*60}")
        print(f"Pipeline complete in {total_duration:.0f}ms")
        print(f"Cost: ${tracker.total_cost:.4f} ({tracker.total_tokens:,} tokens)")
        print(f"{'='*60}")
        
        return PipelineResult(
            success=assembly_result.success,
            final_html=assembly_result.html,
            stages=stages,
            output_dir=output_dir,
            total_duration_ms=total_duration,
            skeleton_html=layout_result.skeleton_html,
            content_json=text_result.content,
            references=layout_result.references,
            cost_usd=tracker.total_cost,
            total_tokens=tracker.total_tokens,
            cost_breakdown=cost_data,
        )
    
    def process_image(
        self,
        image_path: str | Path,
        output_dir: Optional[Path] = None,
        run_name: Optional[str] = None,
    ) -> PipelineResult:
        """
        Process a single image file through the pipeline.
        
        Args:
            image_path: Path to PNG/JPG image
            output_dir: Optional output directory
            run_name: Optional name for this run
            
        Returns:
            PipelineResult
        """
        image_path = Path(image_path)
        
        # Create output directory
        if output_dir is None:
            run_suffix = run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = self.output_dir / f"staged_{image_path.stem}_{run_suffix}"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load and encode image
        with open(image_path, "rb") as f:
            image_data = f.read()
        
        image_base64 = base64.b64encode(image_data).decode("utf-8")
        
        # Run pipeline
        result = self.process_page(image_base64, output_dir)
        
        # Save outputs
        self._save_outputs(output_dir, result)
        
        return result
    
    def _identify_equations_for_refinement(
        self,
        references: list[dict],
        text_result: TextExtractionResult
    ) -> list[str]:
        """Identify equations that need refinement."""
        equations_to_refine = []
        
        for ref_info in references:
            ref = ref_info["ref"]
            
            # Check if it's a math type
            if ref_info.get("type") != "math":
                continue
            
            # Check if complex
            is_complex = ref_info.get("complexity") == "complex"
            
            # Check if low confidence
            content_data = text_result.content.get(ref, {})
            is_low_conf = ref in text_result.low_confidence_refs
            
            # Also check confidence in content itself
            if isinstance(content_data, dict):
                conf = content_data.get("confidence", 1.0)
                if conf < self.math_confidence_threshold:
                    is_low_conf = True
            
            if is_complex or is_low_conf:
                equations_to_refine.append(ref)
        
        return equations_to_refine
    
    def _create_failed_result(
        self,
        stages: list[StageOutput],
        output_dir: Optional[Path],
        start_time: float
    ) -> PipelineResult:
        """Create a failed result when early stages fail."""
        import time
        
        return PipelineResult(
            success=False,
            final_html="<html><body><p>Pipeline failed - see stage outputs</p></body></html>",
            stages=stages,
            output_dir=output_dir,
            total_duration_ms=(time.time() - start_time) * 1000,
        )
    
    def _save_outputs(self, output_dir: Path, result: PipelineResult):
        """Save all pipeline outputs to disk."""
        # Save skeleton HTML
        skeleton_path = output_dir / "skeleton.html"
        skeleton_path.write_text(result.skeleton_html, encoding="utf-8")
        
        # Save content JSON
        content_path = output_dir / "content.json"
        content_path.write_text(
            json.dumps(result.content_json, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        
        # Save references
        refs_path = output_dir / "references.json"
        refs_path.write_text(
            json.dumps(result.references, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        
        # Save final HTML
        final_path = output_dir / "final.html"
        final_path.write_text(result.final_html, encoding="utf-8")
        
        # Save stage summary
        summary = {
            "success": result.success,
            "total_duration_ms": result.total_duration_ms,
            "cost_usd": result.cost_usd,
            "total_tokens": result.total_tokens,
            "cost_breakdown": result.cost_breakdown,
            "stages": [
                {
                    "stage": s.stage,
                    "success": s.success,
                    "duration_ms": s.duration_ms,
                    "warnings": s.warnings,
                }
                for s in result.stages
            ]
        }
        summary_path = output_dir / "summary.json"
        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        
        print(f"\nOutputs saved to: {output_dir}")
        print(f"  - skeleton.html (Stage 1 output)")
        print(f"  - content.json (Stage 2 output)")
        print(f"  - references.json (Reference list)")
        print(f"  - final.html (Assembled output)")
        print(f"  - summary.json (Pipeline summary)")


def main():
    """Command-line entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Staged OCR Pipeline - Process documents with separate layout/text extraction"
    )
    parser.add_argument(
        "input",
        help="Path to PDF or image file"
    )
    parser.add_argument(
        "--pages",
        type=str,
        default=None,
        help="Page numbers to process (e.g., '0,1,2' or '0-5')"
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Name for this run"
    )
    parser.add_argument(
        "--no-math-refinement",
        action="store_true",
        help="Disable math refinement stage"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory"
    )
    
    args = parser.parse_args()
    
    # Parse pages
    pages = None
    if args.pages:
        if "-" in args.pages:
            start, end = args.pages.split("-")
            pages = list(range(int(start), int(end) + 1))
        else:
            pages = [int(p) for p in args.pages.split(",")]
    
    # Create runner
    runner = StagedPipelineRunner(
        output_dir=Path(args.output_dir) if args.output_dir else None,
        enable_math_refinement=not args.no_math_refinement,
    )
    
    # Process input
    input_path = Path(args.input)
    
    if input_path.suffix.lower() == ".pdf":
        results = runner.process_pdf(input_path, pages=pages, run_name=args.run_name)
        print(f"\nProcessed {len(results)} pages")
    else:
        result = runner.process_image(input_path, run_name=args.run_name)
        print(f"\nProcessed image: {'✓ Success' if result.success else '✗ Failed'}")


if __name__ == "__main__":
    main()
