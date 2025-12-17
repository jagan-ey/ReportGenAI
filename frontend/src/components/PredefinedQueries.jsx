import React from 'react'
import './PredefinedQueries.css'

function PredefinedQueries({ queries, onSelect, onExpand }) {
  if (queries.length === 0) {
    return (
      <div className="predefined-queries">
        <div className="queries-header">
          <h3>Saved Queries</h3>
        </div>
        <p className="loading-text">Loading queries...</p>
      </div>
    )
  }

  return (
    <div className="predefined-queries">
      <div className="queries-header">
        <h3>Saved Queries</h3>
        <button 
          className="expand-queries-button"
          onClick={onExpand}
          title="Expand to full screen modal"
          aria-label="Expand queries"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M3 3h10v10M3 13L13 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>
      </div>
      <p className="subtitle">Click to execute (100% accuracy)</p>
      
      <div className="queries-list">
        {queries.map((query, idx) => (
          <div
            key={query.key}
            className="query-item"
            onClick={() => onSelect(query)}
          >
            <div className="query-number">{idx + 1}</div>
            <div className="query-content">
              <div className="query-title">{query.description}</div>
              <div className="query-preview">{query.question.substring(0, 80)}...</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default PredefinedQueries

