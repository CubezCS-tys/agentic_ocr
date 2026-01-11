import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

// Output directory - adjust this path as needed
const OUTPUT_DIR = path.join(process.cwd(), "..", "output");

export async function GET() {
  try {
    const projects: Array<{
      name: string;
      path: string;
      page_count: number;
      pages: string[];
    }> = [];

    if (fs.existsSync(OUTPUT_DIR)) {
      const entries = fs.readdirSync(OUTPUT_DIR, { withFileTypes: true });

      for (const entry of entries) {
        if (entry.isDirectory()) {
          const projectPath = path.join(OUTPUT_DIR, entry.name);
          const pages = fs
            .readdirSync(projectPath, { withFileTypes: true })
            .filter((d) => d.isDirectory() && d.name.startsWith("page_"))
            .map((d) => d.name)
            .sort();

          projects.push({
            name: entry.name,
            path: projectPath,
            page_count: pages.length,
            pages,
          });
        }
      }
    }

    return NextResponse.json(projects);
  } catch (error) {
    console.error("Error listing projects:", error);
    return NextResponse.json({ error: "Failed to list projects" }, { status: 500 });
  }
}
