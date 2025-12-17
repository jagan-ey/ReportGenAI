import React, { useState, useEffect } from 'react'
import { useUser } from '../contexts/UserContext'
import './ApprovalsDashboard.css'

function ApprovalsDashboard() {
  const { user } = useUser()
  const [approvals, setApprovals] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedApproval, setSelectedApproval] = useState(null)
  const [filter, setFilter] = useState('pending') // pending, approved, rejected, all
  const [notes, setNotes] = useState('')

  useEffect(() => {
    fetchApprovals()
  }, [filter])

  const fetchApprovals = async () => {
    setLoading(true)
    try {
      const status = filter === 'all' ? null : filter
      const url = `http://localhost:8000/api/reports/approvals${status ? `?status=${status}` : ''}`
      console.log('Fetching approvals from:', url)
      console.log('User:', user)
      
      const response = await fetch(url, {
        headers: {
          'X-User-ID': user?.username || 'system',
          'Content-Type': 'application/json'
        }
      })
      
      if (response.ok) {
        const data = await response.json()
        console.log('Approvals response:', data)
        setApprovals(data.approvals || [])
      } else {
        const errorData = await response.json()
        console.error('Failed to fetch approvals:', errorData)
        alert(`Error: ${errorData.detail || 'Failed to fetch approvals'}`)
      }
    } catch (error) {
      console.error('Error fetching approvals:', error)
      alert(`Error: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async (approvalId) => {
    try {
      const response = await fetch(
        `http://localhost:8000/api/reports/approvals/${approvalId}/approve`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-User-ID': user?.username || 'system'
          },
          body: JSON.stringify({ notes: notes || null })
        }
      )

      if (response.ok) {
        alert('✅ Request approved successfully!')
        setSelectedApproval(null)
        setNotes('')
        fetchApprovals()
      } else {
        const error = await response.json()
        alert(`❌ Error: ${error.detail || 'Failed to approve request'}`)
      }
    } catch (error) {
      alert(`❌ Error: ${error.message}`)
    }
  }

  const handleReject = async (approvalId) => {
    if (!notes.trim()) {
      alert('Please provide a reason for rejection')
      return
    }

    try {
      const response = await fetch(
        `http://localhost:8000/api/reports/approvals/${approvalId}/reject`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-User-ID': user?.username || 'system'
          },
          body: JSON.stringify({ notes: notes })
        }
      )

      if (response.ok) {
        alert('✅ Request rejected')
        setSelectedApproval(null)
        setNotes('')
        fetchApprovals()
      } else {
        const error = await response.json()
        alert(`❌ Error: ${error.detail || 'Failed to reject request'}`)
      }
    } catch (error) {
      alert(`❌ Error: ${error.message}`)
    }
  }

  const getStatusBadge = (status) => {
    const badges = {
      pending: { class: 'status-pending', text: 'Pending', icon: '⏳' },
      approved: { class: 'status-approved', text: 'Approved', icon: '✅' },
      rejected: { class: 'status-rejected', text: 'Rejected', icon: '❌' }
    }
    const badge = badges[status] || badges.pending
    return (
      <span className={`status-badge ${badge.class}`}>
        {badge.icon} {badge.text}
      </span>
    )
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleString()
  }

  return (
    <div className="approvals-dashboard">
      <div className="dashboard-header">
        <div>
          <h1>Approval Requests</h1>
          <p>Review and manage pending approval requests</p>
        </div>
        <div className="filter-tabs">
          <button
            className={`filter-tab ${filter === 'pending' ? 'active' : ''}`}
            onClick={() => setFilter('pending')}
          >
            Pending ({approvals.filter(a => a.status === 'pending').length})
          </button>
          <button
            className={`filter-tab ${filter === 'approved' ? 'active' : ''}`}
            onClick={() => setFilter('approved')}
          >
            Approved ({approvals.filter(a => a.status === 'approved').length})
          </button>
          <button
            className={`filter-tab ${filter === 'rejected' ? 'active' : ''}`}
            onClick={() => setFilter('rejected')}
          >
            Rejected ({approvals.filter(a => a.status === 'rejected').length})
          </button>
          <button
            className={`filter-tab ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All ({approvals.length})
          </button>
        </div>
      </div>

      <div className="dashboard-content">
        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Loading approvals...</p>
          </div>
        ) : approvals.length === 0 ? (
          <div className="empty-state">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
              <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            <h3>No approvals found</h3>
            <p>There are no {filter === 'all' ? '' : filter} approval requests at this time.</p>
          </div>
        ) : (
          <div className="approvals-list">
            {approvals.map((approval) => (
              <div
                key={approval.approval_id}
                className={`approval-card ${approval.status} ${selectedApproval?.approval_id === approval.approval_id ? 'selected' : ''}`}
                onClick={() => setSelectedApproval(approval)}
              >
                <div className="approval-card-header">
                  <div className="approval-id">{approval.approval_id}</div>
                  {getStatusBadge(approval.status)}
                </div>
                <div className="approval-card-body">
                  <div className="approval-question">
                    <strong>Question:</strong> {approval.question || 'N/A'}
                  </div>
                  <div className="approval-meta">
                    <div className="meta-item">
                      <span className="meta-label">Requested by:</span>
                      <span className="meta-value">{approval.requested_by}</span>
                    </div>
                    <div className="meta-item">
                      <span className="meta-label">Rows:</span>
                      <span className="meta-value">{approval.row_count || 0}</span>
                    </div>
                    <div className="meta-item">
                      <span className="meta-label">Created:</span>
                      <span className="meta-value">{formatDate(approval.created_date)}</span>
                    </div>
                    {approval.approved_date && (
                      <div className="meta-item">
                        <span className="meta-label">Processed:</span>
                        <span className="meta-value">{formatDate(approval.approved_date)}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Approval Detail Modal */}
      {selectedApproval && (
        <div className="modal-overlay" onClick={() => setSelectedApproval(null)}>
          <div className="modal-content approval-detail-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Approval Request Details</h2>
              <button className="modal-close" onClick={() => setSelectedApproval(null)}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>

            <div className="modal-body">
              <div className="approval-detail-section">
                <h3>Request Information</h3>
                <div className="detail-grid">
                  <div className="detail-item">
                    <label>Approval ID:</label>
                    <span>{selectedApproval.approval_id}</span>
                  </div>
                  <div className="detail-item">
                    <label>Status:</label>
                    {getStatusBadge(selectedApproval.status)}
                  </div>
                  <div className="detail-item">
                    <label>Requested by:</label>
                    <span>{selectedApproval.requested_by}</span>
                  </div>
                  <div className="detail-item">
                    <label>Created:</label>
                    <span>{formatDate(selectedApproval.created_date)}</span>
                  </div>
                  {selectedApproval.approved_by && (
                    <div className="detail-item">
                      <label>Processed by:</label>
                      <span>{selectedApproval.approved_by}</span>
                    </div>
                  )}
                  {selectedApproval.approved_date && (
                    <div className="detail-item">
                      <label>Processed on:</label>
                      <span>{formatDate(selectedApproval.approved_date)}</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="approval-detail-section">
                <h3>Question</h3>
                <div className="question-box">
                  {selectedApproval.question || 'N/A'}
                </div>
              </div>

              <div className="approval-detail-section">
                <h3>SQL Query</h3>
                <details className="sql-details">
                  <summary>View SQL Query</summary>
                  <pre className="sql-query">{selectedApproval.query || 'N/A'}</pre>
                </details>
              </div>

              <div className="approval-detail-section">
                <h3>Results Summary</h3>
                <div className="summary-box">
                  <div className="summary-item">
                    <span className="summary-label">Total Rows:</span>
                    <span className="summary-value">{selectedApproval.row_count || 0}</span>
                  </div>
                </div>
              </div>

              {selectedApproval.notes && (
                <div className="approval-detail-section">
                  <h3>Notes</h3>
                  <div className="notes-box">
                    {selectedApproval.notes}
                  </div>
                </div>
              )}

              {selectedApproval.status === 'pending' && (
                <div className="approval-detail-section">
                  <h3>Add Notes (Optional)</h3>
                  <textarea
                    className="notes-input"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Add any notes or comments about this approval request..."
                    rows={4}
                  />
                </div>
              )}
            </div>

            {selectedApproval.status === 'pending' && (
              <div className="modal-footer">
                <button
                  className="modal-button reject"
                  onClick={() => handleReject(selectedApproval.approval_id)}
                >
                  ❌ Reject
                </button>
                <button
                  className="modal-button approve"
                  onClick={() => handleApprove(selectedApproval.approval_id)}
                >
                  ✅ Approve
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default ApprovalsDashboard

