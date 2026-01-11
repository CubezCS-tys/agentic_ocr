"""
OCR Pipeline Orchestrator
Coordinates the recursive feedback loop between Generator, Renderer, and Judge.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Union
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.table import Table

from config import (
    MAX_RETRIES, TARGET_SCORE, OUTPUT_DIR,
    USE_DUAL_JUDGE, USE_CROSS_MODEL, USE_EQUATION_SPECIALIST, USE_VERIFICATION,
    GEMINI_WEIGHT, OPENAI_WEIGHT, EQUATION_WEIGHT,
)
from .ingestion import PDFIngestion, PageAssets
from .generator import HTMLGenerator
from .renderer import HTMLRenderer
from .judge import VisualJudge, JudgeFeedback
from .dual_judge import DualJudge, DualJudgeFeedback


console = Console()


@dataclass
class IterationResult:
    """Result from a single iteration of the feedback loop."""
    iteration: int
    html: str
    rendered_image_path: Path
    feedback: Union[JudgeFeedback, DualJudgeFeedback]
    

@dataclass
class PageResult:
    """Final result for a processed page."""
    page_number: int
    success: bool
    final_html: str
    final_html_path: Path
    final_score: int
    iterations: int
    history: list[IterationResult] = field(default_factory=list)


class OCRPipeline:
    """
    Main pipeline orchestrator for RA-OCR.
    
    Implements the recursive feedback loop:
    1. [NEW] Analyze document to understand its characteristics
    2. Generate HTML from PDF page image (with custom prompt)
    3. Render HTML to image
    4. Judge compares original vs rendered
    5. If score < target, refine and repeat
    """
    
    def __init__(
        self,
        max_retries: int = MAX_RETRIES,
        target_score: int = TARGET_SCORE,
        verbose: bool = True,
        use_dual_judge: bool = USE_DUAL_JUDGE,
    ):
        self.max_retries = max_retries
        self.target_score = target_score
        self.verbose = verbose
        self.use_dual_judge = use_dual_judge
        
        # Initialize components
        self.generator = HTMLGenerator()
        self.renderer = HTMLRenderer()
        
        # Initialize judge (single or dual)
        if use_dual_judge:
            self.judge = DualJudge(
                use_cross_model=USE_CROSS_MODEL,
                use_equation_specialist=USE_EQUATION_SPECIALIST,
                use_verification=USE_VERIFICATION,
                gemini_weight=GEMINI_WEIGHT,
                openai_weight=OPENAI_WEIGHT,
                equation_weight=EQUATION_WEIGHT,
            )
            console.print("[dim]Using Dual-Judge System[/]")
        else:
            self.judge = VisualJudge()
            console.print("[dim]Using Single Judge[/]")
    
    def process_pdf(self, pdf_path: str | Path) -> list[PageResult]:
        """
        Process all pages of a PDF document.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of PageResult for each page
        """
        pdf_path = Path(pdf_path)
        results = []
        
        with PDFIngestion(pdf_path) as ingestion:
            console.print(f"\n[bold blue]Processing PDF:[/] {pdf_path.name}")
            console.print(f"[dim]Pages: {ingestion.page_count}[/]\n")
            
            for page_num in range(ingestion.page_count):
                result = self.process_page(ingestion, page_num)
                results.append(result)
        
        # Print summary
        self._print_summary(results)
        
        return results
    
    def _save_analysis(self, output_dir: Path):
        """Placeholder for backward compatibility - analysis phase removed."""
        pass
    
    def _print_analysis_results(self):
        """Placeholder for backward compatibility - analysis phase removed."""
        pass
    
    def process_page(
        self, 
        ingestion: PDFIngestion, 
        page_number: int
    ) -> PageResult:
        """
        Process a single page through the feedback loop.
        
        Args:
            ingestion: PDFIngestion instance
            page_number: Zero-indexed page number
            
        Returns:
            PageResult with final HTML and metrics
        """
        console.print(Panel(f"[bold]Processing Page {page_number + 1}[/]", expand=False))
        
        # Extract page
        with console.status("[bold green]Extracting page..."):
            page_assets = ingestion.extract_page(page_number)
        
        console.print(f"  [dim]Image: {page_assets.width}x{page_assets.height}px[/]")
        console.print(f"  [dim]Figures found: {len(page_assets.figures)}[/]")
        
        # Output directory for this page
        page_output_dir = ingestion.output_dir / f"page_{page_number:03d}"
        page_output_dir.mkdir(exist_ok=True)
        
        history: list[IterationResult] = []
        current_html: Optional[str] = None
        final_feedback: Optional[JudgeFeedback] = None
        
        for iteration in range(1, self.max_retries + 1):
            console.print(f"\n  [cyan]Iteration {iteration}/{self.max_retries}[/]")
            
            # Step A: Generate HTML
            with console.status("  [bold green]Generating HTML..."):
                if current_html is None:
                    # Initial generation
                    current_html = self.generator.generate_initial(
                        page_assets.page_image_base64,
                        page_assets.figures
                    )
                else:
                    # Refinement based on feedback
                    current_html = self.generator.refine(
                        current_html,
                        final_feedback.to_dict(),
                        page_assets.page_image_base64
                    )
            
            # Save intermediate HTML
            html_path = page_output_dir / f"iteration_{iteration:02d}.html"
            html_path.write_text(current_html, encoding="utf-8")
            
            # Step B: Render HTML
            with console.status("  [bold green]Rendering HTML..."):
                rendered_path = page_output_dir / f"rendered_{iteration:02d}.png"
                self.renderer.render_to_image(current_html, rendered_path)
            
            # Step C: Judge comparison
            with console.status("  [bold green]Evaluating similarity..."):
                final_feedback = self.judge.compare(
                    page_assets.page_image_path,
                    rendered_path
                )
            
            # Record iteration
            history.append(IterationResult(
                iteration=iteration,
                html=current_html,
                rendered_image_path=rendered_path,
                feedback=final_feedback,
            ))
            
            # Display scores
            self._print_scores(final_feedback)
            
            # Step D: Decision
            if final_feedback.passed:
                console.print(f"  [bold green]✓ Target score reached![/]")
                break
            elif iteration < self.max_retries:
                console.print(f"  [yellow]→ Refining based on feedback...[/]")
                # Show what's correct (positive reinforcement)
                if hasattr(final_feedback, 'correct_elements') and final_feedback.correct_elements:
                    console.print(f"  [green]✓ Correct elements to preserve:[/]")
                    for correct in final_feedback.correct_elements[:3]:
                        console.print(f"    [dim green]• {correct}[/]")
                # Show errors to fix
                if final_feedback.critical_errors:
                    console.print(f"  [red]✗ Issues to fix:[/]")
                    for error in final_feedback.critical_errors[:3]:
                        console.print(f"    [dim]• {error}[/]")
        
        # Save final HTML
        final_html_path = page_output_dir / "final.html"
        final_html_path.write_text(current_html, encoding="utf-8")
        
        success = final_feedback.passed if final_feedback else False
        
        return PageResult(
            page_number=page_number,
            success=success,
            final_html=current_html,
            final_html_path=final_html_path,
            final_score=final_feedback.fidelity_score if final_feedback else 0,
            iterations=len(history),
            history=history,
        )
    
    def _print_scores(self, feedback: Union[JudgeFeedback, DualJudgeFeedback]):
        """Print a formatted score table."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Metric", style="dim")
        table.add_column("Score", justify="right")
        
        def score_color(score: int) -> str:
            if score >= self.target_score:
                return "green"
            elif score >= 80:
                return "yellow"
            return "red"
        
        table.add_row("Fidelity", f"[{score_color(feedback.fidelity_score)}]{feedback.fidelity_score}/100[/]")
        table.add_row("Layout", f"[{score_color(feedback.layout_score)}]{feedback.layout_score}/100[/]")
        table.add_row("Text", f"[{score_color(feedback.text_accuracy_score)}]{feedback.text_accuracy_score}/100[/]")
        table.add_row("Colors", f"[{score_color(feedback.color_match_score)}]{feedback.color_match_score}/100[/]")
        table.add_row("Equations", f"[{score_color(feedback.equation_score)}]{feedback.equation_score}/100[/]")
        
        # Extra info for dual judge
        if isinstance(feedback, DualJudgeFeedback):
            console.print(table)
            
            # Show judges used
            judges_str = ", ".join(feedback.judges_used)
            console.print(f"  [dim]Judges: {judges_str}[/]")
            
            # Show consensus status
            if len(feedback.judges_used) > 1:
                consensus_status = "[green]✓ Consensus[/]" if feedback.consensus_reached else "[yellow]⚠ Divergent[/]"
                console.print(f"  [dim]Status: {consensus_status}[/]")
            
            # Show ASCII art warning
            if feedback.equation_feedback and feedback.equation_feedback.ascii_art_detected:
                console.print("  [bold red]⚠ ASCII Art Equations Detected![/]")
            
            # Show verification result
            if feedback.verification_result:
                rec = feedback.verification_result.recommendation
                if rec == "accept":
                    console.print(f"  [green]✓ Verification: ACCEPT[/]")
                elif rec == "reject":
                    console.print(f"  [red]✗ Verification: REJECT[/]")
                else:
                    console.print(f"  [yellow]→ Verification: NEEDS REFINEMENT[/]")
        else:
            console.print(table)
    
    def _print_summary(self, results: list[PageResult]):
        """Print final processing summary."""
        console.print("\n" + "=" * 50)
        console.print("[bold]Processing Complete[/]\n")
        
        table = Table(title="Results Summary")
        table.add_column("Page", justify="center")
        table.add_column("Status", justify="center")
        table.add_column("Score", justify="center")
        table.add_column("Iterations", justify="center")
        table.add_column("Output", style="dim")
        
        for result in results:
            status = "[green]✓ Pass[/]" if result.success else "[red]✗ Below Target[/]"
            table.add_row(
                str(result.page_number + 1),
                status,
                f"{result.final_score}/100",
                str(result.iterations),
                str(result.final_html_path.relative_to(OUTPUT_DIR)),
            )
        
        console.print(table)
        
        # Overall stats
        passed = sum(1 for r in results if r.success)
        console.print(f"\n[bold]Success Rate:[/] {passed}/{len(results)} pages")
