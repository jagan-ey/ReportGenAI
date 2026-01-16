import React, { useState } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar, Line, Pie, Scatter } from 'react-chartjs-2';
import './ChartRenderer.css';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
);

const ChartRenderer = ({ insights, data }) => {
  const [showTable, setShowTable] = useState(false);

  if (!insights || !insights.chart_type || !data || data.length === 0) {
    return null;
  }

  // Don't render chart if type is 'table'
  if (insights.chart_type === 'table') {
    return null;
  }

  /**
   * Transform data into Chart.js format based on insights configuration
   */
  const getChartData = () => {
    const { chart_type, x_axis, y_axis, config = {} } = insights;
    
    // Extract labels (X-axis values)
    const labels = data.map(row => row[x_axis] || 'N/A');
    
    // Default colors
    const defaultColors = config.colors || [
      '#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6',
      '#1abc9c', '#34495e', '#e67e22', '#95a5a6', '#d35400'
    ];

    if (chart_type === 'pie') {
      // For pie charts, use single Y-axis column
      const values = data.map(row => row[y_axis[0]] || 0);
      
      return {
        labels: labels,
        datasets: [{
          label: y_axis[0],
          data: values,
          backgroundColor: defaultColors.slice(0, values.length),
          borderColor: '#fff',
          borderWidth: 2,
        }]
      };
    }

    if (chart_type === 'scatter') {
      // Scatter plot needs x,y coordinates
      const xCol = y_axis[0] || x_axis;
      const yCol = y_axis[1] || y_axis[0];
      
      const points = data.map(row => ({
        x: row[xCol] || 0,
        y: row[yCol] || 0,
      }));

      return {
        datasets: [{
          label: `${xCol} vs ${yCol}`,
          data: points,
          backgroundColor: defaultColors[0],
          borderColor: defaultColors[0],
          pointRadius: 6,
          pointHoverRadius: 8,
        }]
      };
    }

    // For bar and line charts
    const datasets = y_axis.map((yCol, idx) => {
      const values = data.map(row => row[yCol] || 0);
      
      return {
        label: yCol,
        data: values,
        backgroundColor: chart_type === 'bar' ? defaultColors[idx % defaultColors.length] : 'transparent',
        borderColor: defaultColors[idx % defaultColors.length],
        borderWidth: 2,
        fill: false,
        tension: 0.4, // Smooth line curves
      };
    });

    return {
      labels: labels,
      datasets: datasets,
    };
  };

  /**
   * Get Chart.js options based on chart type and config
   */
  const getChartOptions = () => {
    const { title, config = {}, chart_type } = insights;
    
    const baseOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: config.legend !== false,
          position: 'top',
        },
        title: {
          display: !!title,
          text: title || '',
          font: {
            size: 16,
            weight: 'bold',
          },
        },
        tooltip: {
          mode: 'index',
          intersect: false,
        },
      },
    };

    if (chart_type === 'pie') {
      const categoryCount = data.length;
      // For many categories, put legend at bottom to avoid overlap
      const legendPosition = categoryCount > 8 ? 'bottom' : 'right';
      
      return {
        ...baseOptions,
        plugins: {
          ...baseOptions.plugins,
          legend: {
            display: true,
            position: legendPosition,
            labels: {
              boxWidth: 12,
              padding: 8,
              font: {
                size: categoryCount > 12 ? 10 : 12,
              },
            },
          },
          title: {
            display: !!title,
            text: title || '',
            font: {
              size: 16,
              weight: 'bold',
            },
            padding: {
              bottom: 20,
            },
          },
        },
        layout: {
          padding: {
            top: 10,
            bottom: 10,
          },
        },
      };
    }

    if (chart_type === 'scatter') {
      return {
        ...baseOptions,
        scales: {
          x: {
            type: 'linear',
            position: 'bottom',
          },
          y: {
            beginAtZero: true,
          },
        },
      };
    }

    // Bar and Line charts
    return {
      ...baseOptions,
      scales: {
        x: {
          grid: {
            display: false,
          },
        },
        y: {
          beginAtZero: true,
          grid: {
            color: 'rgba(0, 0, 0, 0.05)',
          },
        },
      },
    };
  };

  /**
   * Render the appropriate chart component
   */
  const renderChart = () => {
    const chartData = getChartData();
    const chartOptions = getChartOptions();

    switch (insights.chart_type) {
      case 'bar':
        return <Bar data={chartData} options={chartOptions} />;
      case 'line':
        return <Line data={chartData} options={chartOptions} />;
      case 'pie':
        return <Pie data={chartData} options={chartOptions} />;
      case 'scatter':
        return <Scatter data={chartData} options={chartOptions} />;
      default:
        return <div className="chart-error">Unsupported chart type: {insights.chart_type}</div>;
    }
  };

  /**
   * Render table view
   */
  const renderTable = () => {
    if (!data || data.length === 0) return null;

    const columns = Object.keys(data[0]);

    return (
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col, idx) => (
                <th key={idx}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, rowIdx) => (
              <tr key={rowIdx}>
                {columns.map((col, colIdx) => (
                  <td key={colIdx}>
                    {row[col] === null ? 'NULL' : String(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="chart-renderer">
      <div className="chart-header">
        <button 
          className={`view-toggle-btn ${!showTable ? 'active' : ''}`}
          onClick={() => setShowTable(false)}
        >
          📊 Chart View
        </button>
        <button 
          className={`view-toggle-btn ${showTable ? 'active' : ''}`}
          onClick={() => setShowTable(true)}
        >
          📋 Table View
        </button>
      </div>

      {showTable ? (
        renderTable()
      ) : (
        <div className={`chart-container ${insights.chart_type === 'pie' && data.length > 8 ? 'pie-many-categories' : ''}`}>
          {renderChart()}
        </div>
      )}
    </div>
  );
};

export default ChartRenderer;
