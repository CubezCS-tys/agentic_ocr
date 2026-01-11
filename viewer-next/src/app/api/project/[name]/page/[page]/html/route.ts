import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const OUTPUT_DIR = path.join(process.cwd(), "..", "output");

export async function GET(
  request: Request,
  { params }: { params: Promise<{ name: string; page: string }> }
) {
  try {
    const { name, page } = await params;
    const pageNum = parseInt(page);
    const pageDir = path.join(OUTPUT_DIR, name, `page_${String(pageNum).padStart(3, "0")}`);

    // Try final.html first
    let htmlPath = path.join(pageDir, "final.html");

    if (!fs.existsSync(htmlPath)) {
      // Try latest iteration
      const iterations = fs
        .readdirSync(pageDir)
        .filter((f) => f.startsWith("iteration_") && f.endsWith(".html"))
        .sort()
        .reverse();

      if (iterations.length > 0) {
        htmlPath = path.join(pageDir, iterations[0]);
      } else {
        return NextResponse.json({ error: "HTML not found" }, { status: 404 });
      }
    }

    const htmlContent = fs.readFileSync(htmlPath, "utf-8");
    return new NextResponse(htmlContent, {
      headers: {
        "Content-Type": "text/html; charset=utf-8",
      },
    });
  } catch (error) {
    console.error("Error getting HTML:", error);
    return NextResponse.json({ error: "Failed to get HTML" }, { status: 500 });
  }
}
