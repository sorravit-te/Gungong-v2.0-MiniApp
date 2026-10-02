export default function NavigationIcon({ id }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      {id === 'home' && <><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" /></>}
      {id === 'social' && <><circle cx="9" cy="7" r="4" /><path d="M1 21v-2a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v2M17 3a4 4 0 0 1 0 8M23 21v-2a6 6 0 0 0-4-5.65" /></>}
      {id === 'scanner' && <><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></>}
      {id === 'history' && <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /></>}
      {id === 'report' && <path d="M4 22V3m0 1c5-3 10 3 16 0v12c-6 3-11-3-16 0" />}
    </svg>
  );
}
