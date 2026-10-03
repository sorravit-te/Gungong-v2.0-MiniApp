import { lazy, Suspense, useEffect } from 'react';
import '../dataVisualization.css';
import { useHistoryEntries } from '../../history/hooks/useHistoryEntries';
import { summarizeScannerHistory } from '../../history/utils/historyView';

const SummaryResults = lazy(() => import('./SummaryResults'));

const DataVisualization = ({ onNavigate }) => {
  const { entries, loading, error } = useHistoryEntries();
  const summary = summarizeScannerHistory(entries);
  useEffect(() => { void import('./SummaryResults').catch(() => {}); }, []);
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

      {/* Keep the chart axes visible even while signed out; never create sample scans. */}
      {loading && summary.total === 0
        ? <div className="summary-chart-loading" aria-hidden="true"><span /><span /></div>
        : <Suspense fallback={<div className="summary-chart-loading" aria-hidden="true"><span /><span /></div>}>
            <SummaryResults summary={summary} showCounts={summary.total > 0 || (!loading && !error)} />
          </Suspense>}
      {loading ? <p role="status" className="summary-load-message">กำลังโหลดข้อมูล...</p>
        : error ? <p role="alert" className="summary-load-message">{error}</p>
        : summary.total === 0 ? <p className="summary-load-message">ยังไม่มีประวัติการตรวจสอบ</p>
        : null}
    </div>
  );
};

export default DataVisualization;
