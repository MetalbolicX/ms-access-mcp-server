// Router configuration with auth guard — extracted from main.ts
import { createRouter, createWebHistory, type Router } from 'vue-router'
import { getApiKey } from '../api/client'

// Import views
import DashboardView from '../views/DashboardView.vue'
import SchemaExplorerView from '../views/SchemaExplorerView.vue'
import JobMonitorView from '../views/JobMonitorView.vue'
import ErDiagramView from '../views/ErDiagramView.vue'
import LoginView from '../views/LoginView.vue'

const router: Router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/login', component: LoginView, name: 'login' },
    { path: '/dashboard', component: DashboardView, name: 'dashboard' },
    { path: '/schema', component: SchemaExplorerView, name: 'schema' },
    { path: '/er-diagram', component: ErDiagramView, name: 'er-diagram' },
    { path: '/jobs', component: JobMonitorView, name: 'jobs' },
  ],
})

// Auth guard — redirect to /login for all protected routes when no apiKey
router.beforeEach((to, _from) => {
  if (to.path !== '/login' && !getApiKey()) {
    return '/login'
  }
})

export default router