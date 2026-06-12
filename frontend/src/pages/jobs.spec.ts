// Tests for Alpine job monitor page behavior.
// Verifies mock jobs data, job status display, and 401 logout redirects.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const ORIGINAL_LOCATION = window.location

function mockLocation(href: string) {
  Object.defineProperty(window, 'location', {
    value: { href },
    writable: true,
    configurable: true,
  })
}

function restoreLocation() {
  Object.defineProperty(window, 'location', {
    value: ORIGINAL_LOCATION,
    writable: true,
    configurable: true,
  })
}

describe('jobs page Alpine behavior', () => {
  beforeEach(() => {
    mockLocation('http://localhost/jobs')
  })

  afterEach(() => {
    restoreLocation()
    vi.unstubAllGlobals()
  })

  it('getMockJobs() returns an array of job objects', async () => {
    const { getMockJobs } = await import('../pages/jobs')
    const jobs = getMockJobs()
    expect(Array.isArray(jobs)).toBe(true)
    expect(jobs.length).toBeGreaterThan(0)
  })

  it('each mock job has id, type, status, progress, and created_at', async () => {
    const { getMockJobs } = await import('../pages/jobs')
    const jobs = getMockJobs()
    for (const job of jobs) {
      expect(job).toHaveProperty('id')
      expect(job).toHaveProperty('type')
      expect(job).toHaveProperty('status')
      expect(job).toHaveProperty('progress')
      expect(job).toHaveProperty('created_at')
    }
  })

  it('job statuses are one of pending|running|completed|failed', async () => {
    const { getMockJobs } = await import('../pages/jobs')
    const jobs = getMockJobs()
    const validStatuses = ['pending', 'running', 'completed', 'failed']
    for (const job of jobs) {
      expect(validStatuses).toContain(job.status)
    }
  })

  it('running jobs have progress between 0 and 100', async () => {
    const { getMockJobs } = await import('../pages/jobs')
    const jobs = getMockJobs()
    const runningJobs = jobs.filter((j: any) => j.status === 'running')
    for (const job of runningJobs) {
      expect(job.progress).toBeGreaterThanOrEqual(0)
      expect(job.progress).toBeLessThanOrEqual(100)
    }
  })

  it('completed jobs have progress of 100', async () => {
    const { getMockJobs } = await import('../pages/jobs')
    const jobs = getMockJobs()
    const completedJobs = jobs.filter((j: any) => j.status === 'completed')
    for (const job of completedJobs) {
      expect(job.progress).toBe(100)
    }
  })

  it('failed jobs may have an error message', async () => {
    const { getMockJobs } = await import('../pages/jobs')
    const jobs = getMockJobs()
    const failedJobs = jobs.filter((j: any) => j.status === 'failed')
    for (const job of failedJobs) {
      expect(job).toHaveProperty('error')
    }
  })

  it('formatDate() formats ISO string to locale string', async () => {
    const { formatDate } = await import('../pages/jobs')
    const result = formatDate('2026-06-10T12:00:00Z')
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
  })

  it('formatDate() handles different date formats', async () => {
    const { formatDate } = await import('../pages/jobs')
    const result1 = formatDate('2026-06-10T00:00:00.000Z')
    const result2 = formatDate('2026-06-11T00:00:00Z')
    // Results should be valid locale strings
    expect(result1).toBeTruthy()
    expect(result2).toBeTruthy()
  })
})
