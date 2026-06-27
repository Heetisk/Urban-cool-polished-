import { useCity } from '../context/CityContext';
import { MapPin } from 'lucide-react';

export default function CitySelector() {
  const { cities, currentCity, switchCity, loading } = useCity();

  if (loading || cities.length <= 1) return null;

  return (
    <div className="flex items-center gap-2">
      <MapPin className="w-4 h-4 text-muted" />
      <select
        value={currentCity?.key || ''}
        onChange={(e) => switchCity(e.target.value)}
        className="bg-canvas border border-hairline rounded-lg px-3 py-1.5 text-sm font-medium text-body focus:ring-2 focus:ring-primary focus:border-primary cursor-pointer"
      >
        {cities.map((city) => (
          <option key={city.key} value={city.key} disabled={!city.has_data}>
            {city.name}{city.state ? `, ${city.state}` : ''}{!city.has_data ? ' (coming soon)' : ''}
          </option>
        ))}
      </select>
    </div>
  );
}
