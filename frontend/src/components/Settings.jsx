import React, { useState, useRef, useEffect } from 'react'
import { useTheme } from '../contexts/ThemeContext'
import { useUser } from '../contexts/UserContext'
import './Settings.css'

function Settings() {
  const { isDarkMode, toggleDarkMode, colorTheme, setColorTheme, themes } = useTheme()
  const { logout } = useUser()
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef(null)

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  return (
    <div className="settings-container" ref={dropdownRef}>
      <button
        className="settings-button"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Settings"
        title="Settings"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M12 1v6m0 6v6M5.64 5.64l4.24 4.24m4.24 4.24l4.24 4.24M1 12h6m6 0h6M5.64 18.36l4.24-4.24m4.24-4.24l4.24-4.24"></path>
        </svg>
      </button>

      {isOpen && (
        <div className="settings-dropdown">
          <div className="settings-section">
            <div className="settings-section-title">Appearance</div>
            
            {/* Dark Mode Toggle */}
            <div className="settings-item">
              <div className="settings-item-label">
                <span>Dark Mode</span>
                <span className="settings-item-description">Switch between light and dark theme</span>
              </div>
              <label className="toggle-switch">
                <input
                  type="checkbox"
                  checked={isDarkMode}
                  onChange={toggleDarkMode}
                />
                <span className="toggle-slider"></span>
              </label>
            </div>

            {/* Color Theme Selector */}
            <div className="settings-item">
              <div className="settings-item-label">
                <span>Color Theme</span>
                <span className="settings-item-description">Choose your preferred color scheme</span>
              </div>
              <div className="color-theme-grid">
                {Object.entries(themes)
                  .filter(([key]) => key !== 'dark') // Exclude dark from color themes (it's handled by dark mode toggle)
                  .map(([key, theme]) => (
                    <button
                      key={key}
                      className={`color-theme-option ${colorTheme === key ? 'active' : ''}`}
                      onClick={() => setColorTheme(key)}
                      title={theme.name}
                      style={{
                        '--theme-primary': theme.colors.primary,
                        '--theme-secondary': theme.colors.secondary,
                      }}
                    >
                      <div className="color-theme-preview">
                        <div
                          className="color-theme-primary"
                          style={{ backgroundColor: theme.colors.primary }}
                        ></div>
                        <div
                          className="color-theme-secondary"
                          style={{ backgroundColor: theme.colors.secondary }}
                        ></div>
                      </div>
                      <span className="color-theme-name">{theme.name}</span>
                    </button>
                  ))}
              </div>
            </div>
          </div>
          
          {/* User Section */}
          <div className="settings-section">
            <div className="settings-section-title">Account</div>
            <div className="settings-item">
              <button
                className="logout-button"
                onClick={() => {
                  if (window.confirm('Are you sure you want to logout?')) {
                    logout()
                  }
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                  <polyline points="16 17 21 12 16 7"></polyline>
                  <line x1="21" y1="12" x2="9" y2="12"></line>
                </svg>
                Logout
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Settings

