// Alpine.js job monitor page — mock jobs data (per spec: continues using mock data).
// Mounted by the SSR template at jobs.html via<script src="/dist/assets/jobs.js">
import type { Job } from '../api/types'

/**
 * Returns mock jobs for the jobs page.
 * Per spec: "will continue using mock data" — no real API polling in PR 2.
 */
export function getMockJobs(): Job[] {
  return [
    {
      id: 'job-1',
      type: 'Migration',
      status: 'running',
      progress: 65,
      created_at: new Date().toISOString(),
    },
    {
      id: 'job-2',
      type: 'Export',
      status: 'completed',
      progress: 100,
      created_at: new Date(Date.now() - 3600000).toISOString(),
      completed_at: new Date().toISOString(),
    },
    {
      id: 'job-3',
      type: 'Import',
      status: 'failed',
      progress: 30,
      created_at: new Date(Date.now() - 7200000).toISOString(),
      error: 'Connection timeout',
    },
  ]
}

/**
 * Format an ISO date string to a locale datetime string.
 */
export function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString()
}

// Expose globally for Alpine.js inline templates
declare global {
  interface Window {
    getMockJobs: typeof getMockJobs
    formatDate: typeof formatDate
  }
}

if (typeof window !== 'undefined') {
  window.getMockJobs = getMockJobs
  window.formatDate = formatDate
}
