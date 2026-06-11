<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { clearApiKey, getApiKey } from './api/client'

const router = useRouter()

function handleAuthRequired() {
  clearApiKey()
  if (router.currentRoute.value.path !== '/login') {
    router.push('/login')
  }
}

onMounted(() => {
  window.addEventListener('auth:required', handleAuthRequired)
})

onUnmounted(() => {
  window.removeEventListener('auth:required', handleAuthRequired)
})

function handleLogout() {
  clearApiKey()
  router.push('/login')
}
</script>

<template>
  <div class="app-layout">
    <header class="app-header">
      <div class="header-title">MS Access MCP</div>
      <div class="header-actions">
        <el-button v-if="getApiKey()" text @click="handleLogout">Logout</el-button>
        <el-button text>Settings</el-button>
      </div>
    </header>

    <aside class="app-sidebar">
      <div class="nav-section">
        <div class="nav-section-title">Overview</div>
        <RouterLink to="/dashboard" class="nav-item" active-class="active">
          <span>Dashboard</span>
        </RouterLink>
      </div>

      <div class="nav-section">
        <div class="nav-section-title">Database</div>
        <RouterLink to="/schema" class="nav-item" active-class="active">
          <span>Schema Explorer</span>
        </RouterLink>
        <RouterLink to="/er-diagram" class="nav-item" active-class="active">
          <span>ER Diagram</span>
        </RouterLink>
      </div>

      <div class="nav-section">
        <div class="nav-section-title">Operations</div>
        <RouterLink to="/jobs" class="nav-item" active-class="active">
          <span>Job Monitor</span>
        </RouterLink>
      </div>
    </aside>

    <main class="app-content">
      <RouterView />
    </main>
  </div>
</template>

<style>
/* Global reset */
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html,
body {
  height: 100%;
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

#app {
  height: 100%;
}

/* Element Plus dark overrides */
.el-button--primary {
  --el-button-bg-color: var(--color-accent);
  --el-button-border-color: var(--color-accent);
  --el-button-hover-bg-color: var(--color-accent-hover);
  --el-button-hover-border-color: var(--color-accent-hover);
}
</style>