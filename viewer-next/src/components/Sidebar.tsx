"use client";

import { PageInfo, FeedbackMap } from "@/types";

interface SidebarProps {
  pages: PageInfo[];
  currentPage: PageInfo | null;
  feedback: FeedbackMap;
  onSelectPage: (page: PageInfo) => void;
}

export default function Sidebar({
  pages,
  currentPage,
  feedback,
  onSelectPage,
}: SidebarProps) {
  const getStatusBadge = (pageNumber: number) => {
    const pageFeedback = feedback[pageNumber];
    if (!pageFeedback) return null;

    const statusClasses: Record<string, string> = {
      approved: "badge-approved",
      needs_revision: "badge-needs-revision",
      rejected: "badge-rejected",
    };

    const statusLabels: Record<string, string> = {
      approved: "Approved",
      needs_revision: "Needs Revision",
      rejected: "Rejected",
    };

    return (
      <span
        className={`px-2 py-1 rounded text-[10px] font-semibold uppercase ${statusClasses[pageFeedback.status]}`}
      >
        {statusLabels[pageFeedback.status]}
      </span>
    );
  };

  return (
    <aside className="w-[260px] bg-white border-r border-gray-200 flex flex-col flex-shrink-0">
      {/* Header */}
      <div className="px-5 py-4 border-b border-gray-200">
        <h3 className="text-sm font-semibold text-gray-700">Pages</h3>
        <p className="text-xs text-gray-500 mt-1">
          {pages.length} pages
        </p>
      </div>

      {/* Page List */}
      <div className="flex-1 overflow-y-auto p-2">
        {pages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400 text-center p-4">
            <i className="fas fa-folder-open text-4xl mb-4"></i>
            <p className="text-sm">Select a project to view pages</p>
          </div>
        ) : (
          pages.map((page) => (
            <button
              key={page.number}
              onClick={() => onSelectPage(page)}
              className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-lg mb-1 transition-all text-left ${
                currentPage?.number === page.number
                  ? "bg-blue-600 text-white"
                  : "hover:bg-gray-100"
              }`}
            >
              <div
                className={`w-8 h-8 rounded-md flex items-center justify-center font-semibold text-sm ${
                  currentPage?.number === page.number
                    ? "bg-white/20"
                    : "bg-gray-100"
                }`}
              >
                {page.number + 1}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium">Page {page.number + 1}</div>
                <div
                  className={`text-xs ${
                    currentPage?.number === page.number
                      ? "text-white/80"
                      : "text-gray-500"
                  }`}
                >
                  {page.iterations} iterations
                </div>
              </div>
              {currentPage?.number !== page.number && getStatusBadge(page.number)}
            </button>
          ))
        )}
      </div>
    </aside>
  );
}
