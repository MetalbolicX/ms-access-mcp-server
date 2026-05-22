<script setup lang="ts">
import { ref } from 'vue'
import type { Job } from '../api/types'

// Mock jobs for demo (replace with real API when backend supports)
const jobs = ref<Job[]>([
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
])

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleString()
}
</script>

<template>
  <div class="job-monitor">
    <div class="monitor-header">
      <h1>Job Monitor</h1>
      <span class="job-count">{{ jobs.length }} jobs</span>
    </div>

    <div class="jobs-list">
      <div v-if="jobs.length === 0" class="empty-state data-card">
        <span>No jobs found</span>
      </div>

      <div
        v-for="job in jobs"
        :key="job.id"
        class="data-card job-card"
      >
        <div class="job-header">
          <div class="job-info">
            <span class="job-type">{{ job.type }}</span>
            <span :class="['status-badge', job.status]">
              {{ job.status }}
            </span>
          </div>
          <span class="job-date">{{ formatDate(job.created_at) }}</span>
        </div>

        <div v-if="job.status === 'running'" class="progress-section">
          <el-progress
            :percentage="job.progress"
            :stroke-width="8"
            :color="'var(--color-accent)'"
          />
          <span class="progress-text">{{ job.progress }}%</span>
        </div>

        <div v-if="job.error" class="error-section">
          <el-icon><WarningFilled /></el-icon>
          <span>{{ job.error }}</span>
        </div>

        <div v-if="job.completed_at" class="completed-section">
          <span class="completed-date">
            Completed at {{ formatDate(job.completed_at) }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.job-monitor {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.monitor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;

  & h1 {
    font-size: 24px;
    font-weight: 700;
    color: var(--color-text-primary);
    margin: 0;
  }

  & .job-count {
    color: var(--color-text-muted);
    font-size: 14px;
  }
}

.loading-state,
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-8);
  color: var(--color-text-muted);
}

.jobs-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.job-card {
  & .job-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--space-4);
  }

  & .job-info {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  & .job-type {
    font-weight: 600;
    color: var(--color-text-primary);
  }

  & .job-date {
    color: var(--color-text-muted);
    font-size: 12px;
  }
}

.progress-section {
  display: flex;
  align-items: center;
  gap: var(--space-4);

  & .el-progress {
    flex: 1;
  }

  & .progress-text {
    color: var(--color-text-secondary);
    font-size: 14px;
    min-width: 40px;
  }
}

.error-section {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-3);
  padding: var(--space-3);
  background: rgba(239, 68, 68, 0.1);
  border-radius: var(--radius-md);
  color: var(--color-error);
  font-size: 13px;
}

.completed-section {
  margin-top: var(--space-3);

  & .completed-date {
    color: var(--color-text-muted);
    font-size: 12px;
  }
}
</style>