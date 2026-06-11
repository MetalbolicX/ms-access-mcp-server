import { createApp } from 'vue'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './styles/variables.css'
import App from './App.vue'
import router from './router'

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