"""
HTML Renderer Module
Uses Playwright to render HTML and capture screenshots.
"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

from config import OUTPUT_DIR


class HTMLRenderer:
    """Renders HTML files to images using headless browser."""
    
    def __init__(self, viewport_width: int = 1200, viewport_height: int = 1600):
        # Fixed viewport - good balance for document rendering
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
    
    async def render_to_image_async(
        self, 
        html_content: str, 
        output_path: Path = None,
        wait_for_mathjax: bool = True
    ) -> Path:
        """
        Render HTML content to a PNG image.
        
        Args:
            html_content: The HTML string to render
            output_path: Where to save the screenshot
            wait_for_mathjax: Wait for MathJax to finish rendering
            
        Returns:
            Path to the rendered image
        """
        if output_path is None:
            output_path = OUTPUT_DIR / "rendered_view.png"
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save HTML to temp file
        html_path = output_path.with_suffix(".html")
        html_path.write_text(html_content, encoding="utf-8")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            
            # Simple fixed viewport - no scaling complexity
            page = await browser.new_page(
                viewport={"width": self.viewport_width, "height": self.viewport_height}
            )
            
            # Load the HTML file
            await page.goto(f"file://{html_path.absolute()}")
            
            # Wait for MathJax to render equations
            if wait_for_mathjax and "mathjax" in html_content.lower():
                try:
                    # Wait for MathJax to be ready
                    await page.wait_for_function(
                        """() => {
                            return typeof MathJax !== 'undefined' && 
                                   MathJax.startup && 
                                   MathJax.startup.promise;
                        }""",
                        timeout=5000
                    )
                    # Wait for typesetting to complete
                    await page.evaluate("() => MathJax.startup.promise")
                    # Additional small delay for rendering
                    await asyncio.sleep(0.5)
                except Exception:
                    # MathJax might not be present or failed to load
                    pass
            
            # Wait for fonts and images to load
            await page.wait_for_load_state("networkidle")
            
            # Take full page screenshot (device_scale_factor handles resolution)
            await page.screenshot(
                path=str(output_path),
                full_page=True,
                type="png"
            )
            
            await browser.close()
        
        return output_path
    
    def render_to_image(
        self, 
        html_content: str, 
        output_path: Path = None,
        wait_for_mathjax: bool = True
    ) -> Path:
        """
        Synchronous wrapper for render_to_image_async.
        
        Args:
            html_content: The HTML string to render
            output_path: Where to save the screenshot
            wait_for_mathjax: Wait for MathJax to finish rendering
            
        Returns:
            Path to the rendered image
        """
        return asyncio.run(
            self.render_to_image_async(html_content, output_path, wait_for_mathjax)
        )
    
    async def get_page_dimensions_async(self, html_content: str) -> dict:
        """Get the dimensions of the rendered HTML page."""
        html_path = OUTPUT_DIR / "temp_dimension_check.html"
        html_path.write_text(html_content, encoding="utf-8")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(f"file://{html_path.absolute()}")
            await page.wait_for_load_state("networkidle")
            
            dimensions = await page.evaluate("""() => ({
                width: document.body.scrollWidth,
                height: document.body.scrollHeight,
                viewportWidth: window.innerWidth,
                viewportHeight: window.innerHeight
            })""")
            
            await browser.close()
        
        html_path.unlink(missing_ok=True)
        return dimensions
