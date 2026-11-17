const configuredApi = import.meta.env.VITE_API_URL?.trim();
export const API = (configuredApi || "/api").replace(/\/+$/, "");

export async function apiRequest(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    credentials: "include",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new Error(body.detail || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return response;
}
