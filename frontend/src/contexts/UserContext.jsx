import React, { createContext, useContext, useState, useEffect } from 'react'

const UserContext = createContext()

export const useUser = () => {
  const context = useContext(UserContext)
  if (!context) {
    throw new Error('useUser must be used within UserProvider')
  }
  return context
}

export const UserProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    // Load from localStorage
    const saved = localStorage.getItem('ccm_user')
    return saved ? JSON.parse(saved) : null
  })
  const [isAuthenticated, setIsAuthenticated] = useState(!!user)

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
    setUser(null)
    setIsAuthenticated(false)
  }

  return (
    <UserContext.Provider
      value={{
        user,
        isAuthenticated,
        login,
        logout,
      }}
    >
      {children}
    </UserContext.Provider>
  )
}

