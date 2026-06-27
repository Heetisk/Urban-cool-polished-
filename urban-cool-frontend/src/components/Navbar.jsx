import { MapPin, BarChart3, Sliders, LayoutDashboard, AlertTriangle, Target } from 'lucide-react';
import CitySelector from './CitySelector';

const NAV_ITEMS = [
  { id: 'map', label: 'Heat Map', icon: MapPin },
  { id: 'simulator', label: 'Simulator', icon: Sliders },
  { id: 'optimizer', label: 'Optimize', icon: Target },
  { id: 'alerts', label: 'Alerts', icon: AlertTriangle },
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
];

export default function Navbar({ active, onNavigate }) {
  return (
    <>
      {/* Desktop nav — hidden on mobile */}
      <nav className="hidden md:block fixed top-0 left-0 right-0 z-[9999] bg-canvas/95 backdrop-blur-md border-b border-hairline px-6 py-3 pointer-events-auto">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
              <BarChart3 className="w-5 h-5 text-on-primary" />
            </div>
            <span className="font-serif text-xl font-normal tracking-tight text-ink">UrbanCool AI</span>
          </div>

          <div className="flex items-center gap-2">
            <CitySelector />
            {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => onNavigate(id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer ${
                  active === id
                    ? 'bg-primary text-on-primary'
                    : 'text-muted hover:bg-surface-soft hover:text-ink'
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Mobile bottom tab bar — hidden on desktop */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-[9999] bg-surface-card/95 backdrop-blur-md border-t border-hairline pointer-events-auto">
        <div className="flex items-center justify-around h-16">
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => onNavigate(id)}
              className={`flex flex-col items-center justify-center w-16 h-full gap-0.5 transition-colors cursor-pointer ${
                active === id
                  ? 'text-primary'
                  : 'text-muted'
              }`}
            >
              <Icon className="w-5 h-5" />
              <span className="text-[10px] font-medium leading-tight">{label}</span>
              {active === id && (
                <div className="absolute top-0 w-8 h-0.5 bg-primary rounded-full" />
              )}
            </button>
          ))}
        </div>
      </nav>
    </>
  );
}
