#!/usr/bin/env python3
"""
Staged Pipeline - Quick Test Script

A simple script to test the staged pipeline on a document.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from staged_pipeline import StagedPipelineRunner


def main():
    """Run a quick test of the staged pipeline."""
    
    # Default test files
    test_files = [
        "test_docs/sample.pdf",
        "2_col.pdf", 
        "1749-000-022-008_pages_8_10.pdf",
    ]
    
    # Check for command line argument
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        # Find first available test file
        input_file = None
        for tf in test_files:
            if Path(tf).exists():
                input_file = tf
                break
        
        if not input_file:
            print("Usage: python run_staged.py <pdf_or_image_path>")
            print("\nNo test files found. Please provide a path to a PDF or image.")
            sys.exit(1)
    
    input_path = Path(input_file)
    
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)
    
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║                    STAGED OCR PIPELINE                           ║
║                                                                  ║
║  Stage 1: Layout Extraction (HTML skeleton)                      ║
║  Stage 2: Text Extraction (JSON content)                         ║
║  Stage 2.5: Math Refinement (optional)                           ║
║  Stage 3: Assembly (Pure Python)                                 ║
╚══════════════════════════════════════════════════════════════════╝

Input: {input_path}
""")
    
    # Create runner
    runner = StagedPipelineRunner(
        enable_math_refinement=True,
        math_confidence_threshold=0.8,
    )
    
    # Process based on file type
    if input_path.suffix.lower() == ".pdf":
        # Process first page only for quick test
        results = runner.process_pdf(input_path, pages=[0])
        result = results[0] if results else None
    else:
        result = runner.process_image(input_path)
    
    # Print summary
    if result:
        print(f"""
╔══════════════════════════════════════════════════════════════════╗
║                        RESULTS                                   ║
╚══════════════════════════════════════════════════════════════════╝

Success: {"✓ Yes" if result.success else "✗ No"}
Total Time: {result.total_duration_ms:.0f}ms
Output Dir: {result.output_dir}

Stage Breakdown:
""")
        for stage in result.stages:
            status = "✓" if stage.success else "✗"
            print(f"  {status} {stage.stage}: {stage.duration_ms:.0f}ms")
            if stage.warnings:
                for w in stage.warnings[:3]:  # Limit warnings shown
                    print(f"      ⚠ {w}")
        
        print(f"""
References Found: {len(result.references)}
""")
        for ref in result.references[:10]:  # Show first 10
            print(f"  - {ref['ref']} ({ref['type']})")
        
        if len(result.references) > 10:
            print(f"  ... and {len(result.references) - 10} more")
        
        print(f"""
Output Files:
  - {result.output_dir}/skeleton.html
  - {result.output_dir}/content.json
  - {result.output_dir}/final.html
""")
    else:
        print("No results generated.")


if __name__ == "__main__":
    main()
