import axios from 'axios'
import { getSSOToken, isSSOEnabled, clearSSOSession } from './sso'

// Use environment variable for API base URL, fallback to localhost for development
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Global reference to inactivity timer reset function
// This will be set by UserContext when it initializes
let globalResetInactivityTimer = null

// Track active API requests to prevent timeout during long-running queries
if (typeof window !== 'undefined') {
  window.activeFetchCount = window.activeFetchCount || 0
}

export const setInactivityTimerReset = (resetFn) => {
  globalResetInactivityTimer = resetFn
}

// Add request interceptor to include authentication headers and reset inactivity timer
api.interceptors.request.use((config) => {
  // Track active API requests
  if (typeof window !== 'undefined') {
    window.activeFetchCount = (window.activeFetchCount || 0) + 1
  }
  
  // Check if SSO is enabled and use SSO token
  if (isSSOEnabled()) {
    const ssoToken = getSSOToken()
    if (ssoToken) {
      config.headers['Authorization'] = `Bearer ${ssoToken}`
    }
  } else {
    // Legacy: Use X-User-ID header
    const userStr = localStorage.getItem('ccm_user')
    if (userStr) {
      try {
        const user = JSON.parse(userStr)
        if (user && user.username) {
          config.headers['X-User-ID'] = user.username
        }
      } catch (e) {
        localStorage.removeItem('ccm_user')
      }
    }
  }
  
  // API calls indicate user activity - reset inactivity timer
  if (globalResetInactivityTimer) {
    globalResetInactivityTimer()
  }
  
  return config
})

// Add response interceptor to handle 401 (unauthorized) errors and reset inactivity timer
api.interceptors.response.use(
  (response) => {
    // Decrement active request counter
    if (typeof window !== 'undefined' && window.activeFetchCount > 0) {
      window.activeFetchCount--
    }
    
    // Reset inactivity timer on successful API responses
    // This ensures that long-running queries don't timeout the user
    if (globalResetInactivityTimer) {
      globalResetInactivityTimer()
    }
    return response
  },
  async (error) => {
    // Decrement active request counter
    if (typeof window !== 'undefined' && window.activeFetchCount > 0) {
      window.activeFetchCount--
    }
    
    // Reset inactivity timer even on errors (except 401)
    // This prevents timeout during error handling
    if (error.response && error.response.status !== 401) {
      if (globalResetInactivityTimer) {
        globalResetInactivityTimer()
      }
    }
    
    // If backend returns 401, session is invalid - clear it
    if (error.response && error.response.status === 401) {
      if (isSSOEnabled()) {
        clearSSOSession()
        // Redirect to SSO login will be handled by Login component
      } else {
        localStorage.removeItem('ccm_user')
      }
      // The App.jsx will handle redirecting to login when isAuthenticated becomes false
    }
    return Promise.reject(error)
  }
)

// Auth API functions
export const login = async (username, password) => {
  try {
    const response = await api.post('/auth/login', {
      username,
      password
    })
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || error.message || 'Login failed')
  }
}

export const register = async (userData) => {
  try {
    const response = await api.post('/auth/users', userData)
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || error.message || 'Registration failed')
  }
}

export const sendQuery = async (
  question,
  usePredefined = true,
  queryKey = null,
  previousSqlQuery = null,
  followupAnswers = null,
  skipFollowups = false,
  mode = 'report'
) => {
  try {
    const response = await api.post('/chat/query', {
      question,
      query_key: queryKey,  // If provided, directly use this predefined query
      use_predefined: usePredefined,
      previous_sql_query: previousSqlQuery || null,
      followup_answers: followupAnswers || null,
      skip_followups: !!skipFollowups,
      mode,
    })
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || error.message || 'Failed to send query')
  }
}

export const getPredefinedQueries = async () => {
  try {
    const response = await api.get('/chat/predefined')
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || error.message || 'Failed to load queries')
  }
}

export const getSchema = async () => {
  try {
    const response = await api.get('/chat/schema')
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || error.message || 'Failed to load schema')
  }
}

// Report management functions
export const sendForApproval = async (reportData, userId = 'system') => {
  try {
    const response = await api.post('/reports/send-approval', reportData, {
      headers: {
        'X-User-ID': userId
      }
    })
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || error.message || 'Failed to send for approval')
  }
}

export const scheduleReport = async (scheduleData, userId = 'system') => {
  try {
    const response = await api.post('/reports/schedule', scheduleData, {
      headers: {
        'X-User-ID': userId
      }
    })
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || error.message || 'Failed to schedule report')
  }
}

export const getSchedules = async (userId = 'system') => {
  try {
    const response = await api.get('/reports/schedules', {
      headers: {
        'X-User-ID': userId
      }
    })
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || error.message || 'Failed to load schedules')
  }
}

export const getApprovals = async (userId = 'system', status = null) => {
  try {
    const params = status ? { status } : {}
    const response = await api.get('/reports/approvals', {
      params,
      headers: {
        'X-User-ID': userId
      }
    })
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || error.message || 'Failed to load approvals')
  }
}

export const getApprovers = async (userId = 'system') => {
  try {
    const response = await api.get('/reports/approvers', {
      headers: {
        'X-User-ID': userId
      }
    })
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || error.message || 'Failed to load approvers')
  }
}

export const approveRequest = async (approvalId, notes = null, userId = 'system') => {
  try {
    const response = await api.post(`/reports/approvals/${approvalId}/approve`, {
      notes
    }, {
      headers: {
        'X-User-ID': userId
      }
    })
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || error.message || 'Failed to approve request')
  }
}

export const rejectRequest = async (approvalId, notes, userId = 'system') => {
  try {
    const response = await api.post(`/reports/approvals/${approvalId}/reject`, {
      notes
    }, {
      headers: {
        'X-User-ID': userId
      }
    })
    return response.data
  } catch (error) {
    throw new Error(error.response?.data?.detail || error.message || 'Failed to reject request')
  }
}

