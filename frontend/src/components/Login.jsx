import React, { useState } from 'react'
import { useUser } from '../contexts/UserContext'
import './Login.css'

function Login() {
  const { login } = useUser()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showRegister, setShowRegister] = useState(false)
  
  // Registration form state
  const [regData, setRegData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    fullName: '',
    department: ''
  })

  const handleLogin = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await fetch('http://localhost:8000/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: username,
          password: password
        })
      })

      const data = await response.json()

      if (response.ok) {
        // Store user info and login
        login({
          user_id: data.user.user_id,
          username: data.user.username,
          email: data.user.email,
          full_name: data.user.full_name,
          role: data.user.role,
          department: data.user.department
        })
      } else {
        setError(data.detail || 'Login failed. Please check your credentials.')
      }
    } catch (error) {
      setError('Error connecting to server. Please try again.')
      console.error('Login error:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (e) => {
    e.preventDefault()
    setError('')

    // Validate passwords match
    if (regData.password !== regData.confirmPassword) {
      setError('Passwords do not match')
      return
    }

    // Validate password length
    if (regData.password.length < 6) {
      setError('Password must be at least 6 characters')
      return
    }

    setLoading(true)

    try {
      const response = await fetch('http://localhost:8000/api/auth/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: regData.username,
          email: regData.email,
          password: regData.password,
          full_name: regData.fullName,
          role: 'user', // Default role for new registrations
          department: regData.department || null
        })
      })

      const data = await response.json()

      if (response.ok) {
        // Auto-login after registration
        login({
          user_id: data.user.user_id,
          username: data.user.username,
          email: data.user.email,
          full_name: data.user.full_name,
          role: data.user.role,
          department: data.user.department
        })
      } else {
        setError(data.detail || 'Registration failed. Please try again.')
      }
    } catch (error) {
      setError('Error connecting to server. Please try again.')
      console.error('Registration error:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>GenAI CCM Platform</h1>
          <p>Continuous Controls Monitoring • Talk to Data</p>
        </div>

        {!showRegister ? (
          <div className="login-content">
            <h2>Sign In</h2>
            <p className="login-subtitle">
              Enter your username/email and password to continue
            </p>

            {error && (
              <div className="error-message">
                {error}
              </div>
            )}

            <form onSubmit={handleLogin} className="login-form">
              <div className="form-group">
                <label htmlFor="username">Username or Email:</label>
                <input
                  id="username"
                  type="text"
                  className="form-input"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter username or email"
                  required
                  autoFocus
                />
              </div>

              <div className="form-group">
                <label htmlFor="password">Password:</label>
                <input
                  id="password"
                  type="password"
                  className="form-input"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  required
                />
              </div>

              <button type="submit" className="login-button" disabled={loading}>
                {loading ? 'Signing in...' : 'Sign In'}
              </button>
            </form>

            <div className="login-footer">
              <p>
                Don't have an account?{' '}
                <button
                  type="button"
                  className="link-button"
                  onClick={() => setShowRegister(true)}
                >
                  Register here
                </button>
              </p>
            </div>
          </div>
        ) : (
          <div className="login-content">
            <h2>Create Account</h2>
            <p className="login-subtitle">
              Register for a new account
            </p>

            {error && (
              <div className="error-message">
                {error}
              </div>
            )}

            <form onSubmit={handleRegister} className="login-form">
              <div className="form-group">
                <label htmlFor="reg-username">Username:</label>
                <input
                  id="reg-username"
                  type="text"
                  className="form-input"
                  value={regData.username}
                  onChange={(e) => setRegData({ ...regData, username: e.target.value })}
                  placeholder="Choose a username"
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="reg-email">Email:</label>
                <input
                  id="reg-email"
                  type="email"
                  className="form-input"
                  value={regData.email}
                  onChange={(e) => setRegData({ ...regData, email: e.target.value })}
                  placeholder="Enter your email"
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="reg-fullname">Full Name:</label>
                <input
                  id="reg-fullname"
                  type="text"
                  className="form-input"
                  value={regData.fullName}
                  onChange={(e) => setRegData({ ...regData, fullName: e.target.value })}
                  placeholder="Enter your full name"
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="reg-department">Department (Optional):</label>
                <input
                  id="reg-department"
                  type="text"
                  className="form-input"
                  value={regData.department}
                  onChange={(e) => setRegData({ ...regData, department: e.target.value })}
                  placeholder="Enter department"
                />
              </div>

              <div className="form-group">
                <label htmlFor="reg-password">Password:</label>
                <input
                  id="reg-password"
                  type="password"
                  className="form-input"
                  value={regData.password}
                  onChange={(e) => setRegData({ ...regData, password: e.target.value })}
                  placeholder="Minimum 6 characters"
                  required
                  minLength={6}
                />
              </div>

              <div className="form-group">
                <label htmlFor="reg-confirm">Confirm Password:</label>
                <input
                  id="reg-confirm"
                  type="password"
                  className="form-input"
                  value={regData.confirmPassword}
                  onChange={(e) => setRegData({ ...regData, confirmPassword: e.target.value })}
                  placeholder="Re-enter password"
                  required
                />
              </div>

              <button type="submit" className="login-button" disabled={loading}>
                {loading ? 'Creating account...' : 'Create Account'}
              </button>
            </form>

            <div className="login-footer">
              <p>
                Already have an account?{' '}
                <button
                  type="button"
                  className="link-button"
                  onClick={() => {
                    setShowRegister(false)
                    setError('')
                  }}
                >
                  Sign in here
                </button>
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default Login
