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
import { useHistoryEntries } from '../hooks/useHistoryEntries';
import { summarizeHistory } from '../utils/historyView';

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
  const radius = Math.min(10, height, width / 2);

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

const DataVisualization = ({ onNavigate }) => {
  const { entries, loading, error } = useHistoryEntries();
  const summary = summarizeHistory(entries);
  const chartData = summary.types.map(type => ({ ...type, name: type.label, shortName: type.label, value: type.count }));
  return (
    <div className="summary-viz-card animate-card">
      {/* Header Section - Same style as verify menu */}
      <div className="summary-viz-header">
        <div className="summary-viz-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
          </svg>
        </div>
        <div className="summary-viz-title">
          <h3>Summary</h3>
          <span>ประวัติล่าสุดของคุณ · สูงสุด 50 รายการ</span>
        </div>
        <button type="button" className="summary-viz-action" onClick={() => onNavigate?.('history')}>
          <span>รายละเอียด</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
        </button>
      </div>

      {loading ? <div role="status" className="page-loading">กำลังโหลดข้อมูล...</div>
        : error ? <div role="alert" className="summary-load-message">{error}</div>
        : <>
      <p className="summary-total">ตรวจแล้ว {summary.total} รายการ</p>
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
      <div className="summary-outcomes">
        <span>ไม่พบสัญญาณอันตราย {summary.counts.safe}</span>
        <span>พบความเสี่ยง {summary.counts.risk}</span>
        <span>ยังสรุปไม่ได้ {summary.counts.unknown}</span>
        <span>ข้อมูลไม่ถูกต้อง / ไม่อนุญาต {summary.counts.invalid}</span>
      </div>
      {summary.total === 0 && <p className="summary-load-message">ยังไม่มีประวัติการตรวจสอบ</p>}

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
              allowDecimals={false}
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
      </>}
    </div>
  );
};

export default DataVisualization;
