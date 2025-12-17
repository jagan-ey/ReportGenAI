import React, { useState, useEffect, useRef } from 'react'
import './PredefinedQueriesModal.css'

function PredefinedQueriesModal({ isOpen, onClose, queries, onSelect }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [filteredQueries, setFilteredQueries] = useState(queries)
  const searchInputRef = useRef(null)

  useEffect(() => {
    if (isOpen) {
      // Focus search input when modal opens
      setTimeout(() => {
        searchInputRef.current?.focus()
      }, 100)
    } else {
      // Clear search when modal closes
      setSearchTerm('')
    }
  }, [isOpen])

  useEffect(() => {
    // Filter queries based on search term
    if (!searchTerm.trim()) {
      setFilteredQueries(queries)
    } else {
      const filtered = queries.filter(query => {
        const searchLower = searchTerm.toLowerCase()
        return (
          query.question.toLowerCase().includes(searchLower) ||
          query.description.toLowerCase().includes(searchLower) ||
          query.key.toLowerCase().includes(searchLower)
        )
      })
      setFilteredQueries(filtered)
    }
  }, [searchTerm, queries])

  const handleSelect = (query) => {
    onSelect(query)
    onClose()
  }

  if (!isOpen) return null

  return (
    <>
      <div className="queries-modal-overlay" onClick={onClose}></div>
      <div className="queries-modal">
        <div className="queries-modal-header">
          <div>
            <h2>📋 Saved Queries</h2>
            <p>Select a saved query to execute with 100% accuracy</p>
          </div>
          <button className="queries-modal-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="queries-modal-search">
          <input
            ref={searchInputRef}
            type="text"
            placeholder="Search saved queries by question, description, or key..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="queries-search-input"
          />
          {searchTerm && (
            <button
              className="queries-search-clear"
              onClick={() => setSearchTerm('')}
              aria-label="Clear search"
            >
              ✕
            </button>
          )}
        </div>

        <div className="queries-modal-content">
          {filteredQueries.length === 0 ? (
            <div className="queries-empty">
              <p>No queries found matching "{searchTerm}"</p>
              <button onClick={() => setSearchTerm('')} className="queries-reset-search">
                Clear search
              </button>
            </div>
          ) : (
            <div className="queries-modal-list">
              {filteredQueries.map((query, idx) => (
                <div
                  key={query.key}
                  className="queries-modal-item"
                  onClick={() => handleSelect(query)}
                  style={{ animationDelay: `${idx * 0.05}s` }}
                >
                  <div className="queries-modal-number">{idx + 1}</div>
                  <div className="queries-modal-item-content">
                    <div className="queries-modal-title">{query.description}</div>
                    <div className="queries-modal-question">{query.question}</div>
                    <div className="queries-modal-key">Key: {query.key}</div>
                  </div>
                  <div className="queries-modal-arrow">→</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="queries-modal-footer">
          <p>{filteredQueries.length} {filteredQueries.length === 1 ? 'query' : 'queries'} found</p>
        </div>
      </div>
    </>
  )
}

export default PredefinedQueriesModal

