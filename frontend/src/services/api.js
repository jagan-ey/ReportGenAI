import axios from 'axios'

// Use environment variable for API base URL, fallback to localhost for development
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add request interceptor to include user ID in headers
api.interceptors.request.use((config) => {
  const user = JSON.parse(localStorage.getItem('ccm_user') || 'null')
  if (user && user.username) {
    config.headers['X-User-ID'] = user.username
  }
  return config
})

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
  skipFollowups = false
) => {
  try {
    const response = await api.post('/chat/query', {
      question,
      query_key: queryKey,  // If provided, directly use this predefined query
      use_predefined: usePredefined,
      previous_sql_query: previousSqlQuery || null,
      followup_answers: followupAnswers || null,
      skip_followups: !!skipFollowups,
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

