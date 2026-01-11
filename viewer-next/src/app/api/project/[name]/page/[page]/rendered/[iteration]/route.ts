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
    const imagePath = path.join(pageDir, `rendered_${String(iterNum).padStart(2, "0")}.png`);

    if (!fs.existsSync(imagePath)) {
      return NextResponse.json({ error: "Rendered image not found" }, { status: 404 });
    }

    const imageBuffer = fs.readFileSync(imagePath);
    return new NextResponse(imageBuffer, {
      headers: {
        "Content-Type": "image/png",
        "Cache-Control": "public, max-age=31536000",
      },
    });
  } catch (error) {
    console.error("Error getting rendered image:", error);
    return NextResponse.json({ error: "Failed to get rendered image" }, { status: 500 });
  }
}
