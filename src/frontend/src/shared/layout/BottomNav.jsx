import { PRIMARY_NAV_ITEMS } from '../navigation/appNavigation';
import { SCANNER_ROUTE_IDS } from '../../features/scanner/scannerNavigation';
import NavigationIcon from './NavigationIcon';

const BottomNav = ({ activeSection, onNavigate }) => (
  <nav className="bottom-nav" aria-label="เมนูหลัก">
    {PRIMARY_NAV_ITEMS.map(item => {
      const active = activeSection === item.id ||
        (item.id === 'scanner' && SCANNER_ROUTE_IDS.includes(activeSection));
      return (
        <button key={item.id} type="button"
          className={`${item.isMain ? 'scanner-btn' : 'nav-item'} ${active ? 'active' : ''}`}
          aria-current={active ? 'page' : undefined}
          onClick={() => onNavigate(item.id)}>
          <NavigationIcon id={item.id} />
          <span>{item.label}</span>
        </button>
      );
    })}
  </nav>
);

export default BottomNav;
