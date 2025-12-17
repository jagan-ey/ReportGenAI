import React, { useState, useEffect } from 'react'
import ChatInterface from './components/ChatInterface'
import PredefinedQueries from './components/PredefinedQueries'
import PredefinedQueriesModal from './components/PredefinedQueriesModal'
import Settings from './components/Settings'
import Login from './components/Login'
import ApprovalsDashboard from './components/ApprovalsDashboard'
import { ThemeProvider } from './contexts/ThemeContext'
import { UserProvider, useUser } from './contexts/UserContext'
import './App.css'

function AppContent() {
  const { user, isAuthenticated } = useUser()
  const [predefinedQueries, setPredefinedQueries] = useState([])
  const [selectedQuery, setSelectedQuery] = useState(null)
  const [isQueriesModalOpen, setIsQueriesModalOpen] = useState(false)

  useEffect(() => {
    if (isAuthenticated) {
      // Load predefined queries on mount (only when authenticated and not approver)
      if (user?.role !== 'approver' && user?.role !== 'admin') {
        fetch('http://localhost:8000/api/chat/predefined')
          .then(res => res.json())
          .then(data => setPredefinedQueries(data.queries || []))
          .catch(err => console.error('Error loading queries:', err))
      }
    }
  }, [isAuthenticated, user?.role])

  const handleQuerySelect = (query) => {
    // Store both the question text and query_key for direct lookup
    setSelectedQuery({ question: query.question, queryKey: query.key })
  }

  // Show login screen if not authenticated
  if (!isAuthenticated) {
    return <Login />
  }

  // Show approvals dashboard for approvers/admins
  if (user?.role === 'approver' || user?.role === 'admin') {
    return (
      <div className="app">
        <header className="app-header">
          <div className="header-content">
            <div>
              <h1>GenAI CCM Platform</h1>
              <p>Approval Management • Review Requests</p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-md)' }}>
              <div style={{ 
                fontSize: '0.85rem', 
                color: 'var(--header-text-secondary)',
                marginRight: 'var(--spacing-sm)',
                fontWeight: 500
              }}>
                {user?.full_name || user?.username} ({user?.role})
              </div>
              <Settings />
            </div>
          </div>
        </header>
        <ApprovalsDashboard />
      </div>
    )
  }

  // Show main app for regular users
  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div>
            <h1>GenAI CCM Platform</h1>
            <p>Continuous Controls Monitoring • Talk to Data</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-md)' }}>
            <div style={{ 
              fontSize: '0.85rem', 
              color: 'var(--header-text-secondary)',
              marginRight: 'var(--spacing-sm)',
              fontWeight: 500
            }}>
              {user?.full_name || user?.username} ({user?.role})
            </div>
            <Settings />
          </div>
        </div>
      </header>
    
      <div className="app-container">
        <aside className="sidebar">
          <PredefinedQueries 
            queries={predefinedQueries}
            onSelect={handleQuerySelect}
            onExpand={() => setIsQueriesModalOpen(true)}
          />
        </aside>
        
        <main className="main-content">
          <ChatInterface 
            initialQuestion={selectedQuery}
            onQuestionSent={() => setSelectedQuery(null)}
          />
        </main>
      </div>

      <PredefinedQueriesModal
        isOpen={isQueriesModalOpen}
        onClose={() => setIsQueriesModalOpen(false)}
        queries={predefinedQueries}
        onSelect={handleQuerySelect}
      />
    </div>
  )
}

function App() {
  return (
    <ThemeProvider>
      <UserProvider>
        <AppContent />
      </UserProvider>
    </ThemeProvider>
  )
}

export default App

