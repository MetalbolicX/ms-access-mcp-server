// Tests for LoginView.vue — API key login form
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { useRouter } from 'vue-router'
import LoginView from './LoginView.vue'
import { connectionApi } from '../api/client'

// Mock the router
const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
}))

// Mock the connectionApi
vi.mock('../api/client', () => ({
  connectionApi: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    isConnected: vi.fn(),
  },
  getApiKey: vi.fn(),
  setApiKey: vi.fn(),
  clearApiKey: vi.fn(),
}))

function jsonResponse(body: unknown, ok = true): Response {
  return {
    ok,
    status: ok ? 200 : 500,
    statusText: ok ? 'OK' : 'Internal Server Error',
    json: () => Promise.resolve(body),
  } as unknown as Response
}

describe('LoginView', () => {
  let wrapper: ReturnType<typeof mount>

  beforeEach(() => {
    vi.clearAllMocks()
    wrapper = mount(LoginView, {
      global: {
        stubs: {
          'el-input': {
            template: '<input type="password" class="el-input" v-bind:value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
            props: ['modelValue'],
            emits: ['update:modelValue'],
          },
          'el-button': {
            template: '<button class="el-button" :disabled="disabled"><slot /></button>',
            props: ['type', 'disabled'],
          },
          'el-alert': {
            template: '<div class="el-alert" :class="type">{{ title }}</div>',
            props: ['type', 'title', 'show-icon'],
          },
        },
      },
    })
  })

  it('renders an API key input and authenticate button', () => {
    const inputs = wrapper.findAll('input')
    expect(inputs.length).toBeGreaterThan(0)
    const buttons = wrapper.findAll('button')
    expect(buttons.some((b) => b.text().toLowerCase().includes('authenticate'))).toBe(true)
  })

  it('calls isConnected to validate API key on form submit', async () => {
    const isConnectedMock = vi.mocked(connectionApi.isConnected)
    isConnectedMock.mockResolvedValueOnce({ connected: true, database: 'test.accdb' })

    // Simulate user typing an API key
    const input = wrapper.find('input')
    await input.setValue('test-api-key')

    // Click authenticate button
    const button = wrapper.findAll('button').find((b) =>
      b.text().toLowerCase().includes('authenticate'),
    )
    await button?.trigger('click')

    // Verify isConnected was called (probes with empty/invalid key to check auth)
    expect(isConnectedMock).toHaveBeenCalled()
  })

  it('redirects to /dashboard on successful authentication', async () => {
    const isConnectedMock = vi.mocked(connectionApi.isConnected)
    isConnectedMock.mockResolvedValueOnce({ connected: true, database: 'test.accdb' })

    const input = wrapper.find('input')
    await input.setValue('valid-api-key')

    const button = wrapper.findAll('button').find((b) =>
      b.text().toLowerCase().includes('authenticate'),
    )
    await button?.trigger('click')
    await flushPromises()

    expect(mockPush).toHaveBeenCalledWith('/dashboard')
  })

  it('shows error alert on authentication failure (401)', async () => {
    const isConnectedMock = vi.mocked(connectionApi.isConnected)
    isConnectedMock.mockRejectedValueOnce(new Error('Authentication required'))

    const input = wrapper.find('input')
    await input.setValue('invalid-api-key')

    const button = wrapper.findAll('button').find((b) =>
      b.text().toLowerCase().includes('authenticate'),
    )
    await button?.trigger('click')
    await flushPromises()

    // Error message should be shown in the alert element
    const alertEl = wrapper.find('.el-alert')
    expect(alertEl.exists()).toBe(true)
    // LoginView translates "Authentication required" to "Invalid API key — authentication failed"
    expect(alertEl.text()).toContain('Invalid API key')
  })

  it('shows error alert when isConnected throws a non-401 error', async () => {
    const isConnectedMock = vi.mocked(connectionApi.isConnected)
    isConnectedMock.mockRejectedValueOnce(new Error('Network error'))

    const input = wrapper.find('input')
    await input.setValue('some-key')

    const button = wrapper.findAll('button').find((b) =>
      b.text().toLowerCase().includes('authenticate'),
    )
    await button?.trigger('click')
    await flushPromises()

    const alertEl = wrapper.find('.el-alert')
    expect(alertEl.exists()).toBe(true)
    expect(alertEl.text()).toContain('Network error')
  })

  it('clears error message when user types in the input', async () => {
    const isConnectedMock = vi.mocked(connectionApi.isConnected)
    isConnectedMock.mockRejectedValueOnce(new Error('Authentication required'))

    const input = wrapper.find('input')
    await input.setValue('invalid-key')

    const button = wrapper.findAll('button').find((b) =>
      b.text().toLowerCase().includes('authenticate'),
    )
    await button?.trigger('click')
    await flushPromises()

    // Error should be shown
    expect(wrapper.find('.el-alert').exists()).toBe(true)

    // Now type something to clear error
    await input.setValue('new-key')

    // Error should be cleared
    expect(wrapper.find('.el-alert').exists()).toBe(false)
  })
})