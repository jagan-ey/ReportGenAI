import React, { useState, useEffect } from 'react'
import './ApproverModal.css'

function ApproverModal({ isOpen, onClose, onSelect, currentUser }) {
  const [approvers, setApprovers] = useState([])
  const [searchTerm, setSearchTerm] = useState('')
  const [loading, setLoading] = useState(false)
  const [selectedApprover, setSelectedApprover] = useState(null)

  useEffect(() => {
    if (isOpen) {
      fetchApprovers()
    }
  }, [isOpen])

  const fetchApprovers = async () => {
    setLoading(true)
    try {
      const response = await fetch('http://localhost:8000/api/reports/approvers', {
        headers: {
          'X-User-ID': currentUser?.username || 'system'
        }
      })
      if (response.ok) {
        const data = await response.json()
        setApprovers(data.approvers || [])
      } else {
        console.error('Failed to fetch approvers')
      }
    } catch (error) {
      console.error('Error fetching approvers:', error)
    } finally {
      setLoading(false)
    }
  }

  const filteredApprovers = approvers.filter(approver => {
    const search = searchTerm.toLowerCase()
    return (
      approver.name?.toLowerCase().includes(search) ||
      approver.email?.toLowerCase().includes(search) ||
      approver.department?.toLowerCase().includes(search)
    )
  })

  const handleSelect = () => {
    if (selectedApprover) {
      onSelect(selectedApprover)
      setSelectedApprover(null)
      setSearchTerm('')
    }
  }

  const handleClose = () => {
    setSelectedApprover(null)
    setSearchTerm('')
    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Select Approver</h2>
          <button className="modal-close" onClick={handleClose} aria-label="Close">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <div className="modal-body">
          <div className="search-container">
            <svg className="search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8"></circle>
              <path d="m21 21-4.35-4.35"></path>
            </svg>
            <input
              type="text"
              className="search-input"
              placeholder="Search by name, email, or department..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              autoFocus
            />
          </div>

          {loading ? (
            <div className="loading-state">
              <div className="spinner"></div>
              <p>Loading approvers...</p>
            </div>
          ) : filteredApprovers.length === 0 ? (
            <div className="empty-state">
              <p>{searchTerm ? 'No approvers found matching your search' : 'No approvers available'}</p>
            </div>
          ) : (
            <div className="approvers-list">
              {filteredApprovers.map((approver) => (
                <div
                  key={approver.user_id}
                  className={`approver-item ${selectedApprover?.user_id === approver.user_id ? 'selected' : ''}`}
                  onClick={() => setSelectedApprover(approver)}
                >
                  <div className="approver-avatar">
                    {approver.name?.charAt(0).toUpperCase() || approver.email?.charAt(0).toUpperCase() || 'A'}
                  </div>
                  <div className="approver-info">
                    <div className="approver-name">{approver.name || approver.email}</div>
                    <div className="approver-details">
                      <span className="approver-email">{approver.email}</span>
                      {approver.department && (
                        <>
                          <span className="separator">•</span>
                          <span className="approver-department">{approver.department}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="approver-badge">
                    {approver.role === 'admin' ? 'Admin' : 'Approver'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="modal-button cancel" onClick={handleClose}>
            Cancel
          </button>
          <button
            className="modal-button submit"
            onClick={handleSelect}
            disabled={!selectedApprover}
          >
            Send to {selectedApprover?.name || 'Approver'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ApproverModal

