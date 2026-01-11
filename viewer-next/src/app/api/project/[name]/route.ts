import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const OUTPUT_DIR = path.join(process.cwd(), "..", "output");

export async function GET(
  request: Request,
  { params }: { params: Promise<{ name: string }> }
) {
  try {
    const { name } = await params;
    const projectDir = path.join(OUTPUT_DIR, name);

    if (!fs.existsSync(projectDir)) {
      return NextResponse.json({ error: "Project not found" }, { status: 404 });
    }

    const pages: Array<{
      number: number;
      name: string;
      has_final: boolean;
      iterations: number;
      iteration_files: string[];
    }> = [];

    const entries = fs.readdirSync(projectDir, { withFileTypes: true });

    for (const entry of entries) {
      if (entry.isDirectory() && entry.name.startsWith("page_")) {
        const pageNum = parseInt(entry.name.split("_")[1]);
        const pageDir = path.join(projectDir, entry.name);

        const finalHtml = path.join(pageDir, "final.html");
        const iterations = fs
          .readdirSync(pageDir)
          .filter((f) => f.startsWith("iteration_") && f.endsWith(".html"))
          .sort();

        pages.push({
          number: pageNum,
          name: entry.name,
          has_final: fs.existsSync(finalHtml),
          iterations: iterations.length,
          iteration_files: iterations,
        });
      }
    }

    // Sort by page number
    pages.sort((a, b) => a.number - b.number);

    // Find original PDF
    const pdfFiles = entries.filter(
      (e) => e.isFile() && e.name.endsWith(".pdf")
    );

    return NextResponse.json({
      name,
      pages,
      original_pdf: pdfFiles.length > 0 ? pdfFiles[0].name : null,
    });
  } catch (error) {
    console.error("Error getting project:", error);
    return NextResponse.json({ error: "Failed to get project" }, { status: 500 });
  }
}
