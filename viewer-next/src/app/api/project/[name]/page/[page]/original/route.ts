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
    const imagePath = path.join(OUTPUT_DIR, name, `page_${String(pageNum).padStart(3, "0")}.png`);

    if (!fs.existsSync(imagePath)) {
      return NextResponse.json({ error: "Original page not found" }, { status: 404 });
    }

    const imageBuffer = fs.readFileSync(imagePath);
    return new NextResponse(imageBuffer, {
      headers: {
        "Content-Type": "image/png",
        "Cache-Control": "public, max-age=31536000",
      },
    });
  } catch (error) {
    console.error("Error getting original page:", error);
    return NextResponse.json({ error: "Failed to get original page" }, { status: 500 });
  }
}
