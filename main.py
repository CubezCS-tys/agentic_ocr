#!/usr/bin/env python3
"""
RA-OCR: Recursive Augmentation OCR
Main CLI entry point for the pixel-perfect PDF to HTML converter.
"""

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from config import (
    validate_config, OUTPUT_DIR, TARGET_SCORE, MAX_RETRIES,
    USE_DUAL_JUDGE, USE_CROSS_MODEL, USE_EQUATION_SPECIALIST, USE_VERIFICATION,
    GENERATOR_MODEL,
)
from pipeline import OCRPipeline
from staged_pipeline import StagedPipelineRunner

app = typer.Typer(
    name="ra-ocr",
    help="Convert PDF documents to pixel-perfect HTML using an agentic feedback loop.",
    add_completion=False,
)
console = Console()


@app.command()
def convert(
    pdf_path: Path = typer.Argument(
        ...,
        help="Path to the PDF file to convert",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    pages: str = typer.Option(
        None,
        "--pages", "-p",
        help="Page range to process (e.g., '1', '1-3', '1,3,5'). Default: all pages",
    ),
    target_score: int = typer.Option(
        TARGET_SCORE,
        "--target", "-t",
        help="Target fidelity score (0-100)",
        min=0,
        max=100,
    ),
    max_retries: int = typer.Option(
        MAX_RETRIES,
        "--max-retries", "-r",
        help="Maximum refinement iterations per page",
        min=1,
        max=20,
    ),
    output_dir: Path = typer.Option(
        None,
        "--output", "-o",
        help="Output directory (default: ./output/<pdf_name>)",
    ),
    language: str = typer.Option(
        None,
        "--language", "-l",
        help="Override detected language (e.g., 'arabic', 'english', 'chinese')",
    ),
    direction: str = typer.Option(
        None,
        "--direction", "-d",
        help="Override text direction: 'rtl' or 'ltr'",
    ),
    columns: int = typer.Option(
        None,
        "--columns", "-c",
        help="Override detected column count (1, 2, or more)",
        min=1,
        max=4,
    ),
    verbose: bool = typer.Option(
        True,
        "--verbose/--quiet", "-v/-q",
        help="Show detailed progress",
    ),
):
    """
    Convert a PDF document to pixel-perfect HTML.
    
    Uses an agentic feedback loop with vision LLMs to iteratively
    improve the HTML output until it visually matches the original PDF.
    """
    # Validate configuration
    config_status = validate_config()
    if not config_status["valid"]:
        console.print("[bold red]Configuration Error:[/]")
        for issue in config_status["issues"]:
            console.print(f"  • {issue}")
        console.print("\n[dim]Please check your .env file.[/]")
        raise typer.Exit(1)
    
    # Show configuration
    judge_info = "Dual-Judge" if USE_DUAL_JUDGE else "Single Judge"
    if USE_DUAL_JUDGE:
        features = []
        if USE_CROSS_MODEL:
            features.append("Cross-Model")
        if USE_EQUATION_SPECIALIST:
            features.append("Equation Specialist")
        if USE_VERIFICATION:
            features.append("Verification Gate")
        judge_info += f" ({', '.join(features)})" if features else ""
    
    console.print(Panel.fit(
        f"[bold]RA-OCR Pipeline[/]\n"
        f"[dim]Generator:[/] {config_status['config']['generator_model']}\n"
        f"[dim]Judge:[/] {judge_info}\n"
        f"[dim]Target Score:[/] {target_score}/100\n"
        f"[dim]Max Retries:[/] {max_retries}",
        title="Configuration",
    ))
    
    # Initialize pipeline
    pipeline = OCRPipeline(
        max_retries=max_retries,
        target_score=target_score,
        verbose=verbose,
    )
    
    # Process PDF
    try:
        results = pipeline.process_pdf(pdf_path)
        
        # Report results
        passed = sum(1 for r in results if r.success)
        if passed == len(results):
            console.print("\n[bold green]✓ All pages converted successfully![/]")
        else:
            console.print(f"\n[yellow]⚠ {passed}/{len(results)} pages met target score[/]")
        
        console.print(f"\n[dim]Output saved to:[/] {OUTPUT_DIR / pdf_path.stem}")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/]")
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command()
def check():
    """
    Check configuration and dependencies.
    """
    console.print("[bold]Checking RA-OCR Configuration...[/]\n")
    
    # Check config
    config_status = validate_config()
    
    if config_status["valid"]:
        console.print("[green]✓[/] API keys configured")
    else:
        console.print("[red]✗[/] Configuration issues:")
        for issue in config_status["issues"]:
            console.print(f"    • {issue}")
    
    # Check dependencies
    console.print("\n[bold]Dependencies:[/]")
    
    dependencies = [
        ("pymupdf", "fitz"),
        ("playwright", "playwright"),
        ("google-generativeai", "google.generativeai"),
        ("openai", "openai"),
        ("rich", "rich"),
        ("typer", "typer"),
        ("Pillow", "PIL"),
    ]
    
    all_ok = True
    for name, import_name in dependencies:
        try:
            __import__(import_name)
            console.print(f"  [green]✓[/] {name}")
        except ImportError:
            console.print(f"  [red]✗[/] {name} - not installed")
            all_ok = False
    
    # Check Playwright browsers
    console.print("\n[bold]Playwright Browsers:[/]")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
                browser.close()
                console.print("  [green]✓[/] Chromium installed")
            except Exception:
                console.print("  [red]✗[/] Chromium not installed")
                console.print("    [dim]Run: playwright install chromium[/]")
                all_ok = False
    except Exception as e:
        console.print(f"  [red]✗[/] Playwright error: {e}")
        all_ok = False
    
    if all_ok and config_status["valid"]:
        console.print("\n[bold green]All checks passed! Ready to convert PDFs.[/]")
    else:
        console.print("\n[yellow]Some issues need attention.[/]")
        raise typer.Exit(1)


@app.command()
def version():
    """Show version information."""
    console.print("[bold]RA-OCR[/] - Recursive Augmentation OCR")
    console.print("[dim]Version 0.1.0[/]")


@app.command("staged")
def staged_convert(
    pdf_path: Path = typer.Argument(
        ...,
        help="Path to the PDF or image file to convert",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    pages: str = typer.Option(
        None,
        "--pages", "-p",
        help="Page range to process (e.g., '0', '0-2', '0,2,4'). 0-indexed. Default: all pages",
    ),
    output_dir: Path = typer.Option(
        None,
        "--output", "-o",
        help="Output directory (default: ./output/staged_<name>_<timestamp>)",
    ),
    run_name: str = typer.Option(
        None,
        "--name", "-n",
        help="Name for this run (used in output folder name)",
    ),
    no_math_refinement: bool = typer.Option(
        False,
        "--no-math-refinement",
        help="Disable the optional math refinement stage",
    ),
    verbose: bool = typer.Option(
        True,
        "--verbose/--quiet", "-v/-q",
        help="Show detailed progress",
    ),
):
    """
    Convert a PDF using the STAGED pipeline (experimental).
    
    This pipeline separates concerns into discrete stages:
    
    • Stage 1: Layout Extraction → HTML skeleton with placeholders
    
    • Stage 2: Text Extraction → JSON content for each placeholder
    
    • Stage 2.5: Math Refinement → Re-extract complex equations (optional)
    
    • Stage 3: Assembly → Pure Python merges skeleton + content
    
    Each LLM call has ONE job, making outputs more consistent.
    """
    # Validate configuration
    config_status = validate_config()
    if not config_status["valid"]:
        console.print("[bold red]Configuration Error:[/]")
        for issue in config_status["issues"]:
            console.print(f"  • {issue}")
        console.print("\n[dim]Please check your .env file.[/]")
        raise typer.Exit(1)
    
    # Parse pages
    page_list = None
    if pages:
        if "-" in pages and "," not in pages:
            start, end = pages.split("-")
            page_list = list(range(int(start), int(end) + 1))
        else:
            page_list = [int(p.strip()) for p in pages.split(",")]
    
    # Show configuration
    console.print()
    console.print(Panel.fit(
        "[bold cyan]╔═══════════════════════════════════════════════════════════╗[/]\n"
        "[bold cyan]║[/]           [bold white]STAGED OCR PIPELINE[/] [dim](Experimental)[/]           [bold cyan]║[/]\n"
        "[bold cyan]╚═══════════════════════════════════════════════════════════╝[/]\n\n"
        f"[dim]Stage 1:[/] [green]Layout Extraction[/] → HTML skeleton\n"
        f"[dim]Stage 2:[/] [green]Text Extraction[/] → JSON content\n"
        f"[dim]Stage 2.5:[/] [green]Math Refinement[/] → {'[yellow]Disabled[/]' if no_math_refinement else '[green]Enabled[/]'}\n"
        f"[dim]Stage 3:[/] [green]Assembly[/] → Final HTML (pure Python)\n\n"
        f"[dim]Model:[/] {GENERATOR_MODEL}\n"
        f"[dim]Input:[/] {pdf_path.name}\n"
        f"[dim]Pages:[/] {page_list if page_list else 'All'}",
        title="[bold]Configuration[/]",
        border_style="cyan",
    ))
    
    # Initialize pipeline
    runner = StagedPipelineRunner(
        output_dir=output_dir or OUTPUT_DIR,
        enable_math_refinement=not no_math_refinement,
        math_confidence_threshold=0.8,
    )
    
    # Process based on file type
    try:
        if pdf_path.suffix.lower() == ".pdf":
            results = runner.process_pdf(pdf_path, pages=page_list, run_name=run_name)
        else:
            # Single image
            result = runner.process_image(pdf_path, run_name=run_name)
            results = [result]
        
        # Report results
        console.print()
        
        passed = sum(1 for r in results if r.success)
        total = len(results)
        total_cost = sum(r.cost_usd for r in results)
        total_tokens = sum(r.total_tokens for r in results)
        
        if passed == total:
            console.print(Panel.fit(
                f"[bold green]✓ All {total} page(s) converted successfully![/]\n\n"
                + "\n".join([
                    f"[dim]Page {i}:[/] {r.total_duration_ms:.0f}ms • {len(r.references)} refs • ${r.cost_usd:.4f}"
                    for i, r in enumerate(results)
                ])
                + f"\n\n[bold]Total Cost:[/] ${total_cost:.4f} ({total_tokens:,} tokens)",
                title="[bold green]Success[/]",
                border_style="green",
            ))
        else:
            console.print(Panel.fit(
                f"[yellow]⚠ {passed}/{total} pages completed successfully[/]\n\n"
                + "\n".join([
                    f"[dim]Page {i}:[/] {'[green]✓[/]' if r.success else '[red]✗[/]'} {r.total_duration_ms:.0f}ms • ${r.cost_usd:.4f}"
                    for i, r in enumerate(results)
                ])
                + f"\n\n[bold]Total Cost:[/] ${total_cost:.4f} ({total_tokens:,} tokens)",
                title="[bold yellow]Partial Success[/]",
                border_style="yellow",
            ))
        
        # Show output location
        if results and results[0].output_dir:
            out_path = results[0].output_dir.parent if len(results) > 1 else results[0].output_dir
            console.print(f"\n[dim]Output saved to:[/] {out_path}")
            console.print(f"[dim]Files per page:[/] skeleton.html, content.json, final.html, summary.json")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/]")
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command("validated")
def validated_convert(
    pdf_path: Path = typer.Argument(
        ...,
        help="Path to the PDF file to convert",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    pages: str = typer.Option(
        None,
        "--pages", "-p",
        help="Page range to process (e.g., '0', '0-2', '0,2,4'). 0-indexed. Default: all pages",
    ),
    output_dir: Path = typer.Option(
        None,
        "--output", "-o",
        help="Output directory (default: ./output/staged_<name>_<timestamp>)",
    ),
    run_name: str = typer.Option(
        None,
        "--name", "-n",
        help="Name for this run (used in output folder name)",
    ),
    max_retries: int = typer.Option(
        2,
        "--retries", "-r",
        help="Maximum retries for failed pages",
        min=0,
        max=5,
    ),
    pass_threshold: float = typer.Option(
        0.85,
        "--threshold", "-t",
        help="Score threshold for passing validation (0.0-1.0)",
        min=0.0,
        max=1.0,
    ),
    no_math_refinement: bool = typer.Option(
        False,
        "--no-math-refinement",
        help="Disable the optional math refinement stage",
    ),
    verbose: bool = typer.Option(
        True,
        "--verbose/--quiet", "-v/-q",
        help="Show detailed progress",
    ),
):
    """
    Convert a PDF using the STAGED pipeline with VALIDATION and auto-retry.
    
    After processing each page, an LLM judge compares the output to the original
    and detects issues like:
    
    • Truncated text (cut off mid-sentence)
    • Missing columns or sections  
    • Swapped column order (reading order wrong)
    • Garbled/incorrect text extraction
    
    Pages that fail validation are automatically re-processed up to --retries times.
    """
    # Validate configuration
    config_status = validate_config()
    if not config_status["valid"]:
        console.print("[bold red]Configuration Error:[/]")
        for issue in config_status["issues"]:
            console.print(f"  • {issue}")
        console.print("\n[dim]Please check your .env file.[/]")
        raise typer.Exit(1)
    
    # Parse pages
    page_list = None
    if pages:
        if "-" in pages and "," not in pages:
            start, end = pages.split("-")
            page_list = list(range(int(start), int(end) + 1))
        else:
            page_list = [int(p.strip()) for p in pages.split(",")]
    
    # Show configuration
    console.print()
    console.print(Panel.fit(
        "[bold cyan]╔═══════════════════════════════════════════════════════════╗[/]\n"
        "[bold cyan]║[/]      [bold white]VALIDATED STAGED OCR PIPELINE[/] [dim](with Judge)[/]      [bold cyan]║[/]\n"
        "[bold cyan]╚═══════════════════════════════════════════════════════════╝[/]\n\n"
        f"[dim]Stage 1:[/] [green]Layout Extraction[/] → HTML skeleton\n"
        f"[dim]Stage 2:[/] [green]Text Extraction[/] → JSON content\n"
        f"[dim]Stage 2.5:[/] [green]Math Refinement[/] → {'[yellow]Disabled[/]' if no_math_refinement else '[green]Enabled[/]'}\n"
        f"[dim]Stage 3:[/] [green]Assembly[/] → Final HTML\n"
        f"[dim]Stage 4:[/] [magenta]Validation[/] → LLM Judge\n"
        f"[dim]Stage 5:[/] [magenta]Auto-Retry[/] → Up to {max_retries} retries\n\n"
        f"[dim]Model:[/] {GENERATOR_MODEL}\n"
        f"[dim]Input:[/] {pdf_path.name}\n"
        f"[dim]Pages:[/] {page_list if page_list else 'All'}\n"
        f"[dim]Pass Threshold:[/] {pass_threshold:.0%}",
        title="[bold]Configuration[/]",
        border_style="magenta",
    ))
    
    # Initialize pipeline
    runner = StagedPipelineRunner(
        output_dir=output_dir or OUTPUT_DIR,
        enable_math_refinement=not no_math_refinement,
        math_confidence_threshold=0.8,
    )
    
    # Process with validation
    try:
        summary = runner.process_pdf_with_validation(
            pdf_path,
            pages=page_list,
            run_name=run_name,
            max_retries=max_retries,
            pass_threshold=pass_threshold,
        )
        
        # Report results
        console.print()
        
        if summary["pass_rate"] >= 0.95:
            status_color = "green"
            status_icon = "✓"
            status_text = "Excellent"
        elif summary["pass_rate"] >= 0.8:
            status_color = "yellow"
            status_icon = "⚠"
            status_text = "Good"
        else:
            status_color = "red"
            status_icon = "✗"
            status_text = "Needs Review"
        
        # Calculate total cost from results
        total_cost = sum(r.cost_usd for r in summary["results"].values())
        total_tokens = sum(r.total_tokens for r in summary["results"].values())
        
        console.print(Panel.fit(
            f"[bold {status_color}]{status_icon} {status_text}[/]\n\n"
            f"[bold]Validation Results:[/]\n"
            f"  • Total pages: {summary['total_pages']}\n"
            f"  • Passed: [green]{summary['passed']}[/] ({summary['pass_rate']*100:.1f}%)\n"
            f"  • Failed: [{'red' if summary['failed'] > 0 else 'dim'}]{summary['failed']}[/]\n"
            + (f"  • Failed pages: {[p+1 for p in summary['failed_pages']]}\n" if summary['failed_pages'] else "")
            + (f"  • Pages retried: {len(summary['retry_counts'])}\n" if summary['retry_counts'] else "")
            + f"\n[bold]Cost:[/] ${total_cost:.4f} ({total_tokens:,} tokens)",
            title=f"[bold {status_color}]Validation Summary[/]",
            border_style=status_color,
        ))
        
        console.print(f"\n[dim]Output saved to:[/] {summary['run_dir']}")
        console.print(f"[dim]Validation report:[/] validation_report.json")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/]")
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command("async")
def async_convert(
    pdf_path: Path = typer.Argument(
        ...,
        help="Path to the PDF file to convert",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    pages: str = typer.Option(
        None,
        "--pages", "-p",
        help="Page range to process (e.g., '0', '0-2', '0,2,4'). 0-indexed. Default: all pages",
    ),
    output_dir: Path = typer.Option(
        None,
        "--output", "-o",
        help="Output directory (default: ./output/staged_<name>_<timestamp>)",
    ),
    run_name: str = typer.Option(
        None,
        "--name", "-n",
        help="Name for this run (used in output folder name)",
    ),
    max_retries: int = typer.Option(
        2,
        "--retries", "-r",
        help="Maximum retries for failed pages",
        min=0,
        max=5,
    ),
    pass_threshold: float = typer.Option(
        0.85,
        "--threshold", "-t",
        help="Score threshold for passing validation (0.0-1.0)",
        min=0.0,
        max=1.0,
    ),
    max_concurrent: int = typer.Option(
        4,
        "--concurrent", "-c",
        help="Maximum number of pages to process in parallel",
        min=1,
        max=10,
    ),
    no_math_refinement: bool = typer.Option(
        False,
        "--no-math-refinement",
        help="Disable the optional math refinement stage",
    ),
    no_validation: bool = typer.Option(
        False,
        "--no-validation",
        help="Skip validation and just process pages in parallel",
    ),
    verbose: bool = typer.Option(
        True,
        "--verbose/--quiet", "-v/-q",
        help="Show detailed progress",
    ),
):
    """
    Convert a PDF using ASYNC parallel processing for speed.
    
    Pages are processed concurrently (up to --concurrent at once) for faster
    throughput. Results are automatically ordered by page number.
    
    By default, includes validation with auto-retry. Use --no-validation to skip.
    """
    import asyncio
    
    # Validate configuration
    config_status = validate_config()
    if not config_status["valid"]:
        console.print("[bold red]Configuration Error:[/]")
        for issue in config_status["issues"]:
            console.print(f"  • {issue}")
        console.print("\n[dim]Please check your .env file.[/]")
        raise typer.Exit(1)
    
    # Parse pages
    page_list = None
    if pages:
        if "-" in pages and "," not in pages:
            start, end = pages.split("-")
            page_list = list(range(int(start), int(end) + 1))
        else:
            page_list = [int(p.strip()) for p in pages.split(",")]
    
    # Show configuration
    console.print()
    mode = "ASYNC" + (" + VALIDATION" if not no_validation else "")
    console.print(Panel.fit(
        "[bold cyan]╔═══════════════════════════════════════════════════════════╗[/]\n"
        f"[bold cyan]║[/]      [bold white]{mode} STAGED OCR PIPELINE[/]      [bold cyan]║[/]\n"
        "[bold cyan]╚═══════════════════════════════════════════════════════════╝[/]\n\n"
        f"[dim]Stage 1:[/] [green]Layout Extraction[/] → HTML skeleton\n"
        f"[dim]Stage 2:[/] [green]Text Extraction[/] → JSON content\n"
        f"[dim]Stage 2.5:[/] [green]Math Refinement[/] → {'[yellow]Disabled[/]' if no_math_refinement else '[green]Enabled[/]'}\n"
        f"[dim]Stage 3:[/] [green]Assembly[/] → Final HTML\n"
        + (f"[dim]Stage 4:[/] [magenta]Validation[/] → LLM Judge\n" if not no_validation else "")
        + (f"[dim]Stage 5:[/] [magenta]Auto-Retry[/] → Up to {max_retries} retries\n" if not no_validation else "")
        + f"\n[bold yellow]⚡ Parallel Processing:[/] Up to {max_concurrent} pages at once\n\n"
        f"[dim]Model:[/] {GENERATOR_MODEL}\n"
        f"[dim]Input:[/] {pdf_path.name}\n"
        f"[dim]Pages:[/] {page_list if page_list else 'All'}\n"
        + (f"[dim]Pass Threshold:[/] {pass_threshold:.0%}" if not no_validation else ""),
        title="[bold]Configuration[/]",
        border_style="yellow",
    ))
    
    # Initialize pipeline
    runner = StagedPipelineRunner(
        output_dir=output_dir or OUTPUT_DIR,
        enable_math_refinement=not no_math_refinement,
        math_confidence_threshold=0.8,
    )
    
    # Run async processing
    try:
        if no_validation:
            # Simple async without validation
            results = asyncio.run(runner.process_pdf_async(
                pdf_path,
                pages=page_list,
                run_name=run_name,
                max_concurrent=max_concurrent,
            ))
            
            # Calculate totals
            total_cost = sum(r.cost_usd for r in results)
            total_tokens = sum(r.total_tokens for r in results)
            success_count = sum(1 for r in results if r.success)
            
            console.print()
            console.print(Panel.fit(
                f"[bold green]✓ Complete[/]\n\n"
                f"[bold]Results:[/]\n"
                f"  • Total pages: {len(results)}\n"
                f"  • Successful: [green]{success_count}[/]\n"
                f"  • Failed: [{'red' if len(results) - success_count > 0 else 'dim'}]{len(results) - success_count}[/]\n"
                f"\n[bold]Cost:[/] ${total_cost:.4f} ({total_tokens:,} tokens)",
                title="[bold green]Async Processing Complete[/]",
                border_style="green",
            ))
            
            console.print(f"\n[dim]Output saved to:[/] {results[0].output_dir.parent if results else 'N/A'}")
            
        else:
            # Async with validation
            summary = asyncio.run(runner.process_pdf_with_validation_async(
                pdf_path,
                pages=page_list,
                run_name=run_name,
                max_retries=max_retries,
                pass_threshold=pass_threshold,
                max_concurrent=max_concurrent,
            ))
            
            # Report results
            console.print()
            
            if summary["pass_rate"] >= 0.95:
                status_color = "green"
                status_icon = "✓"
                status_text = "Excellent"
            elif summary["pass_rate"] >= 0.8:
                status_color = "yellow"
                status_icon = "⚠"
                status_text = "Good"
            else:
                status_color = "red"
                status_icon = "✗"
                status_text = "Needs Review"
            
            # Calculate total cost from results
            total_cost = sum(r.cost_usd for r in summary["results"].values())
            total_tokens = sum(r.total_tokens for r in summary["results"].values())
            
            console.print(Panel.fit(
                f"[bold {status_color}]{status_icon} {status_text}[/]\n\n"
                f"[bold]Validation Results:[/]\n"
                f"  • Total pages: {summary['total_pages']}\n"
                f"  • Passed: [green]{summary['passed']}[/] ({summary['pass_rate']*100:.1f}%)\n"
                f"  • Failed: [{'red' if summary['failed'] > 0 else 'dim'}]{summary['failed']}[/]\n"
                + (f"  • Failed pages: {[p+1 for p in summary['failed_pages']]}\n" if summary['failed_pages'] else "")
                + (f"  • Pages retried: {len(summary['retry_counts'])}\n" if summary['retry_counts'] else "")
                + f"\n[bold]Cost:[/] ${total_cost:.4f} ({total_tokens:,} tokens)",
                title=f"[bold {status_color}]Async Validation Summary[/]",
                border_style=status_color,
            ))
            
            console.print(f"\n[dim]Output saved to:[/] {summary['run_dir']}")
            console.print(f"[dim]Validation report:[/] validation_report.json")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/]")
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
