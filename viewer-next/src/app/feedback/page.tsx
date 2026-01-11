"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Project, FeedbackMap, PageFeedback } from "@/types";
import { fetchProjects, fetchProject, fetchFeedback } from "@/lib/api";

interface ProjectFeedback {
  project: Project;
  feedback: FeedbackMap;
  totalPages: number;
}

export default function FeedbackDashboard() {
  const [projectsFeedback, setProjectsFeedback] = useState<ProjectFeedback[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);

  useEffect(() => {
    loadAllFeedback();
  }, []);

  async function loadAllFeedback() {
    try {
      const projects = await fetchProjects();
      const feedbackData: ProjectFeedback[] = [];

      for (const project of projects) {
        const details = await fetchProject(project.name);
        const feedback = await fetchFeedback(project.name);
        feedbackData.push({
          project,
          feedback,
          totalPages: details.pages.length,
        });
      }

      setProjectsFeedback(feedbackData);
    } catch (error) {
      console.error("Failed to load feedback:", error);
    } finally {
      setLoading(false);
    }
  }

  function getStatusCounts(feedback: FeedbackMap) {
    const counts = { approved: 0, needs_revision: 0, rejected: 0, pending: 0 };
    Object.values(feedback).forEach((f) => {
      if (f.status in counts) {
        counts[f.status as keyof typeof counts]++;
      }
    });
    return counts;
  }

  function formatDate(timestamp: string) {
    return new Date(timestamp).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <i className="fas fa-spinner fa-spin text-4xl text-blue-600 mb-4"></i>
          <p className="text-gray-600">Loading feedback...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="h-[60px] bg-white border-b border-gray-200 flex items-center justify-between px-6 shadow-sm">
        <div className="flex items-center gap-4">
          <Link href="/" className="flex items-center gap-2.5 text-xl font-bold text-blue-600 hover:text-blue-700">
            <i className="fas fa-file-pdf text-2xl"></i>
            <span>RA-OCR</span>
          </Link>
          <span className="text-gray-400">|</span>
          <h1 className="text-lg font-semibold text-gray-700">Feedback Dashboard</h1>
        </div>
        <Link
          href="/"
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-600 hover:text-blue-600 transition-colors"
        >
          <i className="fas fa-arrow-left"></i>
          Back to Viewer
        </Link>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto py-8 px-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          {(() => {
            let totalApproved = 0;
            let totalNeedsRevision = 0;
            let totalRejected = 0;
            let totalPending = 0;

            projectsFeedback.forEach(({ feedback, totalPages }) => {
              const counts = getStatusCounts(feedback);
              totalApproved += counts.approved;
              totalNeedsRevision += counts.needs_revision;
              totalRejected += counts.rejected;
              totalPending += totalPages - Object.keys(feedback).length;
            });

            return (
              <>
                <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-200">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                      <i className="fas fa-check-circle text-green-600 text-xl"></i>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-gray-900">{totalApproved}</p>
                      <p className="text-sm text-gray-500">Approved</p>
                    </div>
                  </div>
                </div>
                <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-200">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-amber-100 rounded-lg flex items-center justify-center">
                      <i className="fas fa-edit text-amber-600 text-xl"></i>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-gray-900">{totalNeedsRevision}</p>
                      <p className="text-sm text-gray-500">Needs Revision</p>
                    </div>
                  </div>
                </div>
                <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-200">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-red-100 rounded-lg flex items-center justify-center">
                      <i className="fas fa-times-circle text-red-600 text-xl"></i>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-gray-900">{totalRejected}</p>
                      <p className="text-sm text-gray-500">Rejected</p>
                    </div>
                  </div>
                </div>
                <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-200">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center">
                      <i className="fas fa-clock text-gray-500 text-xl"></i>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-gray-900">{totalPending}</p>
                      <p className="text-sm text-gray-500">Pending Review</p>
                    </div>
                  </div>
                </div>
              </>
            );
          })()}
        </div>

        {/* Projects List */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-800">Projects</h2>
          </div>

          {projectsFeedback.length === 0 ? (
            <div className="p-12 text-center text-gray-500">
              <i className="fas fa-folder-open text-4xl mb-4"></i>
              <p>No projects found</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {projectsFeedback.map(({ project, feedback, totalPages }) => {
                const counts = getStatusCounts(feedback);
                const reviewedCount = Object.keys(feedback).length;
                const progress = totalPages > 0 ? (reviewedCount / totalPages) * 100 : 0;

                return (
                  <div key={project.name} className="p-6">
                    <div
                      className="flex items-center justify-between cursor-pointer"
                      onClick={() =>
                        setSelectedProject(selectedProject === project.name ? null : project.name)
                      }
                    >
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                          <i className="fas fa-file-alt text-blue-600"></i>
                        </div>
                        <div>
                          <h3 className="font-semibold text-gray-800">{project.name}</h3>
                          <p className="text-sm text-gray-500">
                            {reviewedCount} of {totalPages} pages reviewed
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-6">
                        {/* Status Pills */}
                        <div className="flex items-center gap-2">
                          {counts.approved > 0 && (
                            <span className="px-2.5 py-1 bg-green-100 text-green-700 rounded-full text-xs font-medium">
                              {counts.approved} approved
                            </span>
                          )}
                          {counts.needs_revision > 0 && (
                            <span className="px-2.5 py-1 bg-amber-100 text-amber-700 rounded-full text-xs font-medium">
                              {counts.needs_revision} needs revision
                            </span>
                          )}
                          {counts.rejected > 0 && (
                            <span className="px-2.5 py-1 bg-red-100 text-red-700 rounded-full text-xs font-medium">
                              {counts.rejected} rejected
                            </span>
                          )}
                        </div>

                        {/* Progress Bar */}
                        <div className="w-32">
                          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-blue-600 rounded-full transition-all"
                              style={{ width: `${progress}%` }}
                            />
                          </div>
                        </div>

                        <i
                          className={`fas fa-chevron-down text-gray-400 transition-transform ${
                            selectedProject === project.name ? "rotate-180" : ""
                          }`}
                        ></i>
                      </div>
                    </div>

                    {/* Expanded Feedback Details */}
                    {selectedProject === project.name && Object.keys(feedback).length > 0 && (
                      <div className="mt-6 ml-14 space-y-3">
                        {Object.entries(feedback)
                          .sort(([a], [b]) => parseInt(a) - parseInt(b))
                          .map(([pageNum, pageFeedback]) => (
                            <div
                              key={pageNum}
                              className="flex items-start gap-4 p-4 bg-gray-50 rounded-lg"
                            >
                              <div
                                className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                                  pageFeedback.status === "approved"
                                    ? "bg-green-100"
                                    : pageFeedback.status === "needs_revision"
                                    ? "bg-amber-100"
                                    : "bg-red-100"
                                }`}
                              >
                                <i
                                  className={`fas ${
                                    pageFeedback.status === "approved"
                                      ? "fa-check text-green-600"
                                      : pageFeedback.status === "needs_revision"
                                      ? "fa-edit text-amber-600"
                                      : "fa-times text-red-600"
                                  }`}
                                ></i>
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between mb-1">
                                  <span className="font-medium text-gray-800">
                                    Page {parseInt(pageNum) + 1}
                                  </span>
                                  <span className="text-xs text-gray-500">
                                    {formatDate(pageFeedback.timestamp)}
                                  </span>
                                </div>
                                {pageFeedback.feedback && (
                                  <p className="text-sm text-gray-600 whitespace-pre-wrap">
                                    {pageFeedback.feedback}
                                  </p>
                                )}
                              </div>
                              <Link
                                href={`/?project=${encodeURIComponent(project.name)}&page=${pageNum}`}
                                className="px-3 py-1.5 text-xs font-medium text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                              >
                                View
                              </Link>
                            </div>
                          ))}
                      </div>
                    )}

                    {selectedProject === project.name && Object.keys(feedback).length === 0 && (
                      <div className="mt-6 ml-14 p-4 bg-gray-50 rounded-lg text-center text-gray-500 text-sm">
                        No feedback submitted yet
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
