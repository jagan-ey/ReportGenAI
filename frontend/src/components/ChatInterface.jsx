import React, { useState, useEffect, useRef } from 'react'
import { sendQuery } from '../services/api'
import { useUser } from '../contexts/UserContext'
import ApproverModal from './ApproverModal'
import SpeechToText from './SpeechToText'
import FollowUpQuestions from './FollowUpQuestions'
import './ChatInterface.css'

function ChatInterface({ initialQuestion, onQuestionSent }) {
  const { user } = useUser()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingStatus, setLoadingStatus] = useState('Processing your query...')
  const [lastSqlQuery, setLastSqlQuery] = useState(null)
  const [showApproverModal, setShowApproverModal] = useState(false)
  const [pendingApprovalMessage, setPendingApprovalMessage] = useState(null)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    if (initialQuestion) {
      // Handle both string (old) and object (new) format
      const questionText = typeof initialQuestion === 'string' 
        ? initialQuestion 
        : initialQuestion.question
      const queryKey = typeof initialQuestion === 'object' 
        ? initialQuestion.queryKey 
        : null
      
      setInput(questionText)
      handleSend(questionText, queryKey)
      if (onQuestionSent) onQuestionSent()
    }
  }, [initialQuestion])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleSend = async (question = null, queryKey = null) => {
    const query = question || input.trim()
    if (!query) return

    // Add user message
    const userMessage = { type: 'user', content: query }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    
    // Process-aware loading status (best-effort; we don't know route until backend responds)
    // If a saved query key is provided, we DO know it's a saved-query execution path.
    const isSavedQueryRun = Boolean(queryKey)
    setLoadingStatus(isSavedQueryRun ? 'Running saved query...' : 'Orchestrator is analyzing your request...')
    setLoading(true)
    const t1 = setTimeout(
      () => setLoadingStatus(isSavedQueryRun ? 'Executing saved SQL query on the database...' : 'Assistant is drafting a response...'),
      900
    )
    const t2 = setTimeout(
      () => setLoadingStatus(isSavedQueryRun ? 'Formatting results...' : 'Finalizing...'),
      2200
    )

    try {
      const response = await sendQuery(query, true, queryKey, lastSqlQuery)
      
      // Add bot response with standardized structure
      // If backend requests follow-up, render follow-up UI instead of normal bot message
      if (response?.needs_followup && Array.isArray(response.followup_questions)) {
        const followupMessage = {
          type: 'followup',
          content: response.answer,
          success: true,
          sqlQuery: response.sql_query,
          followupQuestions: response.followup_questions,
          followupAnalysis: response.followup_analysis || '',
          agentUsed: response.agent_used || 'followup',
          routeReason: response.route_reason || null
        }
        setMessages(prev => [...prev, followupMessage])
        return
      }

      const botMessage = {
        type: 'bot',
        content: response.answer,  // Brief textual summary
        sqlQuery: response.sql_query,  // The SQL query
        data: response.data || [],  // Table data
        rowCount: response.row_count || 0,  // Number of rows
        isPredefined: response.is_predefined,
        success: response.success,
        isConversational: response.is_conversational || false,  // True if conversational (no SQL)
        agentUsed: response.agent_used || null,
        routeReason: response.route_reason || null
      }
      setMessages(prev => [...prev, botMessage])

      // Save last SQL query for follow-up meta questions and incremental modifications
      // Store SQL from both saved queries and generated queries
      if (response && response.sql_query && !response.is_conversational) {
        setLastSqlQuery(response.sql_query)
      }
    } catch (error) {
      const errorMessage = {
        type: 'bot',
        content: `Error: ${error.message}`,
        success: false
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      clearTimeout(t1)
      clearTimeout(t2)
      setLoading(false)
      setLoadingStatus('Processing your query...')
    }
  }

  const handleFollowupConfirm = async (followupMessage, answers) => {
    try {
      setLoadingStatus('Applying your clarifications...')
      setLoading(true)

      // Re-run the SAME question, but send followup_answers so backend can proceed
      // (Backend will append answers to question and skip followups for this run.)
      const response = await sendQuery(
        // Find the user question just before this follow-up message
        messages.slice(0, messages.findIndex(m => m === followupMessage)).reverse().find(m => m.type === 'user')?.content || '',
        true,
        null,
        lastSqlQuery,
        answers,
        true
      )

      const botMessage = {
        type: 'bot',
        content: response.answer,
        sqlQuery: response.sql_query,
        data: response.data || [],
        rowCount: response.row_count || 0,
        isPredefined: response.is_predefined,
        success: response.success,
        isConversational: response.is_conversational || false,
        agentUsed: response.agent_used || null,
        routeReason: response.route_reason || null
      }

      // Replace the follow-up message with the resulting bot message
      setMessages(prev => prev.map(m => (m === followupMessage ? botMessage : m)))

      if (response && response.success && response.sql_query && !response.is_conversational) {
        setLastSqlQuery(response.sql_query)
      }
    } catch (error) {
      const errorMessage = {
        type: 'bot',
        content: `Error: ${error.message}`,
        success: false
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
      setLoadingStatus('Processing your query...')
    }
  }

  const handleFollowupCancel = (followupMessage) => {
    // Replace follow-up message with a cancelled conversational note
    const cancelled = {
      type: 'bot',
      content: 'Cancelled. No query was executed.',
      success: true,
      isConversational: true,
      agentUsed: 'followup'
    }
    setMessages(prev => prev.map(m => (m === followupMessage ? cancelled : m)))
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleSpeechTranscript = (transcript, isFinal) => {
    if (isFinal) {
      // Final transcript - set and optionally send
      setInput(transcript)
      // Optionally auto-send after a short delay
      // setTimeout(() => handleSend(transcript), 500)
    } else {
      // Interim transcript - show in real-time
      setInput(transcript)
    }
  }

  const handleDownloadReport = (message) => {
    if (!message.data || message.data.length === 0) return

    // Convert data to CSV
    const headers = Object.keys(message.data[0])
    const csvContent = [
      headers.join(','),
      ...message.data.map(row => 
        headers.map(header => {
          const value = row[header]
          // Escape commas and quotes in CSV
          if (value === null || value === undefined) return ''
          const stringValue = String(value)
          if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
            return `"${stringValue.replace(/"/g, '""')}"`
          }
          return stringValue
        }).join(',')
      )
    ].join('\n')

    // Create blob and download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    const url = URL.createObjectURL(blob)
    link.setAttribute('href', url)
    link.setAttribute('download', `ccm_report_${new Date().toISOString().split('T')[0]}.csv`)
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const handleSendForApproval = (message) => {
    // Store the message and show approver selection modal
    setPendingApprovalMessage(message)
    setShowApproverModal(true)
  }

  const handleApproverSelected = async (approver) => {
    if (!pendingApprovalMessage) return

    setShowApproverModal(false)
    
    try {
      // Find the user question that triggered this response
      const messageIndex = messages.findIndex(m => m === pendingApprovalMessage)
      const userQuestion = messageIndex > 0 
        ? messages.slice(0, messageIndex).reverse().find(m => m.type === 'user')?.content 
        : 'Unknown query'

      const response = await fetch('http://localhost:8000/api/reports/send-approval', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user?.username || 'system'
        },
        body: JSON.stringify({
          query: pendingApprovalMessage.sqlQuery,
          data: pendingApprovalMessage.data,
          row_count: pendingApprovalMessage.rowCount,
          question: userQuestion,
          approver_email: approver.email
        })
      })

      if (response.ok) {
        const result = await response.json()
        alert(`✅ Report sent for approval successfully!\n\nApproval ID: ${result.approval_id || 'N/A'}\nApprover: ${approver.name}\nStatus: Pending Review`)
      } else {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to send for approval')
      }
    } catch (error) {
      alert(`❌ Error sending for approval: ${error.message}`)
    } finally {
      setPendingApprovalMessage(null)
    }
  }

  const handleScheduleReport = async (message) => {
    try {
      // Find the user question that triggered this response
      const messageIndex = messages.findIndex(m => m === message)
      const userQuestion = messageIndex > 0 
        ? messages.slice(0, messageIndex).reverse().find(m => m.type === 'user')?.content 
        : 'Unknown query'

      // Show schedule options
      const scheduleType = prompt(
        'Schedule Report:\n\nEnter schedule type:\n1. Daily\n2. Weekly\n3. Monthly\n\nEnter number (1-3):'
      )
      
      if (!scheduleType || !['1', '2', '3'].includes(scheduleType)) {
        return
      }

      const types = { '1': 'daily', '2': 'weekly', '3': 'monthly' }
      const selectedType = types[scheduleType]

      const response = await fetch('http://localhost:8000/api/reports/schedule', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user?.username || 'system'
        },
        body: JSON.stringify({
          query: message.sqlQuery,
          question: userQuestion,
          schedule_type: selectedType,
          enabled: true
        })
      })

      if (response.ok) {
        const result = await response.json()
        alert(`✅ Report scheduled successfully!\n\nSchedule ID: ${result.schedule_id}\nFrequency: ${result.schedule_type}\nStatus: Active`)
      } else {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to schedule report')
      }
    } catch (error) {
      alert(`❌ Error scheduling report: ${error.message}`)
    }
  }

  const handleClearMessages = () => {
    if (window.confirm('Are you sure you want to clear all messages?')) {
      setMessages([])
    }
  }

  return (
    <div className="chat-interface">
      {messages.length > 0 && (
        <div className="chat-header-actions">
          <button 
            className="clear-messages-btn"
            onClick={handleClearMessages}
            title="Clear all messages"
            aria-label="Clear all messages"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              <line x1="10" y1="11" x2="10" y2="17"></line>
              <line x1="14" y1="11" x2="14" y2="17"></line>
            </svg>
          </button>
        </div>
      )}
      
      {messages.length === 0 && (
        <div className="welcome-message-top">
          <h2>Welcome to GenAI CCM Platform</h2>
          <p>Ask questions about your data in natural language, or select a saved query from the sidebar.</p>
          <div className="example-questions">
            <p><strong>💡 Example Questions</strong></p>
            <ul>
              <li>Customers whose ReKYC due &gt;6 months, but ReKYC Credit freeze not applied?</li>
              <li>How many gold loan accounts are there?</li>
              <li>Show me customers with missing IEC codes</li>
            </ul>
          </div>
        </div>
      )}
      
      <div className="chat-messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.type}`}>
            <div className="message-content">
              {msg.type === 'user' ? (
                <div className="user-bubble">
                  <strong>You:</strong> {msg.content}
                </div>
              ) : msg.type === 'followup' ? (
                <div className="bot-bubble success">
                  <div className="bot-header">
                    <strong>Assistant</strong>
                    <span className="badge">{msg.agentUsed || 'followup'}</span>
                  </div>
                  <FollowUpQuestions
                    questions={msg.followupQuestions || []}
                    analysis={msg.followupAnalysis || ''}
                    sqlQuery={msg.sqlQuery || ''}
                    onConfirm={(answers) => handleFollowupConfirm(msg, answers)}
                    onCancel={() => handleFollowupCancel(msg)}
                  />
                </div>
              ) : (
                <div className={`bot-bubble ${msg.success ? 'success' : 'error'}`}>
                  <div className="bot-header">
                    <strong>Assistant</strong>
                    {msg.isPredefined && (
                      <span className="badge">✓ Saved Query</span>
                    )}
                    {msg.agentUsed && !msg.isPredefined && (
                      <span className="badge">{msg.agentUsed}</span>
                    )}
                  </div>
                  <div className="bot-response">
                    {/* Conversational response - formatted nicely */}
                    {msg.success && msg.isConversational && (
                      <div className="conversational-response">
                        {msg.content.split('\n').map((line, idx) => {
                          // Format markdown-like text
                          if (line.trim().startsWith('**') && line.trim().endsWith('**')) {
                            return <p key={idx}><strong>{line.replace(/\*\*/g, '')}</strong></p>
                          }
                          if (line.trim().startsWith('- ')) {
                            return <li key={idx}>{line.replace(/^-\s*/, '')}</li>
                          }
                          if (line.trim() === '') {
                            return <br key={idx} />
                          }
                          return <p key={idx}>{line}</p>
                        })}
                      </div>
                    )}
                    
                    {/* Brief textual response - only show if success and not conversational, otherwise show error below */}
                    {msg.success && !msg.isConversational && (
                      <p className="response-summary">{msg.content}</p>
                    )}
                    
                    {/* Data table if available */}
                    {msg.success && !msg.isConversational && msg.data && msg.data.length > 0 && (
                      <div className="data-table-container">
                        <div className="table-header">
                          <strong>Results ({msg.rowCount} row{msg.rowCount !== 1 ? 's' : ''})</strong>
                        </div>
                        <div className="table-wrapper">
                          <table className="data-table">
                            <thead>
                              <tr>
                                {Object.keys(msg.data[0]).map((key, idx) => (
                                  <th key={idx}>{key}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {msg.data.map((row, rowIdx) => (
                                <tr key={rowIdx}>
                                  {Object.values(row).map((value, colIdx) => (
                                    <td key={colIdx}>
                                      {value === null || value === undefined ? 'NULL' : String(value)}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                    
                    {/* Error message */}
                    {!msg.success && (
                      <p className="error-text">{msg.content}</p>
                    )}
                  </div>
                  
                  {/* Report Actions - Show after successful query with data (not conversational) */}
                  {msg.success && !msg.isConversational && msg.data && msg.data.length > 0 && (
                    <div className="report-actions">
                      <button 
                        className="report-action-btn download-btn"
                        onClick={() => handleDownloadReport(msg)}
                        title="Download report as CSV/Excel"
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                          <polyline points="7 10 12 15 17 10"></polyline>
                          <line x1="12" y1="15" x2="12" y2="3"></line>
                        </svg>
                        Download Report
                      </button>
                      {/* Saved queries: only allow download; SQLMaker-generated reports keep approval/scheduling */}
                      {!msg.isPredefined && (
                        <>
                          <button 
                            className="report-action-btn approval-btn"
                            onClick={() => handleSendForApproval(msg)}
                            title="Send report for approval"
                          >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path>
                            </svg>
                            Send for Approval
                          </button>
                          <button 
                            className="report-action-btn schedule-btn"
                            onClick={() => handleScheduleReport(msg)}
                            title="Schedule recurring report"
                          >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <circle cx="12" cy="12" r="10"></circle>
                              <polyline points="12 6 12 12 16 14"></polyline>
                            </svg>
                            Schedule Report
                          </button>
                        </>
                      )}
                    </div>
                  )}
                  
                  {/* SQL Query - Only show if available and not conversational */}
                  {msg.sqlQuery && !msg.isConversational && (
                    <details className="sql-details">
                      <summary>🔍 {msg.isPredefined ? 'View Saved SQL Query' : 'View Generated SQL Query'}</summary>
                      <pre className="sql-query">{msg.sqlQuery}</pre>
                    </details>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
        
        {loading && (
          <div className="message bot">
            <div className="bot-bubble">
              <div className="loading">{loadingStatus}</div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-container">
        <SpeechToText 
          onTranscript={handleSpeechTranscript}
          disabled={loading}
        />
        <textarea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask a question about your data or click the microphone to speak..."
          rows={2}
        />
        <button
          className="send-button"
          onClick={() => handleSend()}
          disabled={loading || !input.trim()}
          title={loading ? 'Processing...' : 'Send message'}
        >
          {loading ? '⏳' : '→'}
        </button>
      </div>

      {/* Approver Selection Modal */}
      <ApproverModal
        isOpen={showApproverModal}
        onClose={() => {
          setShowApproverModal(false)
          setPendingApprovalMessage(null)
        }}
        onSelect={handleApproverSelected}
        currentUser={user}
      />
    </div>
  )
}

export default ChatInterface

