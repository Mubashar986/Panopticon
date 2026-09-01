/**
 * Centralized API configuration for the Panopticon Frontend.
 * Single Source of Truth (SSOT) for backend endpoint resolution.
 */

export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export function getApiUrl(path: string): string {
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE}${cleanPath}`;
}
