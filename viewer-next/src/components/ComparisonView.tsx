"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { ProjectDetails, PageInfo } from "@/types";
import { getOriginalUrl, getHtmlUrl, getIterationUrl } from "@/lib/api";

interface ComparisonViewProps {
  project: ProjectDetails | null;
  page: PageInfo | null;
  zoom: number;
  syncScroll: boolean;
  selectedIteration: string;
  onIterationChange: (iteration: string) => void;
}

export default function ComparisonView({
  project,
  page,
  zoom,
  syncScroll,
  selectedIteration,
  onIterationChange,
}: ComparisonViewProps) {
  const originalRef = useRef<HTMLDivElement>(null);
  const htmlRef = useRef<HTMLDivElement>(null);
  const [leftWidth, setLeftWidth] = useState(50);
  const [isResizing, setIsResizing] = useState(false);

  // Sync scroll handling
  const handleScroll = useCallback(
    (source: "original" | "html") => {
      if (!syncScroll) return;

      const sourceEl = source === "original" ? originalRef.current : htmlRef.current;
      const targetEl = source === "original" ? htmlRef.current : originalRef.current;

      if (!sourceEl || !targetEl) return;

      const scrollRatio =
        sourceEl.scrollTop / (sourceEl.scrollHeight - sourceEl.clientHeight);
      targetEl.scrollTop =
        scrollRatio * (targetEl.scrollHeight - targetEl.clientHeight);
    },
    [syncScroll]
  );

  // Resizer handling
  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isResizing) return;
      const container = document.getElementById("comparison-container");
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const percentage = ((e.clientX - rect.left) / rect.width) * 100;

      if (percentage > 20 && percentage < 80) {
        setLeftWidth(percentage);
      }
    },
    [isResizing]
  );

  const handleMouseUp = useCallback(() => {
    setIsResizing(false);
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  }, []);

  useEffect(() => {
    if (isResizing) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing, handleMouseMove, handleMouseUp]);

  const getHtmlSrc = () => {
    if (!project || !page) return "";
    if (selectedIteration === "final") {
      return getHtmlUrl(project.name, page.number);
    }
    return getIterationUrl(project.name, page.number, parseInt(selectedIteration));
  };

  const openInNewTab = () => {
    const url = getHtmlSrc();
    if (url) window.open(url, "_blank");
  };

  const downloadFile = (url: string, filename: string) => {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div id="comparison-container" className="flex-1 flex overflow-hidden">
      {/* Original PDF Panel */}
      <div
        className="flex flex-col bg-white min-w-[300px]"
        style={{ width: `${leftWidth}%` }}
      >
        <div className="h-[50px] px-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2.5 text-sm font-semibold text-gray-700">
            <i className="fas fa-file-pdf text-blue-600"></i>
            <span>Original PDF</span>
          </div>
          <button
            onClick={() =>
              project &&
              page &&
              downloadFile(
                getOriginalUrl(project.name, page.number),
                `page_${page.number + 1}_original.png`
              )
            }
            className="w-9 h-9 flex items-center justify-center text-gray-500 hover:text-blue-600 hover:bg-gray-100 rounded-lg transition-all"
            title="Download Original"
          >
            <i className="fas fa-download"></i>
          </button>
        </div>

        <div
          ref={originalRef}
          onScroll={() => handleScroll("original")}
          className="flex-1 overflow-auto p-5 bg-gray-50 panel-scroll"
        >
          {project && page ? (
            <img
              src={getOriginalUrl(project.name, page.number)}
              alt={`Original Page ${page.number + 1}`}
              className="shadow-lg rounded"
              style={{
                transform: `scale(${zoom / 100})`,
                transformOrigin: "top left",
              }}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <i className="fas fa-image text-5xl mb-4"></i>
              <p className="text-sm">Select a page to view</p>
            </div>
          )}
        </div>
      </div>

      {/* Resizer */}
      <div
        onMouseDown={() => setIsResizing(true)}
        className="w-2 bg-gray-200 resizer flex items-center justify-center flex-shrink-0"
      >
        <div className="w-1 h-10 bg-gray-400 rounded-full"></div>
      </div>

      {/* HTML Panel */}
      <div
        className="flex flex-col bg-white min-w-[300px]"
        style={{ width: `${100 - leftWidth}%` }}
      >
        <div className="h-[50px] px-4 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2.5 text-sm font-semibold text-gray-700">
            <i className="fas fa-code text-blue-600"></i>
            <span>Generated HTML</span>
          </div>
          <div className="flex items-center gap-2">
            {/* Iteration Select */}
            <select
              value={selectedIteration}
              onChange={(e) => onIterationChange(e.target.value)}
              className="px-3 py-1.5 border border-gray-300 rounded-md text-sm bg-white cursor-pointer"
            >
              <option value="final">Final</option>
              {page?.iteration_files.map((_, i) => (
                <option key={i + 1} value={i + 1}>
                  Iteration {i + 1}
                </option>
              ))}
            </select>
            <button
              onClick={openInNewTab}
              className="w-9 h-9 flex items-center justify-center text-gray-500 hover:text-blue-600 hover:bg-gray-100 rounded-lg transition-all"
              title="Open in New Tab"
            >
              <i className="fas fa-external-link-alt"></i>
            </button>
            <button
              onClick={() =>
                project &&
                page &&
                downloadFile(
                  getHtmlSrc(),
                  `page_${page.number + 1}_${selectedIteration}.html`
                )
              }
              className="w-9 h-9 flex items-center justify-center text-gray-500 hover:text-blue-600 hover:bg-gray-100 rounded-lg transition-all"
              title="Download HTML"
            >
              <i className="fas fa-download"></i>
            </button>
          </div>
        </div>

        <div
          ref={htmlRef}
          onScroll={() => handleScroll("html")}
          className="flex-1 overflow-auto p-5 bg-gray-50 panel-scroll"
        >
          {project && page ? (
            <iframe
              src={getHtmlSrc()}
              className="w-full h-full min-h-[800px] shadow-lg rounded bg-white html-iframe"
              style={{
                transform: `scale(${zoom / 100})`,
                transformOrigin: "top left",
              }}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <i className="fas fa-code text-5xl mb-4"></i>
              <p className="text-sm">Select a page to view</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
