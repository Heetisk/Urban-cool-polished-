import { useState, useEffect, useCallback } from 'react';
import { MapContainer, TileLayer, Rectangle, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { fetchCells, fetchCell, fetchCellDrivers, fetchDataInfo } from '../api';
import { useCity } from '../context/CityContext';
import CellPanel from '../components/CellPanel';

const MIN_ZOOM = 4;
const MAX_ZOOM = 18;

function getTempColor(temp) {
  if (temp >= 34.5) return '#EF4444';
  if (temp >= 33.5) return '#F97316';
  if (temp >= 33.0) return '#F59E0B';
  return '#22C55E';
}

const TEMP_SOURCE_BADGES = {
  landsat8_satellite: 'Landsat 8',
  satellite: 'MODIS',
  era5_model: 'ERA5',
};

import { memo } from 'react';

const CellRectangle = memo(function CellRectangle({ cell, onSelect, isSelected }) {
  const { geometry, properties } = cell;
  if (!geometry) return null;

  const coords = geometry.coordinates[0];
  const bounds = [
    [coords[0][1], coords[0][0]],
    [coords[2][1], coords[2][0]],
  ];

  const temp = properties.air_temperature_celsius || properties.temp || 0;
  const sourceBadge = TEMP_SOURCE_BADGES[properties.temperature_source] || '';

  return (
    <Rectangle
      key={properties.cell_id}
      bounds={bounds}
      pathOptions={{
        fillColor: getTempColor(temp),
        fillOpacity: isSelected ? 0.8 : 0.5,
        color: isSelected ? '#1E40AF' : '#666',
        weight: isSelected ? 3 : 1,
      }}
      eventHandlers={{
        click: () => onSelect(properties.cell_id),
      }}
    >
      <Popup>
        <div className="text-sm">
          <strong>{properties.cell_id}</strong><br />
          Temp: {temp.toFixed(1)}C
          {sourceBadge && <span className="text-[10px] bg-emerald-100 text-emerald-700 px-1 py-0.5 rounded ml-1">{sourceBadge}</span>}
        </div>
      </Popup>
    </Rectangle>
  );
});

function MapGrid({ cells, onSelect, selectedId }) {
  return cells.map((cell) => (
    <CellRectangle
      key={cell.properties.cell_id}
      cell={cell}
      onSelect={onSelect}
      isSelected={cell.properties.cell_id === selectedId}
    />
  ));
}

function ZoomControls() {
  const map = useMap();
  return (
    <div className="absolute top-20 right-4 z-[100] flex flex-col pointer-events-auto">
      <button
        onClick={() => map.zoomIn()}
        className="w-10 h-10 bg-surface-card border border-hairline rounded-t-lg flex items-center justify-center text-ink cursor-pointer text-xl"
      >+</button>
      <button
        onClick={() => map.zoomOut()}
        className="w-10 h-10 bg-surface-card border border-hairline border-t-0 rounded-b-lg flex items-center justify-center text-ink cursor-pointer text-xl"
      >−</button>
    </div>
  );
}

function MapResizer() {
  const map = useMap();
  useEffect(() => {
    const timer = setTimeout(() => map.invalidateSize(), 100);
    return () => clearTimeout(timer);
  }, [map]);
  return null;
}

function Legend() {
  const items = [
    { color: '#22C55E', label: '< 33°C (Low)' },
    { color: '#F59E0B', label: '33–33.5°C (Moderate)' },
    { color: '#F97316', label: '33.5–34.5°C (High)' },
    { color: '#EF4444', label: '> 34.5°C (Severe)' },
  ];

  return (
    <div className="absolute bottom-20 left-4 z-[100] bg-surface-card/95 backdrop-blur rounded-xl border border-hairline p-4 pointer-events-auto md:bottom-6 md:left-6">
      <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">Temperature</p>
      {items.map(({ color, label }) => (
        <div key={label} className="flex items-center gap-2 mb-1.5">
          <div className="w-4 h-3 rounded" style={{ backgroundColor: color }} />
          <span className="text-xs text-body">{label}</span>
        </div>
      ))}
    </div>
  );
}

export default function HeatMap() {
  const { currentCity } = useCity();
  const [cells, setCells] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [cellDetail, setCellDetail] = useState(null);
  const [drivers, setDrivers] = useState(null);
  const [dataInfo, setDataInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (!currentCity) return;
    setLoading(true);
    setError(null);
    setSelectedId(null);
    setCellDetail(null);
    setDrivers(null);
    setDataInfo(null);
    Promise.all([
      fetchCells(),
      fetchDataInfo().catch(() => null),
    ])
      .then(([cells, info]) => {
        setCells(cells);
        setDataInfo(info);
      })
      .catch((err) => {
        console.error(err);
        setError('Failed to load map data. Please try again.');
      })
      .finally(() => setLoading(false));
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [currentCity, currentCity?.key]);

  const handleSelect = useCallback(async (cellId) => {
    setSelectedId(cellId);
    setCellDetail(null);
    setDrivers(null);
    try {
      const [detail, drv] = await Promise.all([
        fetchCell(cellId),
        fetchCellDrivers(cellId),
      ]);
      setCellDetail(detail);
      setDrivers(drv);
    } catch (err) {
      console.error(err);
    }
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full w-full bg-canvas">
        <div className="text-muted text-lg font-serif">Loading heat map…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full w-full bg-canvas">
        <div className="text-center p-8 bg-surface-card rounded-xl border border-hairline">
          <p className="text-error font-medium mb-2">Error Loading Data</p>
          <p className="text-muted text-sm">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-5 py-2.5 bg-primary text-on-primary rounded-lg text-sm font-medium"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full">
      <MapContainer
        center={currentCity?.center || [23.0225, 72.5714]}
        zoom={currentCity?.zoom || 12}
        className="h-full w-full"
        zoomControl={false}
        style={{ zIndex: 1 }}
        worldCopyJump={true}
        minZoom={MIN_ZOOM}
        maxZoom={MAX_ZOOM}
      >
        <TileLayer
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />
        <MapGrid cells={cells} onSelect={handleSelect} selectedId={selectedId} />
        <ZoomControls />
        <MapResizer />
      </MapContainer>

      <Legend />

      {cellDetail && drivers && (
        <CellPanel
          cell={cellDetail}
          drivers={drivers}
          dataInfo={dataInfo}
          onClose={() => {
            setSelectedId(null);
            setCellDetail(null);
            setDrivers(null);
          }}
        />
      )}
    </div>
  );
}


