"""
PDF Ingestion Module
Handles PDF to image conversion and asset extraction.
"""

import base64
import fitz  # pymupdf
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from config import DPI, OUTPUT_DIR


@dataclass
class PageAssets:
    """Container for extracted page assets."""
    page_number: int
    page_image_path: Path
    page_image_base64: str
    figures: list[dict]  # List of {bbox, image_base64, index}
    width: int
    height: int


class PDFIngestion:
    """Handles PDF processing: page rendering and asset extraction."""
    
    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")
        
        self.doc = fitz.open(self.pdf_path)
        self.output_dir = OUTPUT_DIR / self.pdf_path.stem
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def page_count(self) -> int:
        """Return total number of pages in the PDF."""
        return len(self.doc)
    
    def extract_page(self, page_number: int = 0) -> PageAssets:
        """
        Extract a single page as high-DPI image and identify figures.
        
        Args:
            page_number: Zero-indexed page number
            
        Returns:
            PageAssets with image and extracted figures
        """
        if page_number < 0 or page_number >= self.page_count:
            raise ValueError(f"Page {page_number} out of range (0-{self.page_count - 1})")
        
        page = self.doc[page_number]
        
        # Render page at high DPI
        zoom = DPI / 72  # PDF default is 72 DPI
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix)
        
        # Save page image
        page_image_path = self.output_dir / f"page_{page_number:03d}.png"
        pix.save(str(page_image_path))
        
        # Convert to base64
        page_image_base64 = base64.b64encode(pix.tobytes("png")).decode("utf-8")
        
        # Extract figures/images from the page
        figures = self._extract_figures(page, page_number, zoom)
        
        return PageAssets(
            page_number=page_number,
            page_image_path=page_image_path,
            page_image_base64=page_image_base64,
            figures=figures,
            width=pix.width,
            height=pix.height,
        )
    
    def _extract_figures(self, page: fitz.Page, page_number: int, zoom: float) -> list[dict]:
        """
        Extract embedded images and figure regions from a page.
        
        Args:
            page: PyMuPDF page object
            page_number: Page index for naming
            zoom: Scale factor for coordinates
            
        Returns:
            List of figure dictionaries with bbox and base64 data
        """
        figures = []
        
        # Get images embedded in the PDF
        image_list = page.get_images(full=True)
        
        for idx, img_info in enumerate(image_list):
            try:
                xref = img_info[0]
                base_image = self.doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                # Find the image bbox on the page
                img_rects = page.get_image_rects(xref)
                if img_rects:
                    rect = img_rects[0]
                    # Scale bbox to match high-DPI rendering
                    scaled_bbox = {
                        "x0": int(rect.x0 * zoom),
                        "y0": int(rect.y0 * zoom),
                        "x1": int(rect.x1 * zoom),
                        "y1": int(rect.y1 * zoom),
                    }
                else:
                    scaled_bbox = None
                
                # Convert to base64
                image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                mime_type = f"image/{image_ext}" if image_ext != "jpeg" else "image/jpeg"
                
                figures.append({
                    "index": idx,
                    "bbox": scaled_bbox,
                    "image_base64": image_base64,
                    "mime_type": mime_type,
                    "data_uri": f"data:{mime_type};base64,{image_base64}",
                })
                
            except Exception as e:
                print(f"Warning: Could not extract image {idx}: {e}")
                continue
        
        return figures
    
    def extract_all_pages(self) -> list[PageAssets]:
        """Extract all pages from the PDF."""
        return [self.extract_page(i) for i in range(self.page_count)]
    
    def close(self):
        """Close the PDF document."""
        self.doc.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def image_to_base64(image_path: Path) -> str:
    """Convert an image file to base64 string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
