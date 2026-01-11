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
    const feedbackFile = path.join(OUTPUT_DIR, name, "feedback.json");

    if (fs.existsSync(feedbackFile)) {
      const content = fs.readFileSync(feedbackFile, "utf-8");
      return NextResponse.json(JSON.parse(content));
    }

    return NextResponse.json({});
  } catch (error) {
    console.error("Error getting feedback:", error);
    return NextResponse.json({ error: "Failed to get feedback" }, { status: 500 });
  }
}
