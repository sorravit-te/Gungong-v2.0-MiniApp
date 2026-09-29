import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import '../styles/dataVisualization.css';

// Data for the chart - Colors matching verify page icon palette
const chartData = [
  { name: 'Successful Checks', shortName: 'check', value: 43, color: '#86EFAC' },
  { name: 'Prevented Threats', shortName: 'block', value: 36, color: '#93C5FD' },
  { name: 'Confirmed Scams', shortName: 'scam', value: 12, color: '#FCA5A5' },
];

// Custom Tooltip with glassmorphism effect
const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="chart-tooltip">
        <div className="tooltip-indicator" style={{ backgroundColor: data.color }} />
        <div className="tooltip-content">
          <span className="tooltip-label">{data.name}</span>
          <span className="tooltip-value">{data.value}</span>
        </div>
      </div>
    );
  }
  return null;
};

// Custom Bar shape with rounded top corners
const RoundedBar = (props) => {
  const { x, y, width, height, fill } = props;
  const radius = 10;

  if (height <= 0) return null;

  return (
    <path
      d={`
        M ${x},${y + height}
        L ${x},${y + radius}
        Q ${x},${y} ${x + radius},${y}
        L ${x + width - radius},${y}
        Q ${x + width},${y} ${x + width},${y + radius}
        L ${x + width},${y + height}
        Z
      `}
      fill={fill}
      className="chart-bar"
    />
  );
};

const DataVisualization = () => {
  return (
    <div className="summary-viz-card animate-card">
      {/* Header Section - Same style as verify menu */}
      <div className="summary-viz-header">
        <div className="summary-viz-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="5"></circle>
            <line x1="12" y1="1" x2="12" y2="3"></line>
            <line x1="12" y1="21" x2="12" y2="23"></line>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
            <line x1="1" y1="12" x2="3" y2="12"></line>
            <line x1="21" y1="12" x2="23" y2="12"></line>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
          </svg>
        </div>
        <div className="summary-viz-title">
          <h3>Summary</h3>
          <span>of this week</span>
        </div>
        <div className="summary-viz-action">
          <span>รายละเอียด</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
        </div>
      </div>

      {/* Stats Row - Compact inline style */}
      <div className="summary-stats-inline">
        {chartData.map((item, index) => (
          <div key={index} className="stat-item-inline">
            <span className="stat-dot" style={{ backgroundColor: item.color }} />
            <span className="stat-label">{item.shortName}</span>
            <span className="stat-value" style={{ color: item.color }}>{item.value}</span>
          </div>
        ))}
      </div>

      {/* Chart Section */}
      <div className="chart-container">
        <ResponsiveContainer width="100%" height={180}>
          <BarChart
            data={chartData}
            margin={{ top: 10, right: 10, left: -20, bottom: 5 }}
            barCategoryGap="20%"
          >
            <XAxis
              dataKey="shortName"
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 11, fontWeight: 600 }}
              className="chart-axis-tick"
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 10, fontWeight: 500 }}
              className="chart-axis-tick"
              domain={[0, 'dataMax + 10']}
              tickCount={4}
            />
            <Tooltip
              content={<CustomTooltip />}
              cursor={{ fill: 'rgba(0, 0, 0, 0.04)' }}
            />
            <Bar
              dataKey="value"
              shape={<RoundedBar />}
              animationDuration={1200}
              animationEasing="ease-out"
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default DataVisualization;
