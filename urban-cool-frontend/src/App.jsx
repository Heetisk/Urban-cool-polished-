import { useState } from 'react';
import { CityProvider } from './context/CityContext';
import Navbar from './components/Navbar';
import HeatMap from './pages/HeatMap';
import Simulator from './pages/Simulator';
import Optimizer from './pages/Optimizer';
import Priority from './pages/Priority';
import Dashboard from './pages/Dashboard';

export default function App() {
  const [page, setPage] = useState('map');

  return (
    <CityProvider>
      <div className="h-full w-full bg-canvas">
        <Navbar active={page} onNavigate={setPage} />
        {page === 'map' && <HeatMap />}
        {page === 'simulator' && <Simulator />}
        {page === 'optimizer' && <Optimizer />}
        {page === 'alerts' && <Priority />}
        {page === 'dashboard' && <Dashboard />}
      </div>
    </CityProvider>
  );
}
