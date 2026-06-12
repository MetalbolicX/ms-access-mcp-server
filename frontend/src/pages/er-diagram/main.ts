// Vue 3 + Vue Flow ER diagram entry point.
// Mounts ErDiagramView.vue to #vue-app div on /er-diagram SSR page.
// Uses cookie-based auth via apiClient (no localStorage).
import { createApp } from 'vue'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import { VueFlow } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import ErDiagramView from '../../views/ErDiagramView.vue'
import '../../styles/variables.css'

// Initialize Vue app for ER diagram page
const vueApp = createApp(ErDiagramView)

// TanStack Query client for data fetching
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000,
      refetchOnWindowFocus: false,
    },
  },
})

vueApp.use(VueQueryPlugin, { queryClient })
vueApp.use(ElementPlus)
vueApp.use(VueFlow)

// Mount to #vue-app div (rendered by er_diagram.html SSR template)
const mountPoint = document.getElementById('vue-app')
if (!mountPoint) {
  throw new Error('ER diagram mount point #vue-app not found in DOM')
}

vueApp.mount(mountPoint)