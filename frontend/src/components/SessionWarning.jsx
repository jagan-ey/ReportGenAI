import React, { useState, useEffect } from 'react'
import './SessionWarning.css'

/**
 * SessionWarning component
 * Displays a warning modal when user is about to be logged out due to inactivity
 * Shows countdown and allows user to stay logged in
 */
const SessionWarning = ({ onStayLoggedIn, onLogout, timeRemaining }) => {
  const [countdown, setCountdown] = useState(Math.ceil(timeRemaining / 1000))

  useEffect(() => {
    setCountdown(Math.ceil(timeRemaining / 1000))
    const interval = setInterval(() => {
      const remaining = Math.ceil(timeRemaining / 1000)
      setCountdown(remaining)
      if (remaining <= 0) {
        clearInterval(interval)
      }
    }, 1000)

    return () => clearInterval(interval)
  }, [timeRemaining])

  if (timeRemaining <= 0) {
    return null // Don't show if already timed out
  }

  return (
    <div className="session-warning-overlay">
      <div className="session-warning-modal">
        <div className="session-warning-icon">⏱️</div>
        <h2>Session Timeout Warning</h2>
        <p>
          Your session will expire due to inactivity in{' '}
          <strong>{countdown} second{countdown !== 1 ? 's' : ''}</strong>.
        </p>
        <p className="session-warning-subtitle">
          Click "Stay Logged In" to continue your session.
        </p>
        <div className="session-warning-actions">
          <button
            className="session-warning-button stay-logged-in"
            onClick={onStayLoggedIn}
          >
            Stay Logged In
          </button>
          <button
            className="session-warning-button logout-now"
            onClick={onLogout}
          >
            Logout Now
          </button>
        </div>
      </div>
    </div>
  )
}

export default SessionWarning
