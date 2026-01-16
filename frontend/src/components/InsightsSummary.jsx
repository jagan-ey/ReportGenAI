import React from 'react';
import './InsightsSummary.css';

const InsightsSummary = ({ insights }) => {
  if (!insights || !insights.insights || insights.insights.length === 0) {
    return null;
  }

  return (
    <div className="insights-summary">
      <div className="insights-header">
        <span className="insights-icon">💡</span>
        <h4>Key Insights</h4>
      </div>
      <ul className="insights-list">
        {insights.insights.map((insight, idx) => (
          <li key={idx} className="insight-item">
            <span className="insight-bullet">•</span>
            <span className="insight-text">{insight}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default InsightsSummary;
