import { useState, useEffect } from 'react';
import { Thermometer, MapPin, TrendingUp, AlertTriangle } from 'lucide-react';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Legend, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';
import { fetchDashboard, fetchGlobalDrivers, fetchHotspots, fetchValidation, fetchDataInfo } from '../api';
import { useCity } from '../context/CityContext';

const PIE_COLORS = ['#22C55E', '#F59E0B', '#EF4444'];

export default function Dashboard() {
  const { currentCity } = useCity();
  const [stats, setStats] = useState(null);
  const [drivers, setDrivers] = useState(null);
  const [hotspots, setHotspots] = useState([]);
  const [validation, setValidation] = useState(null);
  const [dataInfo, setDataInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (!currentCity) return;
    setLoading(true);

    // Track individual failures for better error reporting
    const results = { stats: null, drivers: null, hotspots: [], validation: null, dataInfo: null };
    const errors = [];

    Promise.allSettled([
      fetchDashboard().then((s) => { results.stats = s; }),
      fetchGlobalDrivers().then((d) => { results.drivers = d; }),
      fetchHotspots(10).then((h) => { results.hotspots = h; }),
      fetchValidation().then((v) => { results.validation = v; }).catch(() => {}),
      fetchDataInfo().then((info) => { results.dataInfo = info; }).catch(() => {}),
    ]).then((settled) => {
      settled.forEach((result) => {
        if (result.status === 'rejected') {
          errors.push(result.reason);
        }
      });

      setStats(results.stats);
      setDrivers(results.drivers);
      setHotspots(results.hotspots);
      setValidation(results.validation);
      setDataInfo(results.dataInfo);

      if (errors.length > 0) {
        console.warn('Dashboard partial load errors:', errors);
      }
    }).finally(() => setLoading(false));
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [currentCity]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full w-full">
        <div className="text-muted text-lg">Loading dashboard...</div>
      </div>
    );
  }

  const riskData = stats
    ? [
        { name: 'Low Risk', value: stats.low_risk_cells },
        { name: 'Moderate', value: stats.moderate_risk_cells },
        { name: 'High', value: stats.high_risk_cells },
      ]
    : [];

  const driverData = drivers
    ? drivers.features.slice(0, 10).map((f, i) => ({
        name: drivers.feature_names[f] || f,
        importance: drivers.importance[i] * 100,
      }))
    : [];

  const hotspotData = hotspots.map((h) => ({
    name: h.cell_id.split('_').slice(1).join('_'),
    temp: h.air_temperature_celsius || h.temp,
  }));

  const physicsData = stats?.physics_radar || [];

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-6 pt-20 md:pt-24">
      <h1 className="text-[36px] font-serif font-normal text-ink tracking-tight mb-2">Dashboard</h1>
      <p className="text-muted mb-8">{currentCity?.name || 'City'} Urban Heat Overview</p>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <StatCard
          icon={<MapPin className="w-5 h-5 text-primary" />}
          label="Total Cells"
          value={stats?.total_cells || 0}
        />
        <StatCard
          icon={<Thermometer className="w-5 h-5 text-red-500" />}
          label="Highest Temp (est. air)"
          value={`${stats?.max_temp?.toFixed(1)}C`}
        />
        <StatCard
          icon={<TrendingUp className="w-5 h-5 text-amber-500" />}
          label="Average Temp (est. air)"
          value={`${stats?.avg_temp?.toFixed(1)}C`}
        />
        <StatCard
          icon={<AlertTriangle className="w-5 h-5 text-orange-500" />}
          label="High Risk Cells"
          value={stats?.high_risk_cells || 0}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="bg-surface-card rounded-xl border border-hairline p-8">
          <h3 className="font-serif text-base font-normal text-ink mb-4">Risk Distribution</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={riskData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={3}
                dataKey="value"
              >
                {riskData.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-surface-card rounded-xl border border-hairline p-8">
          <h3 className="font-serif text-base font-normal text-ink mb-4">Feature Importance (Top 10)</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={driverData} layout="vertical" margin={{ left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis dataKey="name" type="category" width={120} tick={{ fontSize: 10 }} />
              <Tooltip formatter={(v) => `${v.toFixed(1)}%`} />
              <Bar dataKey="importance" fill="#3B82F6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-surface-card rounded-xl border border-hairline p-8">
          <h3 className="font-serif text-base font-normal text-ink mb-4">Top Hotspots (Temperature)</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={hotspotData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-45} textAnchor="end" height={60} />
              <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => `${v.toFixed(1)}C`} />
              <Bar dataKey="temp" radius={[4, 4, 0, 0]}>
                {hotspotData.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.temp >= 40 ? '#EF4444' : entry.temp >= 37 ? '#F97316' : '#F59E0B'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-surface-card rounded-xl border border-hairline p-8">
          <h3 className="font-serif text-base font-normal text-ink mb-4">Physics-Informed Energy Balance</h3>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={physicsData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="subject" tick={{ fontSize: 12 }} />
              <PolarRadiusAxis angle={30} domain={[0, 100]} />
              <Radar name="Energy Balance" dataKey="A" stroke="#3B82F6" fill="#3B82F6" fillOpacity={0.5} />
              <Tooltip />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-surface-card rounded-xl border border-hairline p-8">
          <h3 className="font-serif text-base font-normal text-ink mb-4">Temperature Trend Across Hotspots</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={hotspotData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-45} textAnchor="end" height={60} />
              <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => `${v.toFixed(1)}C`} />
              <Legend />
              <Line
                type="monotone"
                dataKey="temp"
                stroke="#EF4444"
                strokeWidth={2}
                dot={{ r: 4, fill: '#EF4444' }}
                name="Temperature (C)"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {validation?.available && validation.spatial_cv && (
        <div className="bg-surface-dark rounded-xl border border-surface-dark-elevated p-8">
          <h3 className="font-serif text-base font-normal text-on-dark mb-2">Model Validation (Spatial Cross-Validation)</h3>
          <p className="text-xs text-on-dark-soft mb-4">{validation.model}</p>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="text-center p-4 bg-surface-dark-elevated rounded-lg">
              <p className="text-xs text-on-dark-soft mb-1">MAE</p>
              <p className="text-xl font-bold text-on-dark font-mono">{validation.spatial_cv.mae_mean} +/- {validation.spatial_cv.mae_std}C</p>
              {validation.spatial_cv.physics_only_mae && (
                <p className="text-[10px] text-on-dark-soft mt-1">Physics only: {validation.spatial_cv.physics_only_mae}C</p>
              )}
            </div>
            <div className="text-center p-4 bg-surface-dark-elevated rounded-lg">
              <p className="text-xs text-on-dark-soft mb-1">RMSE</p>
              <p className="text-xl font-bold text-on-dark font-mono">{validation.spatial_cv.rmse_mean} +/- {validation.spatial_cv.rmse_std}C</p>
            </div>
            <div className="text-center p-4 bg-surface-dark-elevated rounded-lg">
              <p className="text-xs text-on-dark-soft mb-1">R2</p>
              <p className="text-xl font-bold text-on-dark font-mono">{validation.spatial_cv.r2_mean} +/- {validation.spatial_cv.r2_std}</p>
              {validation.spatial_cv.physics_only_r2 != null && (
                <p className="text-[10px] text-on-dark-soft mt-1">Physics only: {validation.spatial_cv.physics_only_r2}</p>
              )}
            </div>
          </div>
          <div className="text-xs text-on-dark-soft space-y-1">
            <p>ML Features: {validation.ml_features?.length ?? validation.n_ml_features ?? 0} (urban morphology)</p>
            <p>Physics Features: {validation.physics_features?.length ?? 0} (atmospheric/surface)</p>
            <p>Spatial blocks: {validation.spatial_cv.n_blocks}x{validation.spatial_cv.n_blocks} ({validation.spatial_cv.n_folds} folds)</p>
            {validation.alpha && <p>Ridge alpha: {validation.alpha}</p>}
          </div>
        </div>
      )}

      <div className="bg-surface-card rounded-xl border border-hairline p-8">
        <h3 className="font-serif text-base font-normal text-ink mb-1">Data Sources</h3>
        <p className="text-xs text-muted-soft mb-4">Study period: Apr 1 – Aug 31, 2024 | Generated: {dataInfo?.generated_at || '—'}</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div className="space-y-3">
            <p className="text-xs font-semibold text-muted uppercase tracking-wide">Satellite Data</p>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
              <a href="https://www.usgs.gov/landsat-missions/landsat-8" target="_blank" rel="noopener noreferrer" className="text-body underline hover:text-emerald-600">Landsat 8 LST - 30m Thermal</a>
              <span className="text-[10px] bg-teal-100 text-teal-600 px-1.5 py-0.5 rounded-full font-medium">GEE</span>
              <span className="text-[10px] text-muted-soft">Apr–Aug 2024</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-lime-500"></div>
              <a href="https://sentinel.esa.int/web/sentinel/missions/sentinel-2" target="_blank" rel="noopener noreferrer" className="text-body underline hover:text-lime-600">Sentinel-2 NDVI - 10m Vegetation</a>
              <span className="text-[10px] bg-lime-100 text-lime-600 px-1.5 py-0.5 rounded-full font-medium">GEE</span>
              <span className="text-[10px] text-muted-soft">Apr–Aug 2024</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-green-500"></div>
              <a href="https://lpdaac.usgs.gov/products/mod11a1v061/" target="_blank" rel="noopener noreferrer" className="text-body underline hover:text-green-600">MODIS LST (MOD11A1) - 1km Daily</a>
              <span className="text-[10px] bg-green-100 text-green-600 px-1.5 py-0.5 rounded-full font-medium">NASA</span>
              <span className="text-[10px] text-muted-soft">Apr–Jun 2024</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-green-600"></div>
              <a href="https://lpdaac.usgs.gov/products/mod13a2v061/" target="_blank" rel="noopener noreferrer" className="text-body underline hover:text-green-600">MODIS NDVI (MOD13A2) - 1km 16-day</a>
              <span className="text-[10px] bg-green-100 text-green-600 px-1.5 py-0.5 rounded-full font-medium">NASA</span>
              <span className="text-[10px] text-muted-soft">Mar–Aug 2024</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-cyan-500"></div>
              <a href="https://ecostress.jpl.nasa.gov/" target="_blank" rel="noopener noreferrer" className="text-body underline hover:text-cyan-600">ECOSTRESS LST - 70m Thermal</a>
              <span className="text-[10px] bg-cyan-100 text-cyan-600 px-1.5 py-0.5 rounded-full font-medium">AppEEARS</span>
              <span className="text-[10px] text-muted-soft">Jun 2024</span>
            </div>
          </div>
          <div className="space-y-3">
            <p className="text-xs font-semibold text-muted uppercase tracking-wide">Weather & Maps</p>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-blue-500"></div>
              <a href="https://cds.climate.copernicus.eu/" target="_blank" rel="noopener noreferrer" className="text-body underline hover:text-blue-600">ERA5 Reanalysis - Humidity, Wind, Solar</a>
              <span className="text-[10px] bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded-full font-medium">CDS API</span>
              <span className="text-[10px] text-muted-soft">Apr–Aug 2024</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-orange-500"></div>
              <a href="https://www.openstreetmap.org/" target="_blank" rel="noopener noreferrer" className="text-body underline hover:text-orange-600">OpenStreetMap - Roads, Buildings, Water</a>
              <span className="text-[10px] bg-orange-100 text-orange-600 px-1.5 py-0.5 rounded-full font-medium">Overpass API</span>
              <span className="text-[10px] text-muted-soft">Current</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-muted"></div>
              <span className="text-body">GHSL Building Density - Approximated via OSM</span>
              <span className="text-[10px] bg-surface-soft text-body px-1.5 py-0.5 rounded-full font-medium">Proxy</span>
            </div>
          </div>
          <div className="space-y-3">
            <p className="text-xs font-semibold text-muted uppercase tracking-wide">Air Quality</p>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-amber-500"></div>
              <a href="https://app.cpcbccr.com/" target="_blank" rel="noopener noreferrer" className="text-body underline hover:text-amber-600">CPCB AQI - PM2.5, PM10</a>
              <span className="text-[10px] bg-amber-100 text-amber-600 px-1.5 py-0.5 rounded-full font-medium">data.gov.in</span>
              <span className="text-[10px] text-muted-soft">{dataInfo?.cpcb?.stations || '—'} stations</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value }) {
  return (
    <div className="bg-surface-card rounded-xl border border-hairline p-5">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-canvas rounded-lg border border-hairline-soft">{icon}</div>
        <div>
          <p className="text-xs text-muted">{label}</p>
          <p className="text-xl font-bold text-ink font-mono">{value}</p>
        </div>
      </div>
    </div>
  );
}
