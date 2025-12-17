import React, { useState } from 'react'
import './FollowUpQuestions.css'

function FollowUpQuestions({ questions, analysis, onConfirm, onCancel, sqlQuery }) {
  const [answers, setAnswers] = useState({})
  const [errors, setErrors] = useState({})

  const handleAnswerChange = (questionId, value) => {
    setAnswers(prev => ({
      ...prev,
      [questionId]: value
    }))
    // Clear error for this question
    if (errors[questionId]) {
      setErrors(prev => {
        const newErrors = { ...prev }
        delete newErrors[questionId]
        return newErrors
      })
    }
  }

  const handleConfirm = () => {
    // Validate all required questions are answered
    const missing = questions.filter(q => q.required && !answers[q.id])
    if (missing.length > 0) {
      const newErrors = {}
      missing.forEach(q => {
        newErrors[q.id] = 'This question is required'
      })
      setErrors(newErrors)
      return
    }

    // All answered - proceed
    onConfirm(answers)
  }

  const renderQuestionInput = (question) => {
    const value = answers[question.id] || ''
    const hasError = errors[question.id]

    switch (question.type) {
      case 'date_selection':
        return (
          <div className="followup-options">
            {question.options?.map((option, idx) => (
              <label key={idx} className="followup-option">
                <input
                  type="radio"
                  name={question.id}
                  value={option}
                  checked={value === option}
                  onChange={(e) => handleAnswerChange(question.id, e.target.value)}
                />
                <span>{option}</span>
              </label>
            ))}
            {question.options?.includes('Custom Date') && value === 'Custom Date' && (
              <input
                type="date"
                className="followup-custom-date"
                value={answers[`${question.id}_date`] || ''}
                onChange={(e) => handleAnswerChange(`${question.id}_date`, e.target.value)}
              />
            )}
          </div>
        )

      case 'confirmation':
        return (
          <div className="followup-options">
            <label className="followup-option">
              <input
                type="radio"
                name={question.id}
                value="yes"
                checked={value === 'yes'}
                onChange={(e) => handleAnswerChange(question.id, e.target.value)}
              />
              <span>✓ Yes, Confirm</span>
            </label>
            <label className="followup-option">
              <input
                type="radio"
                name={question.id}
                value="no"
                checked={value === 'no'}
                onChange={(e) => handleAnswerChange(question.id, e.target.value)}
              />
              <span>✗ No, Cancel</span>
            </label>
          </div>
        )

      case 'text':
        return (
          <textarea
            className="followup-text-input"
            value={value}
            onChange={(e) => handleAnswerChange(question.id, e.target.value)}
            placeholder="Enter your answer..."
            rows={3}
          />
        )

      default:
        return (
          <input
            type="text"
            className="followup-text-input"
            value={value}
            onChange={(e) => handleAnswerChange(question.id, e.target.value)}
            placeholder="Enter your answer..."
          />
        )
    }
  }

  return (
    <div className="followup-container">
      <div className="followup-header">
        <h3>🔍 Query Clarification Needed</h3>
        {analysis && <p className="followup-analysis">{analysis}</p>}
      </div>

      <div className="followup-questions">
        {questions.map((question, idx) => (
          <div key={question.id || idx} className={`followup-question ${errors[question.id] ? 'error' : ''}`}>
            <div className="followup-question-label">
              <span className="followup-number">{idx + 1}</span>
              <span className="followup-question-text">{question.question}</span>
              {question.required && <span className="followup-required">*</span>}
            </div>
            
            {question.estimated_mb && (
              <div className="followup-estimates">
                <span className="estimate-badge">
                  📊 Estimated: {question.estimated_mb} MB
                </span>
                {question.estimated_seconds && (
                  <span className="estimate-badge">
                    ⏱️ Runtime: ~{question.estimated_seconds} seconds
                  </span>
                )}
              </div>
            )}

            {renderQuestionInput(question)}
            
            {errors[question.id] && (
              <div className="followup-error">{errors[question.id]}</div>
            )}
          </div>
        ))}
      </div>

      {sqlQuery && (
        <details className="followup-sql-preview">
          <summary>Preview Generated SQL Query</summary>
          <pre className="sql-preview">{sqlQuery}</pre>
        </details>
      )}

      <div className="followup-actions">
        <button className="followup-cancel" onClick={onCancel}>
          Cancel
        </button>
        <button className="followup-confirm" onClick={handleConfirm}>
          ✓ Confirm & Execute
        </button>
      </div>
    </div>
  )
}

export default FollowUpQuestions

