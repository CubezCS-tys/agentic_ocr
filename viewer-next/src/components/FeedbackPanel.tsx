"use client";

import { useState, useEffect } from "react";
import { ProjectDetails, PageInfo, PageFeedback } from "@/types";
import { saveFeedback } from "@/lib/api";

interface FeedbackPanelProps {
  isOpen: boolean;
  onClose: () => void;
  project: ProjectDetails | null;
  page: PageInfo | null;
  currentFeedback?: PageFeedback;
  onFeedbackSaved: (feedback: PageFeedback) => void;
  onError: (message: string) => void;
}

type FeedbackStatus = "approved" | "needs_revision" | "rejected";

export default function FeedbackPanel({
  isOpen,
  onClose,
  project,
  page,
  currentFeedback,
  onFeedbackSaved,
  onError,
}: FeedbackPanelProps) {
  const [status, setStatus] = useState<FeedbackStatus | null>(null);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  // Update form when page changes
  useEffect(() => {
    if (currentFeedback) {
      setStatus(currentFeedback.status);
      setNotes(currentFeedback.feedback || "");
    } else {
      setStatus(null);
      setNotes("");
    }
  }, [currentFeedback, page]);

  const handleSave = async () => {
    if (!status) {
      onError("Please select a status");
      return;
    }

    if (!project || page === null) {
      onError("No page selected");
      return;
    }

    setSaving(true);
    try {
      const feedbackData: PageFeedback = {
        status,
        feedback: notes,
        timestamp: new Date().toISOString(),
      };

      await saveFeedback({
        project: project.name,
        page: page.number,
        status,
        feedback: notes,
        timestamp: feedbackData.timestamp,
      });

      onFeedbackSaved(feedbackData);
      onClose();
    } catch (error) {
      onError("Failed to save feedback");
    } finally {
      setSaving(false);
    }
  };

  const statusButtons: { value: FeedbackStatus; label: string; icon: string }[] = [
    { value: "approved", label: "Approved", icon: "fa-check-circle" },
    { value: "needs_revision", label: "Needs Revision", icon: "fa-edit" },
    { value: "rejected", label: "Rejected", icon: "fa-times-circle" },
  ];

  return (
    <aside
      className={`fixed right-0 top-[60px] w-[320px] h-[calc(100vh-60px)] bg-white border-l border-gray-200 shadow-xl transition-transform duration-300 z-40 flex flex-col ${
        isOpen ? "translate-x-0" : "translate-x-full"
      }`}
    >
      {/* Header */}
      <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-base font-semibold">Review & Feedback</h3>
        <button
          onClick={onClose}
          className="w-9 h-9 flex items-center justify-center text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-all"
        >
          <i className="fas fa-times"></i>
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 p-5 flex flex-col gap-5 overflow-y-auto">
        {/* Page Info */}
        {page && (
          <div className="bg-gray-50 rounded-lg p-3 text-sm">
            <span className="text-gray-500">Reviewing:</span>
            <span className="font-medium ml-2">Page {page.number + 1}</span>
          </div>
        )}

        {/* Status Selection */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-3">
            Status
          </label>
          <div className="flex flex-col gap-2">
            {statusButtons.map((btn) => (
              <button
                key={btn.value}
                onClick={() => setStatus(btn.value)}
                className={`flex items-center gap-3 px-4 py-3 border-2 rounded-lg text-sm font-medium transition-all ${
                  status === btn.value
                    ? btn.value === "approved"
                      ? "border-green-500 bg-green-50 text-green-600"
                      : btn.value === "needs_revision"
                      ? "border-amber-500 bg-amber-50 text-amber-600"
                      : "border-red-500 bg-red-50 text-red-600"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <i className={`fas ${btn.icon}`}></i>
                {btn.label}
              </button>
            ))}
          </div>
        </div>

        {/* Notes */}
        <div className="flex-1 flex flex-col">
          <label className="block text-sm font-semibold text-gray-700 mb-3">
            Notes & Improvement Requests
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Describe any issues or improvements needed..."
            className="flex-1 min-h-[150px] p-3 border border-gray-300 rounded-lg text-sm resize-none focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          />
        </div>

        {/* Save Button */}
        <button
          onClick={handleSave}
          disabled={saving || !page}
          className="flex items-center justify-center gap-2 px-6 py-3.5 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          <i className={`fas ${saving ? "fa-spinner fa-spin" : "fa-save"}`}></i>
          {saving ? "Saving..." : "Save Feedback"}
        </button>
      </div>
    </aside>
  );
}
