import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const OUTPUT_DIR = path.join(process.cwd(), "..", "output");

export async function GET(
  request: Request,
  { params }: { params: Promise<{ name: string; page: string; iteration: string }> }
) {
  try {
    const { name, page, iteration } = await params;
    const pageNum = parseInt(page);
    const iterNum = parseInt(iteration);
    const pageDir = path.join(OUTPUT_DIR, name, `page_${String(pageNum).padStart(3, "0")}`);
    const htmlPath = path.join(pageDir, `iteration_${String(iterNum).padStart(2, "0")}.html`);

    if (!fs.existsSync(htmlPath)) {
      return NextResponse.json({ error: "Iteration not found" }, { status: 404 });
    }

    const htmlContent = fs.readFileSync(htmlPath, "utf-8");
    return new NextResponse(htmlContent, {
      headers: {
        "Content-Type": "text/html; charset=utf-8",
      },
    });
  } catch (error) {
    console.error("Error getting iteration:", error);
    return NextResponse.json({ error: "Failed to get iteration" }, { status: 500 });
  }
}
