import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import '../dataVisualization.css';
import { SUMMARY_OUTCOMES } from '../../history/utils/historyView';

const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="chart-tooltip summary-result-tooltip">
        <strong>{data.name} · {data.value} รายการ</strong>
        {SUMMARY_OUTCOMES.map(outcome => (
          <div className="summary-tooltip-row" key={outcome.key}>
            <span className="summary-result-swatch" style={{ backgroundColor: outcome.color }} />
            <span>{outcome.label}</span>
            <strong>{data[outcome.key]}</strong>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

// Round only the uppermost non-empty segment, keeping stack boundaries aligned.
const ResultSegment = ({ x, y, width, height, fill, payload, outcomeKey }) => {
  if (!(height > 0) || !payload) return null;
  const topKey = SUMMARY_OUTCOMES.filter(outcome => payload[outcome.key] > 0).at(-1)?.key;
  const isTop = topKey === outcomeKey;
  const radius = isTop ? Math.min(8, height, width / 2) : 0;

  return (
    <g>
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
      {height >= 22 && <text x={x + width / 2} y={y + height / 2} textAnchor="middle" dominantBaseline="central" className="summary-segment-count">{payload[outcomeKey]}</text>}
      {isTop && <text x={x + width / 2} y={y - 10} textAnchor="middle" className="summary-bar-total">{payload.value}</text>}
    </g>
  );
};

export const SummaryResults = ({ summary, showCounts = true }) => {
  const chartData = summary.types.map(type => ({ ...type.outcomes, name: type.label, shortName: type.label, value: type.count }));
  const maxCount = Math.max(...chartData.map(item => item.value), 0);
  return (
    <>
      <div className="summary-chart-heading">
        <h4>ผลลัพธ์การตรวจสอบ</h4>
        <span>จำนวนรายการ · แยกตามผลลัพธ์</span>
      </div>
      <div className="chart-container" role="group" aria-label="กราฟแท่งซ้อนจำนวนการตรวจสอบลิงก์ / QR Code และข้อความ แยกตามผลลัพธ์">
        <ResponsiveContainer width="100%" height="100%" minWidth={0} initialDimension={{ width: 300, height: 220 }}>
          <BarChart data={chartData} margin={{ top: 26, right: 10, left: -20, bottom: 5 }} barCategoryGap="20%" accessibilityLayer>
            <CartesianGrid vertical={false} strokeDasharray="3 3" className="summary-chart-grid" />
            <XAxis dataKey="shortName" axisLine={false} tickLine={false} interval={0}
              tick={{ fontSize: 11, fontWeight: 600 }} className="chart-axis-tick chart-category-axis" />
            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fontWeight: 500 }}
              className="chart-axis-tick" domain={[0, Math.max(5, Math.ceil(maxCount / 5) * 5)]} tickCount={6} allowDecimals={false} />
            {summary.total > 0 && <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(0, 0, 0, 0.04)' }} />}
            {SUMMARY_OUTCOMES.map(outcome => (
              <Bar key={outcome.key} dataKey={outcome.key} name={outcome.label} stackId="results"
                fill={outcome.color} barSize={56} shape={<ResultSegment outcomeKey={outcome.key} />}
                isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ul className="summary-result-legend" aria-label="จำนวนผลลัพธ์รวมของสองฟีเจอร์">
        {SUMMARY_OUTCOMES.map(outcome => (
          <li key={outcome.key}>
            <span className="summary-result-swatch" style={{ backgroundColor: outcome.color }} aria-hidden="true" />
            <span className="summary-result-label">{outcome.label}</span>
            <strong>{showCounts ? summary.counts[outcome.key] : '—'}</strong>
          </li>
        ))}
      </ul>
      {showCounts && <table className="summary-accessible-data">
        <caption>จำนวนรายการจากประวัติล่าสุด ไม่ใช่ประวัติทั้งหมด</caption>
        <thead><tr><th scope="col">ประเภท</th>{SUMMARY_OUTCOMES.map(outcome => <th scope="col" key={outcome.key}>{outcome.label}</th>)}<th scope="col">รวม</th></tr></thead>
        <tbody>{summary.types.map(type => <tr key={type.value}><th scope="row">{type.label}</th>{SUMMARY_OUTCOMES.map(outcome => <td key={outcome.key}>{type.outcomes[outcome.key]}</td>)}<td>{type.count}</td></tr>)}</tbody>
      </table>}
    </>
  );
};

export default SummaryResults;
