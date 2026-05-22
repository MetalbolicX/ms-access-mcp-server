import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './styles/variables.css'
import App from './App.vue'

// Import views
import DashboardView from './views/DashboardView.vue'
import SchemaExplorerView from './views/SchemaExplorerView.vue'
import JobMonitorView from './views/JobMonitorView.vue'

// Router configuration
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', component: DashboardView, name: 'dashboard' },
    { path: '/schema', component: SchemaExplorerView, name: 'schema' },
    { path: '/jobs', component: JobMonitorView, name: 'jobs' },
  ],
})

// TanStack Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000,
      refetchOnWindowFocus: false,
    },
  },
})

const app = createApp(App)

app.use(router)
app.use(ElementPlus)
app.use(VueQueryPlugin, { queryClient })

app.mount('#app')