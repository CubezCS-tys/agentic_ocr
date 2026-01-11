#!/usr/bin/env python3
"""
Simple OCR Script - Single-shot PDF to HTML conversion using Gemini 3 Flash

This is a standalone script that uses all the learnings from the feedback loop
implementation to create the best possible single-shot OCR result.

Usage:
    python simple_ocr.py input.pdf [--output output.html] [--page 0]
    python simple_ocr.py image.png [--output output.html]
"""

import argparse
import base64
import sys
import time
import asyncio
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple

import google.generativeai as genai

# Rich for beautiful CLI output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

console = Console() if RICH_AVAILABLE else None

# ============================================================================
# Configuration
# ============================================================================

# Load API key from environment or .env file
try:
    from dotenv import load_dotenv
    import os
    load_dotenv()
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    MODEL = os.getenv("GEMINI_MODEL", "gemini-3-pro-preview")
except ImportError:
    import os
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    MODEL = os.getenv("GEMINI_MODEL", "gemini-3-pro-preview")

# ============================================================================
# Pricing (per 1M tokens) - Gemini 3 Flash Preview
# ============================================================================
# Source: https://ai.google.dev/pricing
PRICING = {
    "gemini-3-flash-preview": {
        "input": 0.50,    # $0.50 per 1M input tokens (prompts <= 200k)
        "output": 3.00,  # $3.00 per 1M output tokens (includes thinking tokens)
    },
}


@dataclass
class UsageStats:
    """Track API usage and costs."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_input: float = 0.0
    cost_output: float = 0.0
    cost_total: float = 0.0
    duration_seconds: float = 0.0
    pages_processed: int = 0
    
    def add_call(self, input_tokens: int, output_tokens: int, duration: float, model: str):
        """Add stats from an API call."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += input_tokens + output_tokens
        self.duration_seconds += duration
        self.pages_processed += 1
        
        # Calculate costs
        pricing = PRICING.get(model, PRICING["gemini-3-flash-preview"])
        self.cost_input = (self.input_tokens / 1_000_000) * pricing["input"]
        self.cost_output = (self.output_tokens / 1_000_000) * pricing["output"]
        self.cost_total = self.cost_input + self.cost_output


# Global stats tracker
stats = UsageStats()

# ============================================================================
# The Ultimate OCR Prompt (distilled from feedback loop learnings)
# ============================================================================

MASTER_PROMPT = """You are an elite document digitization expert. Your task is to convert this document image into pixel-perfect HTML that is visually IDENTICAL to the original.

## CRITICAL ANALYSIS STEPS (Do these FIRST):

### Step 1: Language & Direction Detection
Look at the SCRIPT used in the body text (not equations):
- **Arabic script** (connected cursive, right-to-left): ا ب ت ث ج ح خ → Use `dir="rtl"`, Arabic fonts
- **Latin script** (A-Z, a-z, left-to-right) → Use `dir="ltr"`, standard fonts
- **Mixed**: Arabic body with Latin math symbols is STILL an Arabic RTL document

### Step 2: Layout Analysis
- Count the number of text columns (1, 2, or more)
- Note headers, footers, page numbers and their positions
- Identify any colored banners, boxes, or backgrounds

### Step 3: Content Inventory
- Text blocks and paragraphs
- Mathematical equations (inline and display)
- Tables, lists, figures
- Special formatting (bold, italic, underline)

---

## OUTPUT REQUIREMENTS:

### 1. Document Structure
```html
<!DOCTYPE html>
<html lang="ar" dir="rtl">  <!-- Use appropriate lang and dir -->
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
    <!-- MathJax for equations -->
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
    <style>
        /* Your CSS here */
    </style>
</head>
<body>
    <!-- Content here -->
</body>
</html>
```

### 2. RTL/Arabic Documents (CRITICAL)
If the document contains Arabic text:
```css
html {
    direction: rtl;
}
body {
    font-family: 'Amiri', 'Traditional Arabic', 'Noto Naskh Arabic', serif;
    text-align: right;
    line-height: 1.8;
}
/* For LTR elements within RTL (equations, English) */
.ltr {
    direction: ltr;
    display: inline-block;
    unicode-bidi: embed;
}
```

### 3. Multi-Column Layouts
For 2-column academic papers:
```css
.two-column {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}
.column {
    text-align: justify;
}
```
- Content flows: RIGHT column first, then LEFT column (for RTL)
- Or LEFT first, then RIGHT (for LTR)

### 4. Mathematical Equations (ABSOLUTELY CRITICAL)
- **INLINE math**: Wrap with `\\( ... \\)`
- **DISPLAY/BLOCK math**: Wrap with `$$ ... $$`
- **NEVER use plain text** like "x^2" or "a/b" - always use LaTeX

Common LaTeX:
- Fractions: `\\frac{a}{b}`
- Subscripts: `x_{i}`, Superscripts: `x^{2}`
- Greek: `\\alpha`, `\\beta`, `\\gamma`, `\\theta`, `\\lambda`
- Summation: `\\sum_{i=1}^{n}`, Integral: `\\int_{a}^{b}`
- Square root: `\\sqrt{x}`, nth root: `\\sqrt[n]{x}`
- Limits: `\\lim_{x \\to \\infty}`

### 5. Typography Matching
- **Font sizes**: Match relative sizes (title > headers > body)
- **Font weights**: Use `font-weight: bold` for emphasized text
- **Line height**: Academic papers typically use 1.4-1.6
- **Text alignment**: Justified for body text in academic papers
- **Colors**: Sample exact hex codes from the image

### 6. Headers, Footers & Page Elements
- Position headers/footers with `position: fixed` or flexbox
- Match background colors for colored banners
- Include page numbers in correct position

### 7. Tables
```html
<table>
    <thead><tr><th>Header 1</th><th>Header 2</th></tr></thead>
    <tbody><tr><td>Data</td><td>Data</td></tr></tbody>
</table>
```
- Match border styles (solid, dashed, none)
- Match cell padding and alignment

### 8. Figures & Images
For any figures, charts, or images, insert a placeholder:
```html
<!-- FIGURE: Description of the figure -->
<div class="figure-placeholder" style="border: 1px dashed #ccc; padding: 20px; text-align: center;">
    [Figure: Brief description]
</div>
<p class="caption">Figure X: Caption text</p>
```

### 9. Lists
- Numbered: `<ol>` with appropriate `type` attribute (1, a, i, etc.)
- Bulleted: `<ul>`
- Match indentation and spacing

---

## QUALITY CHECKLIST (Verify before responding):
✓ Correct language direction (RTL for Arabic)
✓ All equations in proper LaTeX notation
✓ Column layout matches original
✓ Typography (fonts, sizes, weights) matches
✓ Colors and backgrounds match
✓ Headers/footers in correct positions
✓ All text content is included (no omissions)
✓ Proper spacing between elements

---

## OUTPUT FORMAT:
Return ONLY the complete HTML code, starting with `<!DOCTYPE html>` and ending with `</html>`.
Do NOT include any explanation, markdown code blocks, or commentary.
The HTML must be complete and self-contained.
"""


# ============================================================================
# Helper Functions
# ============================================================================

def pdf_to_images(pdf_path: Path, page_num: int = None) -> list[tuple[bytes, str]]:
    """Convert PDF pages to images. Returns list of (image_bytes, mime_type)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        log("[red]Error: PyMuPDF not installed. Run: pip install pymupdf[/red]")
        sys.exit(1)
    
    doc = fitz.open(pdf_path)
    images = []
    
    pages_to_process = [page_num] if page_num is not None else range(len(doc))
    
    for pnum in pages_to_process:
        if pnum >= len(doc):
            log(f"[yellow]Warning: Page {pnum} does not exist (document has {len(doc)} pages)[/yellow]")
            continue
        
        page = doc[pnum]
        # High DPI for quality
        mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        images.append((img_bytes, "image/png"))
        log(f"  [dim]Extracted page {pnum + 1}/{len(doc)} ({len(img_bytes):,} bytes)[/dim]")
    
    doc.close()
    return images


def load_image(image_path: Path) -> tuple[bytes, str]:
    """Load an image file and return (bytes, mime_type)."""
    suffix = image_path.suffix.lower()
    mime_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }
    mime_type = mime_types.get(suffix, 'image/png')
    
    with open(image_path, 'rb') as f:
        return f.read(), mime_type


def log(message: str, style: str = None):
    """Print with Rich if available, otherwise plain print."""
    if RICH_AVAILABLE and console:
        console.print(message, style=style)
    else:
        # Strip Rich markup for plain print
        import re
        plain = re.sub(r'\[.*?\]', '', message)
        print(plain)


async def convert_to_html_async(image_bytes: bytes, mime_type: str, page_index: int) -> Tuple[int, str]:
    """Send image to Gemini and get HTML output (async version).
    
    Returns: (page_index, html_content) to preserve page ordering
    """
    global stats
    
    # Configure API
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(MODEL)
    
    # Prepare image
    image_part = {
        "mime_type": mime_type,
        "data": base64.b64encode(image_bytes).decode("utf-8")
    }
    
    # Generate with timing
    start_time = time.time()
    
    # Run API call in thread pool executor to not block asyncio
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: model.generate_content(
            [MASTER_PROMPT, image_part],
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=32000,
            )
        )
    )
    
    duration = time.time() - start_time
    
    # Extract token usage from response
    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count if usage else 0
    output_tokens = usage.candidates_token_count if usage else 0
    
    # Update global stats
    stats.add_call(input_tokens, output_tokens, duration, MODEL)
    
    html = response.text.strip()
    
    # Clean up markdown code blocks if present
    if html.startswith("```html"):
        html = html[7:]
    elif html.startswith("```"):
        html = html[3:]
    if html.endswith("```"):
        html = html[:-3]
    
    return (page_index, html.strip())


def convert_to_html(image_bytes: bytes, mime_type: str) -> str:
    """Send image to Gemini and get HTML output (sync wrapper)."""
    # Run async version synchronously with page_index=-1 for single page
    _, html = asyncio.run(convert_to_html_async(image_bytes, mime_type, -1))
    return html


def print_stats_summary():
    """Print a beautiful summary of API usage and costs."""
    if RICH_AVAILABLE and console:
        # Create a nice table
        table = Table(title="📊 API Usage Summary", box=box.ROUNDED, show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="white")
        table.add_column("Value", justify="right", style="green")
        
        table.add_row("Pages Processed", f"{stats.pages_processed}")
        table.add_row("Input Tokens", f"{stats.input_tokens:,}")
        table.add_row("Output Tokens", f"{stats.output_tokens:,}")
        table.add_row("Total Tokens", f"[bold]{stats.total_tokens:,}[/bold]")
        table.add_row("─" * 15, "─" * 12)
        table.add_row("Input Cost", f"${stats.cost_input:.4f}")
        table.add_row("Output Cost", f"${stats.cost_output:.4f}")
        table.add_row("[bold]Total Cost[/bold]", f"[bold yellow]${stats.cost_total:.4f}[/bold yellow]")
        table.add_row("─" * 15, "─" * 12)
        table.add_row("Total Time", f"{stats.duration_seconds:.1f}s")
        if stats.pages_processed > 0:
            table.add_row("Avg Time/Page", f"{stats.duration_seconds / stats.pages_processed:.1f}s")
            table.add_row("Cost/Page", f"${stats.cost_total / stats.pages_processed:.4f}")
        
        console.print()
        console.print(table)
        console.print()
    else:
        print("\n" + "=" * 40)
        print("API Usage Summary")
        print("=" * 40)
        print(f"Pages Processed: {stats.pages_processed}")
        print(f"Input Tokens:    {stats.input_tokens:,}")
        print(f"Output Tokens:   {stats.output_tokens:,}")
        print(f"Total Tokens:    {stats.total_tokens:,}")
        print("-" * 40)
        print(f"Input Cost:      ${stats.cost_input:.4f}")
        print(f"Output Cost:     ${stats.cost_output:.4f}")
        print(f"TOTAL COST:      ${stats.cost_total:.4f}")
        print("-" * 40)
        print(f"Total Time:      {stats.duration_seconds:.1f}s")
        if stats.pages_processed > 0:
            print(f"Avg Time/Page:   {stats.duration_seconds / stats.pages_processed:.1f}s")
            print(f"Cost/Page:       ${stats.cost_total / stats.pages_processed:.4f}")
        print("=" * 40 + "\n")


def create_viewer_project(input_path: Path, html_contents: list[str], page_images: list[bytes], project_name: str = None) -> Path:
    """
    Create a project structure compatible with the Next.js viewer.
    
    Structure (matches main.py output):
    output/<project_name>/
        page_000.png          <- original page image
        page_000/
            final.html        <- generated HTML
        page_001.png
        page_001/
            final.html
        ...
    """
    # Determine project name
    if not project_name:
        project_name = f"simple_{input_path.stem}"
    
    # Get the script directory and create output folder
    script_dir = Path(__file__).parent
    output_dir = script_dir / "output" / project_name
    
    # Remove existing project if it exists
    import shutil
    if output_dir.exists():
        shutil.rmtree(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create each page folder (matching main.py structure)
    for i, (html, img_bytes) in enumerate(zip(html_contents, page_images)):
        # Save original image at project root level (like main.py does)
        with open(output_dir / f"page_{i:03d}.png", 'wb') as f:
            f.write(img_bytes)
        
        # Create page folder for HTML
        page_dir = output_dir / f"page_{i:03d}"
        page_dir.mkdir(exist_ok=True)
        
        # Save HTML as final.html
        with open(page_dir / "final.html", 'w', encoding='utf-8') as f:
            f.write(html)
    
    log(f"  [green]✓ Created viewer project:[/green] {output_dir}")
    return output_dir


def start_viewer_and_open(project_name: str):
    """Start the Next.js viewer and open the browser."""
    import subprocess
    import webbrowser
    import socket
    
    viewer_dir = Path(__file__).parent / "viewer-next"
    
    if not viewer_dir.exists():
        log("[yellow]Warning: viewer-next directory not found[/yellow]")
        return
    
    # Check if the dev server is already running on port 3000
    def is_port_in_use(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0
    
    if not is_port_in_use(3000):
        log("\n[bold]🚀 Starting Next.js viewer...[/bold]")
        # Start the dev server in background
        subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=viewer_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        # Wait for server to start
        import time
        for _ in range(30):  # Wait up to 30 seconds
            if is_port_in_use(3000):
                break
            time.sleep(1)
        else:
            log("[yellow]Warning: Viewer server may not have started properly[/yellow]")
    
    # Open browser
    url = f"http://localhost:3000"
    log(f"\n[bold]🌐 Opening viewer:[/bold] {url}")
    log(f"[dim]Select project: {project_name}[/dim]")
    webbrowser.open(url)


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description=f"Convert PDF/image to HTML using {MODEL}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python simple_ocr.py document.pdf
    python simple_ocr.py document.pdf --page 0 --output page1.html
    python simple_ocr.py scan.png --output result.html
    python simple_ocr.py document.pdf --page 0 --view  # Process page 0 and open in viewer
    python simple_ocr.py document.pdf --parallel --view  # Process ALL pages in parallel
    
    # View existing HTML file with original image:
    python simple_ocr.py original.png --import-html result.html --view
        """
    )
    parser.add_argument("input", type=Path, help="Input PDF or image file")
    parser.add_argument("--output", "-o", type=Path, help="Output HTML file (default: input_name.html)")
    parser.add_argument("--page", "-p", type=int, help="Page number to process (0-indexed, PDF only)")
    parser.add_argument("--parallel", action="store_true", help="Process all PDF pages in parallel (async mode)")
    parser.add_argument("--view", "-v", action="store_true", help="Open result in the Next.js viewer for comparison")
    parser.add_argument("--import-html", type=Path, help="Import existing HTML file instead of generating (use with --view)")
    
    args = parser.parse_args()
    
    # Validate input
    if not args.input.exists():
        log(f"[red]Error: File not found: {args.input}[/red]")
        sys.exit(1)
    
    # Import mode - just view existing HTML with original
    if args.import_html:
        if not args.import_html.exists():
            log(f"[red]Error: HTML file not found: {args.import_html}[/red]")
            sys.exit(1)
        
        log(f"\n[bold]📂 Import mode[/bold]")
        log(f"  Original: {args.input}")
        log(f"  HTML: {args.import_html}")
        
        # Load the original image
        suffix = args.input.suffix.lower()
        if suffix == '.pdf':
            images = pdf_to_images(args.input, args.page or 0)
            if not images:
                log("[red]Error: Could not extract page from PDF[/red]")
                sys.exit(1)
            img_bytes = images[0][0]
        else:
            img_bytes, _ = load_image(args.input)
        
        # Load the HTML
        with open(args.import_html, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Create viewer project and open
        project_name = f"simple_{args.input.stem}"
        create_viewer_project(args.input, [html_content], [img_bytes], project_name)
        
        if args.view:
            start_viewer_and_open(project_name)
        else:
            log("\n[dim]Use --view to open in browser[/dim]")
        
        sys.exit(0)
    
    # Check API key (only needed if not in import mode)
    if not GOOGLE_API_KEY:
        log("[red]Error: GOOGLE_API_KEY not set[/red]")
        log("[dim]Set it in your environment or in a .env file[/dim]")
        sys.exit(1)
    
    # Print header
    if RICH_AVAILABLE and console:
        console.print()
        console.print(Panel.fit(
            f"[bold cyan]Simple OCR[/bold cyan]\n"
            f"[dim]Model:[/dim] [green]{MODEL}[/green]\n"
            f"[dim]Input:[/dim] [white]{args.input}[/white]",
            title="🔍 Document Digitization",
            border_style="cyan"
        ))
    else:
        print(f"\n{'='*60}")
        print(f"Simple OCR - {MODEL}")
        print(f"{'='*60}")
        print(f"Input: {args.input}")
        print(f"Model: {MODEL}")
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        stem = args.input.stem
        if args.page is not None:
            stem += f"_page{args.page}"
        output_path = args.input.parent / f"{stem}.html"
    
    # Process input
    suffix = args.input.suffix.lower()
    
    if suffix == '.pdf':
        log("\n[bold]📄 Processing PDF...[/bold]")
        images = pdf_to_images(args.input, args.page)
        
        if len(images) == 0:
            log("[red]Error: No pages extracted[/red]")
            sys.exit(1)
        
        # Process pages (parallel or sequential)
        all_html = []
        all_images = []  # Keep track of images for viewer
        
        if args.parallel and len(images) > 1:
            # Parallel mode: process all pages concurrently
            log(f"\n[bold cyan]⚡ Processing {len(images)} pages in parallel...[/bold cyan]")
            
            if RICH_AVAILABLE and console:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold cyan]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    console=console
                ) as progress:
                    task = progress.add_task("Converting pages...", total=len(images))
                    
                    # Create async tasks for all pages
                    async def process_all_pages():
                        tasks = [
                            convert_to_html_async(img_bytes, mime_type, i)
                            for i, (img_bytes, mime_type) in enumerate(images)
                        ]
                        results = []
                        for coro in asyncio.as_completed(tasks):
                            result = await coro
                            progress.update(task, advance=1)
                            results.append(result)
                        return results
                    
                    # Run all pages in parallel
                    results = asyncio.run(process_all_pages())
            else:
                # Without Rich progress
                async def process_all_pages():
                    tasks = [
                        convert_to_html_async(img_bytes, mime_type, i)
                        for i, (img_bytes, mime_type) in enumerate(images)
                    ]
                    return await asyncio.gather(*tasks)
                
                results = asyncio.run(process_all_pages())
                log(f"[green]✓ Processed {len(results)} pages[/green]")
            
            # Sort results by page index to maintain order
            results.sort(key=lambda x: x[0])
            all_html = [html for _, html in results]
            all_images = [img_bytes for img_bytes, _ in images]
            
        else:
            # Sequential mode: process pages one by one
            for i, (img_bytes, mime_type) in enumerate(images):
                log(f"\n[bold cyan]Converting page {i + 1}/{len(images)}...[/bold cyan]")
                html = convert_to_html(img_bytes, mime_type)
                all_html.append(html)
                all_images.append(img_bytes)
                
                # If multiple pages, save each separately (unless using viewer)
                if len(images) > 1 and not args.view:
                    page_output = output_path.parent / f"{output_path.stem}_page{i}{output_path.suffix}"
                    with open(page_output, 'w', encoding='utf-8') as f:
                        f.write(html)
                    log(f"  [green]✓ Saved:[/green] {page_output}")
        
        # Save first/only page to main output
        final_html = all_html[0]
        
    else:
        # Image file
        log("\n[bold]🖼️  Processing image...[/bold]")
        img_bytes, mime_type = load_image(args.input)
        log("[bold cyan]Converting...[/bold cyan]")
        final_html = convert_to_html(img_bytes, mime_type)
        all_html = [final_html]
        all_images = [img_bytes]
    
    # Always save to output folder for viewer compatibility
    project_name = f"simple_{args.input.stem}"
    project_dir = create_viewer_project(args.input, all_html, all_images, project_name)
    
    # Also save to custom output path if specified
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(final_html)
        log(f"  [green]✓ Also saved to:[/green] {args.output}")
    
    # Print output summary
    if RICH_AVAILABLE and console:
        console.print()
        console.print(Panel.fit(
            f"[bold green]✓ Output saved![/bold green]\n"
            f"[dim]Project:[/dim] [white]{project_name}[/white]\n"
            f"[dim]Path:[/dim] [white]{project_dir}[/white]\n"
            f"[dim]Size:[/dim] [white]{len(final_html):,} characters[/white]",
            border_style="green"
        ))
    else:
        print(f"\n{'='*60}")
        print(f"✓ Output saved to: {project_dir}")
        print(f"  Size: {len(final_html):,} characters")
        print(f"{'='*60}")
    
    # Detection summary
    detections = []
    if "dir=\"rtl\"" in final_html or "direction: rtl" in final_html:
        detections.append("🔄 RTL document (Arabic/Hebrew)")
    if "MathJax" in final_html:
        detections.append("📐 Mathematical equations")
    if "two-column" in final_html or "grid-template-columns" in final_html:
        detections.append("📰 Multi-column layout")
    
    if detections:
        log("\n[bold]Detected Features:[/bold]")
        for d in detections:
            log(f"  {d}")
    
    # Print usage stats
    print_stats_summary()
    
    # Open viewer if --view flag is set
    if args.view:
        start_viewer_and_open(project_name)
    else:
        log(f"\n[dim]Tip: Run 'npm run dev' in viewer-next/ and select '{project_name}' to compare[/dim]")


if __name__ == "__main__":
    main()
