import React, { createContext, useContext, useState, useEffect } from 'react'

const ThemeContext = createContext()

export const useTheme = () => {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider')
  }
  return context
}

const THEMES = {
  light: {
    name: 'Light',
    colors: {
      primary: '#2563eb',
      secondary: '#7c3aed',
      accent: '#06b6d4',
      success: '#10b981',
      warning: '#f59e0b',
      error: '#ef4444',
      info: '#3b82f6',
    }
  },
  dark: {
    name: 'Dark',
    colors: {
      primary: '#3b82f6',
      secondary: '#8b5cf6',
      accent: '#22d3ee',
      success: '#34d399',
      warning: '#fbbf24',
      error: '#f87171',
      info: '#60a5fa',
    }
  },
  axis: {
    name: 'Axis Bank',
    colors: {
      primary: '#AE275F', // X11 Maroon (Axis theme primary)
      secondary: '#EB1165', // Ruby (Axis theme secondary)
      accent: '#EB1165', // Keep accent aligned to Ruby
      success: '#10b981', // Green for success
      warning: '#f59e0b', // Amber for warnings
      error: '#dc2626', // Darker red for errors
      info: '#AE275F', // Maroon for info
    }
  },
  blue: {
    name: 'Ocean Blue',
    colors: {
      primary: '#0ea5e9',
      secondary: '#0284c7',
      accent: '#06b6d4',
      success: '#10b981',
      warning: '#f59e0b',
      error: '#ef4444',
      info: '#3b82f6',
    }
  },
  purple: {
    name: 'Royal Purple',
    colors: {
      primary: '#8b5cf6',
      secondary: '#7c3aed',
      accent: '#a78bfa',
      success: '#10b981',
      warning: '#f59e0b',
      error: '#ef4444',
      info: '#3b82f6',
    }
  },
  green: {
    name: 'Forest Green',
    colors: {
      primary: '#10b981',
      secondary: '#059669',
      accent: '#34d399',
      success: '#059669',
      warning: '#f59e0b',
      error: '#ef4444',
      info: '#3b82f6',
    }
  },
  orange: {
    name: 'Sunset Orange',
    colors: {
      primary: '#f97316',
      secondary: '#ea580c',
      accent: '#fb923c',
      success: '#10b981',
      warning: '#f59e0b',
      error: '#ef4444',
      info: '#3b82f6',
    }
  },
}

export const ThemeProvider = ({ children }) => {
  const [isDarkMode, setIsDarkMode] = useState(() => {
    const saved = localStorage.getItem('darkMode')
    return saved ? JSON.parse(saved) : false
  })
  
  const [colorTheme, setColorTheme] = useState(() => {
    return localStorage.getItem('colorTheme') || 'light'
  })

  useEffect(() => {
    localStorage.setItem('darkMode', JSON.stringify(isDarkMode))
    document.documentElement.setAttribute('data-theme', isDarkMode ? 'dark' : 'light')
  }, [isDarkMode])

  useEffect(() => {
    localStorage.setItem('colorTheme', colorTheme)
    const theme = THEMES[colorTheme]
    if (theme) {
      // Primary colors
      document.documentElement.style.setProperty('--primary-color', theme.colors.primary)
      document.documentElement.style.setProperty('--primary-dark', darkenColor(theme.colors.primary))
      document.documentElement.style.setProperty('--primary-light', lightenColor(theme.colors.primary))
      
      // Secondary colors
      document.documentElement.style.setProperty('--secondary-color', theme.colors.secondary)
      document.documentElement.style.setProperty('--secondary-dark', darkenColor(theme.colors.secondary))
      document.documentElement.style.setProperty('--secondary-light', lightenColor(theme.colors.secondary))
      
      // Accent colors
      document.documentElement.style.setProperty('--accent-color', theme.colors.accent)
      
      // Semantic colors
      document.documentElement.style.setProperty('--success-color', theme.colors.success)
      document.documentElement.style.setProperty('--warning-color', theme.colors.warning)
      document.documentElement.style.setProperty('--error-color', theme.colors.error)
      document.documentElement.style.setProperty('--info-color', theme.colors.info)
      
      // Header colors - use primary color for header, or burgundy for Axis theme
      if (colorTheme === 'axis') {
        document.documentElement.style.setProperty('--header-bg-start', '#AE275F')
        document.documentElement.style.setProperty('--header-bg-end', '#EB1165')
        document.documentElement.style.setProperty('--header-text', '#ffffff')
        document.documentElement.style.setProperty('--header-text-secondary', 'rgba(255, 255, 255, 0.9)')
      } else {
        document.documentElement.style.setProperty('--header-bg-start', theme.colors.primary)
        document.documentElement.style.setProperty('--header-bg-end', theme.colors.secondary || theme.colors.primary)
        document.documentElement.style.setProperty('--header-text', '#ffffff')
        document.documentElement.style.setProperty('--header-text-secondary', 'rgba(255, 255, 255, 0.9)')
      }
      
      // Lighter variants for backgrounds (15% opacity)
      const hexToRgb = (hex) => {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
        return result ? {
          r: parseInt(result[1], 16),
          g: parseInt(result[2], 16),
          b: parseInt(result[3], 16)
        } : null
      }
      
      const rgb = hexToRgb(theme.colors.success)
      if (rgb) {
        document.documentElement.style.setProperty('--success-bg', `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.1)`)
      }
      
      const warningRgb = hexToRgb(theme.colors.warning)
      if (warningRgb) {
        document.documentElement.style.setProperty('--warning-bg', `rgba(${warningRgb.r}, ${warningRgb.g}, ${warningRgb.b}, 0.1)`)
      }
      
      const errorRgb = hexToRgb(theme.colors.error)
      if (errorRgb) {
        document.documentElement.style.setProperty('--error-bg', `rgba(${errorRgb.r}, ${errorRgb.g}, ${errorRgb.b}, 0.1)`)
      }
      
      const infoRgb = hexToRgb(theme.colors.info)
      if (infoRgb) {
        document.documentElement.style.setProperty('--info-bg', `rgba(${infoRgb.r}, ${infoRgb.g}, ${infoRgb.b}, 0.1)`)
      }
    }
  }, [colorTheme, isDarkMode]) // Also update when dark mode changes

  const toggleDarkMode = () => {
    setIsDarkMode(prev => !prev)
  }

  return (
    <ThemeContext.Provider
      value={{
        isDarkMode,
        toggleDarkMode,
        colorTheme,
        setColorTheme,
        themes: THEMES,
      }}
    >
      {children}
    </ThemeContext.Provider>
  )
}

// Helper functions to adjust color brightness
function darkenColor(color) {
  const hex = color.replace('#', '')
  const r = Math.max(0, parseInt(hex.substring(0, 2), 16) - 30)
  const g = Math.max(0, parseInt(hex.substring(2, 4), 16) - 30)
  const b = Math.max(0, parseInt(hex.substring(4, 6), 16) - 30)
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

function lightenColor(color) {
  const hex = color.replace('#', '')
  const r = Math.min(255, parseInt(hex.substring(0, 2), 16) + 30)
  const g = Math.min(255, parseInt(hex.substring(2, 4), 16) + 30)
  const b = Math.min(255, parseInt(hex.substring(4, 6), 16) + 30)
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

