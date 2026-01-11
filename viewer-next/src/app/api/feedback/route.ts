import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const OUTPUT_DIR = path.join(process.cwd(), "..", "output");

export async function POST(request: Request) {
  try {
    const data = await request.json();
    const { project, page, status, feedback, timestamp } = data;

    const projectDir = path.join(OUTPUT_DIR, project);
    const feedbackFile = path.join(projectDir, "feedback.json");

    // Load existing feedback
    let allFeedback: Record<string, unknown> = {};
    if (fs.existsSync(feedbackFile)) {
      const content = fs.readFileSync(feedbackFile, "utf-8");
      allFeedback = JSON.parse(content);
    }

    // Update feedback for this page
    allFeedback[String(page)] = {
      status,
      feedback,
      timestamp,
    };

    // Ensure directory exists
    if (!fs.existsSync(projectDir)) {
      fs.mkdirSync(projectDir, { recursive: true });
    }

    // Save
    fs.writeFileSync(feedbackFile, JSON.stringify(allFeedback, null, 2));

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Error saving feedback:", error);
    return NextResponse.json({ error: "Failed to save feedback" }, { status: 500 });
  }
}
