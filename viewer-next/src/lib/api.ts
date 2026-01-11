const API_BASE = '/api';

export async function fetchProjects() {
  const res = await fetch(`${API_BASE}/projects`);
  if (!res.ok) throw new Error('Failed to fetch projects');
  return res.json();
}

export async function fetchProject(name: string) {
  const res = await fetch(`${API_BASE}/project/${encodeURIComponent(name)}`);
  if (!res.ok) throw new Error('Failed to fetch project');
  return res.json();
}

export async function fetchFeedback(projectName: string) {
  const res = await fetch(`${API_BASE}/project/${encodeURIComponent(projectName)}/feedback`);
  if (!res.ok) throw new Error('Failed to fetch feedback');
  return res.json();
}

export async function saveFeedback(data: {
  project: string;
  page: number;
  status: string;
  feedback: string;
  timestamp: string;
}) {
  const res = await fetch(`${API_BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to save feedback');
  return res.json();
}

export function getOriginalUrl(project: string, page: number) {
  return `${API_BASE}/project/${encodeURIComponent(project)}/page/${page}/original`;
}

export function getHtmlUrl(project: string, page: number) {
  return `${API_BASE}/project/${encodeURIComponent(project)}/page/${page}/html`;
}

export function getIterationUrl(project: string, page: number, iteration: number) {
  return `${API_BASE}/project/${encodeURIComponent(project)}/page/${page}/iteration/${iteration}`;
}

export function getRenderedUrl(project: string, page: number, iteration: number) {
  return `${API_BASE}/project/${encodeURIComponent(project)}/page/${page}/rendered/${iteration}`;
}
