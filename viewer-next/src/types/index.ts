export interface Project {
  name: string;
  path: string;
  page_count: number;
  pages: string[];
}

export interface PageInfo {
  number: number;
  name: string;
  has_final: boolean;
  iterations: number;
  iteration_files: string[];
}

export interface ProjectDetails {
  name: string;
  pages: PageInfo[];
  original_pdf: string | null;
}

export interface PageFeedback {
  status: 'approved' | 'needs_revision' | 'rejected';
  feedback: string;
  timestamp: string;
}

export interface FeedbackMap {
  [pageNumber: string]: PageFeedback;
}
