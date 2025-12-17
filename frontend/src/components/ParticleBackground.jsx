import React, { useEffect, useRef } from 'react'
import { useTheme } from '../contexts/ThemeContext'
import './ParticleBackground.css'

function ParticleBackground() {
  const containerRef = useRef(null)
  const { colorTheme } = useTheme()

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    // Clear existing particles
    container.innerHTML = ''

    // Get theme colors
    const getThemeColors = () => {
      const themes = {
        light: { primary: '#2563eb', secondary: '#7c3aed', accent: '#06b6d4' },
        dark: { primary: '#3b82f6', secondary: '#8b5cf6', accent: '#22d3ee' },
        axis: { primary: '#AE275F', secondary: '#EB1165', accent: '#EB1165' },
        blue: { primary: '#0ea5e9', secondary: '#0284c7', accent: '#06b6d4' },
        purple: { primary: '#8b5cf6', secondary: '#7c3aed', accent: '#a78bfa' },
        green: { primary: '#10b981', secondary: '#059669', accent: '#34d399' },
        orange: { primary: '#f97316', secondary: '#ea580c', accent: '#fb923c' }
      }
      return themes[colorTheme] || themes.light
    }

    const colors = getThemeColors()
    const numParticles = 80

    // Create particles
    for (let i = 0; i < numParticles; i++) {
      const particle = document.createElement('span')
      particle.className = 'particle'
      
      // Random size (2px to 6px)
      const size = Math.random() * 4 + 2
      particle.style.width = `${size}px`
      particle.style.height = `${size}px`
      
      // Random position
      particle.style.left = `${Math.random() * 100}%`
      particle.style.top = `${Math.random() * 100}%`
      
      // Random color from theme
      const colorKeys = Object.keys(colors)
      const randomColor = colors[colorKeys[Math.floor(Math.random() * colorKeys.length)]]
      
      // Convert hex to rgba with opacity
      const hexToRgba = (hex, opacity) => {
        const r = parseInt(hex.slice(1, 3), 16)
        const g = parseInt(hex.slice(3, 5), 16)
        const b = parseInt(hex.slice(5, 7), 16)
        return `rgba(${r}, ${g}, ${b}, ${opacity})`
      }
      
      // Darker, more visible particles
      const particleColor = hexToRgba(randomColor, 0.4)
      const glowColor = hexToRgba(randomColor, 0.2)
      
      particle.style.background = `radial-gradient(circle, ${particleColor} 0%, transparent 70%)`
      particle.style.boxShadow = `0 0 ${size * 2}px ${size}px ${glowColor}`
      
      // Random animation duration (20s to 40s)
      const duration = Math.random() * 20 + 20
      particle.style.animationDuration = `${duration}s`
      
      // Random delay
      const delay = Math.random() * 5
      particle.style.animationDelay = `${delay}s`
      
      // Random animation direction
      const direction = Math.random() > 0.5 ? 'normal' : 'reverse'
      particle.style.animationDirection = direction
      
      container.appendChild(particle)
    }

    return () => {
      if (container) {
        container.innerHTML = ''
      }
    }
  }, [colorTheme])

  return <div ref={containerRef} className="particle-background" />
}

export default ParticleBackground

