import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import { useInactivityTimeout } from '../hooks/useInactivityTimeout'
import { setInactivityTimerReset } from '../services/api'
import { isSSOEnabled, clearSSOSession, initiateSSOLogin } from '../services/sso'
import SessionWarning from '../components/SessionWarning'

const UserContext = createContext()

// Industry standard: Inactivity timeout (30 seconds as per user requirement)
// Note: Industry standards typically recommend 15-30 minutes, but user requested 30 seconds for high security
const INACTIVITY_TIMEOUT_MS = 30 * 10000 // 30 seconds
const WARNING_THRESHOLD_MS = 5 * 10000 // Show warning 5 seconds before timeout

export const useUser = () => {
  const context = useContext(UserContext)
  if (!context) {
    throw new Error('useUser must be used within UserProvider')
  }
  return context
}

export const UserProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    // Load from localStorage (no expiration check on load - we use inactivity timeout instead)
    const saved = localStorage.getItem('ccm_user')
    if (!saved) return null
    
    try {
      return JSON.parse(saved)
    } catch (e) {
      // Invalid data - clear it
      localStorage.removeItem('ccm_user')
      return null
    }
  })
  const [isAuthenticated, setIsAuthenticated] = useState(!!user)
  const [showWarning, setShowWarning] = useState(false)
  const [warningTimeRemaining, setWarningTimeRemaining] = useState(0)
  const resetTimerRef = useRef(null)

  // Handle inactivity timeout - logout user after period of inactivity
  const handleInactivityTimeout = useCallback(() => {
    console.log('Session timeout due to inactivity')
    setShowWarning(false)
    
    if (isSSOEnabled()) {
      // Clear SSO session
      clearSSOSession()
      // Redirect to SSO login (will be handled by Login component)
    } else {
      // Legacy logout
      setUser(null)
      setIsAuthenticated(false)
      localStorage.removeItem('ccm_user')
    }
  }, [])

  // Handle warning threshold - show warning modal
  const handleWarning = useCallback((timeRemaining) => {
    // Only show warning if user is still authenticated
    if (isAuthenticated) {
      setWarningTimeRemaining(timeRemaining)
      setShowWarning(true)
    }
  }, [isAuthenticated])

  // Set up inactivity tracking when user is authenticated
  const { resetTimer, timeRemaining } = useInactivityTimeout(
    handleInactivityTimeout,
    INACTIVITY_TIMEOUT_MS,
    isAuthenticated, // Only track when authenticated
    handleWarning,
    WARNING_THRESHOLD_MS
  )

  // Wrapper to reset timer and clear warning
  // Defined early so it can be used in useEffect
  const resetTimerWithWarningClear = useCallback(() => {
    setShowWarning(false)
    resetTimer()
  }, [resetTimer])

  // Update warning time remaining and hide warning if timer was reset
  useEffect(() => {
    if (showWarning) {
      // If time remaining increased (timer was reset), hide warning
      if (timeRemaining > warningTimeRemaining) {
        setShowWarning(false)
      } else {
        setWarningTimeRemaining(timeRemaining)
      }
    }
  }, [timeRemaining, showWarning, warningTimeRemaining])

  // Store resetTimer in ref and expose it globally for API interceptor
  useEffect(() => {
    resetTimerRef.current = resetTimer
    if (isAuthenticated && resetTimer) {
      // Expose reset function globally so API interceptor can call it
      // Use wrapper to also clear warning if it's showing
      setInactivityTimerReset(resetTimerWithWarningClear)
    } else {
      setInactivityTimerReset(null)
    }
  }, [resetTimer, isAuthenticated, resetTimerWithWarningClear])

  useEffect(() => {
    if (user) {
      localStorage.setItem('ccm_user', JSON.stringify(user))
      setIsAuthenticated(true)
    } else {
      localStorage.removeItem('ccm_user')
      setIsAuthenticated(false)
    }
  }, [user])

  const login = (userData) => {
    setUser(userData)
    setIsAuthenticated(true)
  }

  const logout = () => {
    setShowWarning(false)
    
    if (isSSOEnabled()) {
      // Clear SSO session
      clearSSOSession()
    } else {
      // Legacy logout
      setUser(null)
      setIsAuthenticated(false)
      localStorage.removeItem('ccm_user')
    }
  }

  const handleStayLoggedIn = useCallback(() => {
    setShowWarning(false)
    resetTimer() // Reset the inactivity timer
  }, [resetTimer])

  // Expose resetTimer so components can manually reset if needed
  return (
    <UserContext.Provider
      value={{
        user,
        isAuthenticated,
        login,
        logout,
        resetInactivityTimer: resetTimer, // Allow manual reset (e.g., on API calls)
      }}
    >
      {children}
      {showWarning && isAuthenticated && (
        <SessionWarning
          onStayLoggedIn={handleStayLoggedIn}
          onLogout={logout}
          timeRemaining={warningTimeRemaining}
        />
      )}
    </UserContext.Provider>
  )
}

