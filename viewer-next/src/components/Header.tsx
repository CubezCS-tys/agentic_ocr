"use client";

import Link from "next/link";
import { Project, ProjectDetails } from "@/types";

interface HeaderProps {
  projects: Project[];
  currentProject: ProjectDetails | null;
  onSelectProject: (name: string) => void;
  zoom: number;
  onZoomChange: (zoom: number) => void;
  syncScroll: boolean;
  onSyncScrollChange: (sync: boolean) => void;
}

export default function Header({
  projects,
  currentProject,
  onSelectProject,
  zoom,
  onZoomChange,
  syncScroll,
  onSyncScrollChange,
}: HeaderProps) {
  return (
    <header className="h-[60px] bg-white border-b border-gray-200 flex items-center justify-between px-5 shadow-sm z-50">
      {/* Left: Logo */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5 text-xl font-bold text-blue-600">
          <i className="fas fa-file-pdf text-2xl"></i>
          <span>RA-OCR</span>
        </div>
        <span className="text-gray-500 text-sm pl-4 border-l border-gray-200">
          Document Comparison Viewer
        </span>
      </div>

      {/* Center: Project Select */}
      <div className="flex-1 max-w-md mx-10">
        <select
          value={currentProject?.name || ""}
          onChange={(e) => onSelectProject(e.target.value)}
          className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm bg-white cursor-pointer hover:border-blue-500 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all"
        >
          <option value="">Select a project...</option>
          {projects.map((project) => (
            <option key={project.name} value={project.name}>
              {project.name} ({project.page_count} pages)
            </option>
          ))}
        </select>
      </div>

      {/* Right: Controls */}
      <div className="flex items-center gap-4">
        {/* Zoom Controls */}
        <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-lg">
          <button
            onClick={() => onZoomChange(Math.max(25, zoom - 10))}
            className="w-8 h-8 flex items-center justify-center text-gray-600 hover:text-blue-600 hover:bg-gray-200 rounded transition-all"
            title="Zoom Out"
          >
            <i className="fas fa-search-minus"></i>
          </button>
          <span className="text-sm font-medium min-w-[45px] text-center">
            {zoom}%
          </span>
          <button
            onClick={() => onZoomChange(Math.min(200, zoom + 10))}
            className="w-8 h-8 flex items-center justify-center text-gray-600 hover:text-blue-600 hover:bg-gray-200 rounded transition-all"
            title="Zoom In"
          >
            <i className="fas fa-search-plus"></i>
          </button>
        </div>

        {/* Sync Scroll Toggle */}
        <button
          onClick={() => onSyncScrollChange(!syncScroll)}
          className={`flex items-center gap-1.5 px-3.5 py-2 border rounded-lg text-sm font-medium transition-all ${
            syncScroll
              ? "bg-blue-600 border-blue-600 text-white"
              : "bg-white border-gray-300 text-gray-700 hover:border-blue-500"
          }`}
        >
          <i className="fas fa-link"></i>
          <span>Sync</span>
        </button>

        {/* Feedback Dashboard Link */}
        <Link
          href="/feedback"
          className="flex items-center gap-1.5 px-3.5 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:border-blue-500 hover:text-blue-600 transition-all"
        >
          <i className="fas fa-chart-bar"></i>
          <span>Dashboard</span>
        </Link>
      </div>
    </header>
  );
}
