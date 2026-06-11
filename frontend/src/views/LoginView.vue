<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { connectionApi, setApiKey } from '../api/client'

const router = useRouter()
const apiKey = ref('')
const errorMessage = ref('')
const isLoading = ref(false)

async function handleAuthenticate() {
  errorMessage.value = ''
  isLoading.value = true

  try {
    // Probe the backend with the provided API key
    const result = await connectionApi.isConnected()
    if (result.connected) {
      // Save the API key on successful auth
      setApiKey(apiKey.value)
      router.push('/dashboard')
    } else {
      errorMessage.value = 'Authentication failed — check your API key'
    }
  } catch (err: unknown) {
    const error = err as Error
    if (error.message === 'Authentication required') {
      errorMessage.value = 'Invalid API key — authentication failed'
    } else {
      errorMessage.value = error.message || 'Connection failed'
    }
  } finally {
    isLoading.value = false
  }
}

function clearError() {
  if (errorMessage.value) {
    errorMessage.value = ''
  }
}
</script>

<template>
  <div class="login-view">
    <div class="login-card">
      <div class="login-header">
        <h1>MS Access MCP</h1>
        <p class="login-subtitle">Enter your API key to continue</p>
      </div>

      <form class="login-form" @submit.prevent="handleAuthenticate">
        <el-input
          v-model="apiKey"
          type="password"
          show-password
          placeholder="API Key"
          size="large"
          :disabled="isLoading"
          autocomplete="off"
          @input="clearError"
        />

        <el-alert
          v-if="errorMessage"
          type="error"
          :title="errorMessage"
          :closable="false"
          show-icon
        />

        <el-button
          type="primary"
          size="large"
          :disabled="isLoading || !apiKey"
          class="auth-button"
          @click="handleAuthenticate"
        >
          {{ isLoading ? 'Authenticating...' : 'Authenticate' }}
        </el-button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-view {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--color-bg-primary);
}

.login-card {
  width: 100%;
  max-width: 400px;
  padding: var(--space-8);
  background: var(--color-bg-secondary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
}

.login-header {
  text-align: center;
  margin-bottom: var(--space-6);
}

.login-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin: 0 0 var(--space-2);
}

.login-subtitle {
  color: var(--color-text-muted);
  margin: 0;
  font-size: 14px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.auth-button {
  width: 100%;
}
</style>