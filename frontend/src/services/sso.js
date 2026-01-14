/**
 * SSO Authentication Service
 * Handles OAuth2/OIDC, SAML, or other SSO flows
 * Works with backend SSO_ENABLED flag
 */

const SSO_ENABLED = import.meta.env.VITE_SSO_ENABLED === 'true'
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

/**
 * Check if SSO is enabled
 */
export const isSSOEnabled = () => {
  return SSO_ENABLED
}

/**
 * Get SSO login URL from backend
 */
export const getSSOLoginURL = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/sso/login-url`)
    if (response.ok) {
      const data = await response.json()
      return data.login_url
    }
    throw new Error('Failed to get SSO login URL')
  } catch (error) {
    console.error('Error getting SSO login URL:', error)
    throw error
  }
}

/**
 * Initiate SSO login - redirects to SSO provider
 */
export const initiateSSOLogin = async () => {
  if (!SSO_ENABLED) {
    throw new Error('SSO is not enabled')
  }
  
  try {
    const loginUrl = await getSSOLoginURL()
    // Redirect to SSO provider
    window.location.href = loginUrl
  } catch (error) {
    console.error('Error initiating SSO login:', error)
    throw error
  }
}

/**
 * Handle SSO callback after redirect from SSO provider
 * Exchanges authorization code for tokens
 */
export const handleSSOCallback = async (code) => {
  if (!SSO_ENABLED) {
    throw new Error('SSO is not enabled')
  }
  
  try {
    const response = await fetch(`${API_BASE_URL}/auth/sso/callback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ code })
    })
    
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'SSO callback failed')
    }
    
    const data = await response.json()
    
    // Store tokens securely
    if (data.token) {
      // Store access token in sessionStorage (less secure but works)
      // In production, consider using httpOnly cookies
      sessionStorage.setItem('sso_access_token', data.token)
      
      if (data.id_token) {
        sessionStorage.setItem('sso_id_token', data.id_token)
      }
      
      if (data.refresh_token) {
        sessionStorage.setItem('sso_refresh_token', data.refresh_token)
      }
      
      // Store user info in localStorage (for inactivity timeout)
      localStorage.setItem('ccm_user', JSON.stringify({
        user_id: data.user.user_id,
        username: data.user.username,
        email: data.user.email,
        role: data.user.role,
        full_name: data.user.full_name,
        department: data.user.department,
        loginTimestamp: Date.now() // For inactivity timeout
      }))
      
      return data.user
    }
    
    throw new Error('No token received from SSO callback')
  } catch (error) {
    console.error('SSO callback error:', error)
    clearSSOSession()
    throw error
  }
}

/**
 * Validate SSO token with backend
 * Used to check if session is still valid
 */
export const validateSSOToken = async () => {
  if (!SSO_ENABLED) {
    return null
  }
  
  const token = sessionStorage.getItem('sso_access_token')
  if (!token) {
    return null
  }
  
  try {
    const response = await fetch(`${API_BASE_URL}/auth/sso/validate`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    
    if (response.ok) {
      const user = await response.json()
      // Update localStorage with fresh user info
      localStorage.setItem('ccm_user', JSON.stringify({
        ...user,
        loginTimestamp: Date.now()
      }))
      return user
    } else {
      // Token invalid - clear session
      clearSSOSession()
      return null
    }
  } catch (error) {
    console.error('Error validating SSO token:', error)
    clearSSOSession()
    return null
  }
}

/**
 * Clear SSO session
 */
export const clearSSOSession = () => {
  sessionStorage.removeItem('sso_access_token')
  sessionStorage.removeItem('sso_id_token')
  sessionStorage.removeItem('sso_refresh_token')
  localStorage.removeItem('ccm_user')
}

/**
 * Get SSO access token
 */
export const getSSOToken = () => {
  return sessionStorage.getItem('sso_access_token')
}
