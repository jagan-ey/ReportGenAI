import { useEffect, useRef, useCallback, useState } from 'react'

/**
 * Custom hook for tracking user inactivity and triggering logout
 * Industry standard: Tracks mouse, keyboard, clicks, and API activity
 * 
 * @param {Function} onTimeout - Callback when inactivity timeout is reached
 * @param {number} timeoutMs - Inactivity timeout in milliseconds (default: 30 seconds)
 * @param {boolean} enabled - Whether the inactivity tracking is enabled
 * @param {Function} onWarning - Optional callback when warning threshold is reached (e.g., 5 seconds before timeout)
 * @param {number} warningThresholdMs - Time before timeout to show warning (default: 5 seconds)
 */
export const useInactivityTimeout = (
  onTimeout, 
  timeoutMs = 30000, 
  enabled = true,
  onWarning = null,
  warningThresholdMs = 5000
) => {
  const timeoutRef = useRef(null)
  const warningTimeoutRef = useRef(null)
  const lastActivityRef = useRef(Date.now())
  const [timeRemaining, setTimeRemaining] = useState(timeoutMs)

  // Reset the inactivity timer
  const resetTimer = useCallback(() => {
    if (!enabled) return
    
    lastActivityRef.current = Date.now()
    
    // Clear existing timeouts
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    if (warningTimeoutRef.current) {
      clearTimeout(warningTimeoutRef.current)
    }
    
    // Reset time remaining
    setTimeRemaining(timeoutMs)
    
    // Set warning timeout (if callback provided)
    if (onWarning && warningThresholdMs < timeoutMs) {
      warningTimeoutRef.current = setTimeout(() => {
        // Check if still inactive (no activity since warning was set)
        const timeSinceLastActivity = Date.now() - lastActivityRef.current
        const remaining = timeoutMs - timeSinceLastActivity
        if (remaining <= warningThresholdMs && remaining > 0) {
          onWarning(remaining)
        }
      }, timeoutMs - warningThresholdMs)
    }
    
    // Set main timeout
    timeoutRef.current = setTimeout(() => {
      const timeSinceLastActivity = Date.now() - lastActivityRef.current
      
      // Check if there are any pending API requests
      // If so, extend the timeout to prevent logout during active queries
      const hasActiveRequests = typeof window !== 'undefined' && 
        (window.activeFetchCount || 0) > 0
      
      // Only trigger timeout if:
      // 1. No activity occurred during the timeout period, AND
      // 2. There are no active API requests (user is not waiting for a response)
      if (timeSinceLastActivity >= timeoutMs && !hasActiveRequests) {
        onTimeout()
      } else if (hasActiveRequests && timeSinceLastActivity >= timeoutMs) {
        // If there are active requests but timeout expired, extend it
        // This prevents logout while waiting for API responses
        // The timer will be reset when the response arrives
        const extendedTimeout = 10000 // Extend by 10 seconds
        timeoutRef.current = setTimeout(() => {
          const newTimeSinceLastActivity = Date.now() - lastActivityRef.current
          const stillHasActiveRequests = typeof window !== 'undefined' && 
            (window.activeFetchCount || 0) > 0
          if (newTimeSinceLastActivity >= timeoutMs && !stillHasActiveRequests) {
            onTimeout()
          }
        }, extendedTimeout)
      }
    }, timeoutMs)
  }, [onTimeout, timeoutMs, enabled, onWarning, warningThresholdMs])

  // Update time remaining periodically
  useEffect(() => {
    if (!enabled) return

    const interval = setInterval(() => {
      const elapsed = Date.now() - lastActivityRef.current
      const remaining = Math.max(0, timeoutMs - elapsed)
      setTimeRemaining(remaining)
    }, 1000)

    return () => clearInterval(interval)
  }, [enabled, timeoutMs])

  // Track user activity events
  useEffect(() => {
    if (!enabled) return

    // Events that indicate user activity
    const activityEvents = [
      'mousedown',
      'mousemove',
      'keypress',
      'scroll',
      'touchstart',
      'click',
      'keydown'
    ]

    // Add event listeners
    activityEvents.forEach(event => {
      document.addEventListener(event, resetTimer, true)
    })

    // Also track visibility changes (tab focus)
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        resetTimer()
      }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)

    // Initialize timer
    resetTimer()

    // Cleanup
    return () => {
      activityEvents.forEach(event => {
        document.removeEventListener(event, resetTimer, true)
      })
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
      if (warningTimeoutRef.current) {
        clearTimeout(warningTimeoutRef.current)
      }
    }
  }, [resetTimer, enabled])

  // Expose reset function and time remaining for manual activity tracking
  return { resetTimer, timeRemaining }
}
