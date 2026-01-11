"use client";

import { useState, useEffect } from "react";
import Header from "@/components/Header";
import Sidebar from "@/components/Sidebar";
import ComparisonView from "@/components/ComparisonView";
import FeedbackPanel from "@/components/FeedbackPanel";
import Toast from "@/components/Toast";
import { Project, ProjectDetails, PageInfo, FeedbackMap } from "@/types";
import { fetchProjects, fetchProject, fetchFeedback } from "@/lib/api";

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProject, setCurrentProject] = useState<ProjectDetails | null>(null);
  const [currentPage, setCurrentPage] = useState<PageInfo | null>(null);
  const [feedback, setFeedback] = useState<FeedbackMap>({});
  const [zoom, setZoom] = useState(100);
  const [syncScroll, setSyncScroll] = useState(true);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [selectedIteration, setSelectedIteration] = useState<string>("final");
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  // Load projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

  async function loadProjects() {
    try {
      const data = await fetchProjects();
      setProjects(data);
    } catch {
      showToast("Failed to load projects", "error");
    }
  }

  async function selectProject(projectName: string) {
    if (!projectName) {
      setCurrentProject(null);
      setCurrentPage(null);
      return;
    }

    try {
      const project = await fetchProject(projectName);
      const feedbackData = await fetchFeedback(projectName);
      setCurrentProject(project);
      setFeedback(feedbackData);
      
      // Auto-select first page
      if (project.pages.length > 0) {
        setCurrentPage(project.pages[0]);
        setSelectedIteration("final");
      }
    } catch {
      showToast("Failed to load project", "error");
    }
  }

  function selectPage(page: PageInfo) {
    setCurrentPage(page);
    setSelectedIteration("final");
  }

  function updateFeedback(pageNumber: number, newFeedback: FeedbackMap[string]) {
    setFeedback(prev => ({
      ...prev,
      [pageNumber]: newFeedback
    }));
  }

  function showToast(message: string, type: "success" | "error") {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header
        projects={projects}
        currentProject={currentProject}
        onSelectProject={selectProject}
        zoom={zoom}
        onZoomChange={setZoom}
        syncScroll={syncScroll}
        onSyncScrollChange={setSyncScroll}
      />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          pages={currentProject?.pages || []}
          currentPage={currentPage}
          feedback={feedback}
          onSelectPage={selectPage}
        />

        <ComparisonView
          project={currentProject}
          page={currentPage}
          zoom={zoom}
          syncScroll={syncScroll}
          selectedIteration={selectedIteration}
          onIterationChange={setSelectedIteration}
        />
      </div>

      {/* Feedback Toggle Button */}
      {!feedbackOpen && currentPage && (
        <button
          onClick={() => setFeedbackOpen(true)}
          className="fixed right-5 bottom-5 w-14 h-14 bg-blue-600 text-white rounded-full shadow-lg hover:bg-blue-700 transition-all hover:scale-105 z-50"
        >
          <i className="fas fa-comment-alt text-xl"></i>
        </button>
      )}

      {/* Feedback Panel */}
      <FeedbackPanel
        isOpen={feedbackOpen}
        onClose={() => setFeedbackOpen(false)}
        project={currentProject}
        page={currentPage}
        currentFeedback={currentPage ? feedback[currentPage.number] : undefined}
        onFeedbackSaved={(newFeedback) => {
          if (currentPage) {
            updateFeedback(currentPage.number, newFeedback);
          }
          showToast("Feedback saved successfully", "success");
        }}
        onError={(msg) => showToast(msg, "error")}
      />

      {/* Toast Notifications */}
      {toast && <Toast message={toast.message} type={toast.type} />}
    </div>
  );
}
