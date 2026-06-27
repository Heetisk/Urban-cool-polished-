import { useState, useEffect, useRef } from 'react';
import { Play, TreePine, Droplets, Building, Waves } from 'lucide-react';
import { fetchCells, fetchCell, simulateIntervention, fetchCellDrivers } from '../api';
import { useCity } from '../context/CityContext';

export default function Simulator() {
  const { currentCity } = useCity();
  const [cells, setCells] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [cellDetail, setCellDetail] = useState(null);
  const [treeCover, setTreeCover] = useState(0);
  const [coolRoof, setCoolRoof] = useState(0);
  const [greenRoof, setGreenRoof] = useState(0);
  const [waterBody, setWaterBody] = useState(0);
  const [result, setResult] = useState(null);
  const [drivers, setDrivers] = useState(null);
  const [loading, setLoading] = useState(false);
  const [cellLoading, setCellLoading] = useState(false);
  const resultRef = useRef(null);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (!currentCity) return;
    setSelectedId(null);
    setResult(null);
    fetchCells()
      .then((data) => {
        const sorted = [...data].sort((a, b) => (b.properties.air_temperature_celsius || b.properties.temp || 0) - (a.properties.air_temperature_celsius || a.properties.temp || 0));
        setCells(sorted);
        if (sorted.length > 0) {
          setSelectedId(sorted[0].properties.cell_id);
        }
      })
      .catch(console.error);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [currentCity, currentCity?.key]);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (selectedId) {
      setCellLoading(true);
      setResult(null);
      fetchCell(selectedId)
        .then((detail) => {
          setCellDetail(detail);
        })
        .catch(console.error)
        .finally(() => setCellLoading(false));

      fetchCellDrivers(selectedId)
        .then((drv) => {
          setDrivers(drv);
        })
        .catch(console.error);
    }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [selectedId]);

  const handleSimulate = async () => {
    setLoading(true);
    try {
      const res = await simulateIntervention(selectedId, {
        tree_cover: treeCover,
        cool_roof: coolRoof,
        green_roof: greenRoof,
        water_body: waterBody,
      });
      setResult(res);
      setTimeout(() => {
        resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 100);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-4 md:p-6 pt-20 md:pt-24">
      <h1 className="text-[36px] font-serif font-normal text-ink tracking-tight mb-2">Intervention Simulator</h1>
      <p className="text-muted mb-8">Test cooling strategies for any cell in {currentCity?.name || 'city'}</p>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-surface-card rounded-xl border border-hairline p-8">
            <label className="block text-sm font-semibold text-ink mb-2">Select Cell</label>
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              className="w-full bg-canvas border border-hairline rounded-lg px-4 py-2.5 text-sm text-ink focus:ring-2 focus:ring-primary focus:border-primary"
            >
              {cells.map((c) => (
                <option key={c.properties.cell_id} value={c.properties.cell_id}>
                  {c.properties.cell_id} ({(c.properties.air_temperature_celsius || c.properties.temp)?.toFixed(1)}C)
                </option>
              ))}
            </select>
          </div>

          <div className="bg-surface-card rounded-xl border border-hairline p-8">
            <h3 className="font-serif text-base font-normal text-ink mb-4">Cooling Interventions</h3>

            <div className="space-y-5">
              <SliderControl
                icon={<TreePine className="w-5 h-5 text-green-500" />}
                label="Tree Cover"
                value={treeCover}
                onChange={setTreeCover}
                min={0}
                max={100}
                unit="%"
                description="Increase tree canopy coverage"
              />
              <SliderControl
                icon={<Building className="w-5 h-5 text-blue-500" />}
                label="Albedo Modification (Cool Roofs)"
                value={coolRoof}
                onChange={setCoolRoof}
                min={0}
                max={100}
                unit="%"
                description="Reflective roof coating"
              />
              <SliderControl
                icon={<Droplets className="w-5 h-5 text-emerald-500" />}
                label="Green Roofs"
                value={greenRoof}
                onChange={setGreenRoof}
                min={0}
                max={100}
                unit="%"
                description="Vegetated roof installation"
              />
              <SliderControl
                icon={<Waves className="w-5 h-5 text-cyan-500" />}
                label="Water Body Creation"
                value={waterBody}
                onChange={setWaterBody}
                min={0}
                max={100}
                unit="%"
                description="Add ponds, lakes, or fountains"
              />
            </div>

            <button
              onClick={handleSimulate}
              disabled={loading}
              className="mt-6 w-full bg-primary hover:bg-primary-active text-on-primary font-medium py-3 rounded-lg transition-colors duration-200 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
            >
              <Play className="w-5 h-5" />
              {loading ? 'Simulating...' : 'Run Simulation'}
            </button>
          </div>

          {result && (
            <div ref={resultRef} className="bg-surface-card rounded-xl border border-hairline p-8">
              <h3 className="font-serif text-base font-normal text-ink mb-4">Results</h3>
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="text-center p-4 bg-canvas rounded-xl border border-hairline-soft">
                  <p className="text-xs text-muted-soft mb-1">Before</p>
                  <p className="text-2xl font-bold text-error font-mono">{result.before.toFixed(1)}°C</p>
                </div>
                <div className="text-center p-4 bg-canvas rounded-xl border border-hairline-soft">
                  <p className="text-xs text-muted-soft mb-1">After</p>
                  <p className="text-2xl font-bold text-success font-mono">{result.after.toFixed(1)}°C</p>
                </div>
                <div className="text-center p-4 bg-canvas rounded-xl border border-hairline-soft">
                  <p className="text-xs text-muted-soft mb-1">Reduction</p>
                  <p className="text-2xl font-bold text-primary font-mono">-{result.reduction.toFixed(1)}°C</p>
                </div>
              </div>

              {Object.keys(result.interventions_applied).length > 0 && (
                <div className="space-y-2 mb-4">
                  {Object.entries(result.interventions_applied).map(([key, val]) => (
                    <div key={key} className="flex justify-between text-sm bg-surface-soft rounded-lg px-4 py-2">
                      <span className="text-body capitalize">{key.replace('_', ' ')}</span>
                      <span className="font-mono font-medium text-ink">
                        {val.percent}% -{val.reduction.toFixed(2)}°C
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {result.spatial_effects && result.spatial_effects.n_neighbors_affected > 0 && (
                <div className="border-t border-hairline pt-4 mt-4">
                  <h4 className="text-sm font-semibold text-ink mb-2">
                    Spatial Effects ({result.spatial_effects.n_neighbors_affected} neighbors within {result.spatial_effects.sigma_meters}m)
                  </h4>
                  <p className="text-xs text-muted-soft mb-3">
                    Total spatial cooling spread to neighbors: -{result.spatial_effects.total_spatial_reduction.toFixed(3)}°C
                  </p>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {result.spatial_effects.neighbors.map((n) => (
                      <div key={n.cell_id} className="flex items-center justify-between text-xs bg-surface-soft rounded-lg px-3 py-1.5">
                        <span className="text-body">{n.cell_id}</span>
                        <span className="text-muted-soft">{n.distance_m.toFixed(0)}m</span>
                        <span className="font-mono font-medium text-primary">-{n.reduction.toFixed(3)}°C</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {result.energy_balance && result.energy_balance.residual !== null && (
                <div className="border-t border-hairline pt-4 mt-4">
                  <h4 className="text-sm font-semibold text-ink mb-2">Energy Balance Check</h4>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-surface-soft rounded-lg p-2">
                      <p className="text-accent-amber font-medium">Rn (Net Radiation)</p>
                      <p className="font-mono font-bold text-ink">{result.energy_balance.net_radiation} W/m2</p>
                    </div>
                    <div className="bg-surface-soft rounded-lg p-2">
                      <p className="text-error font-medium">H (Sensible)</p>
                      <p className="font-mono font-bold text-ink">{result.energy_balance.sensible_heat} W/m2</p>
                    </div>
                    <div className="bg-surface-soft rounded-lg p-2">
                      <p className="text-success font-medium">LE (Latent)</p>
                      <p className="font-mono font-bold text-ink">{result.energy_balance.latent_heat} W/m2</p>
                    </div>
                    <div className="bg-surface-soft rounded-lg p-2">
                      <p className="text-accent-amber font-medium">G (Ground)</p>
                      <p className="font-mono font-bold text-ink">{result.energy_balance.ground_heat} W/m2</p>
                    </div>
                  </div>
                  <p className="text-[10px] text-muted-soft mt-2">
                    Residual (Rn - H - LE - G): {result.energy_balance.residual} W/m2
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="space-y-6">
          {cellLoading ? (
            <div className="bg-surface-card rounded-xl border border-hairline p-8">
              <p className="text-muted text-sm">Loading cell data...</p>
            </div>
          ) : cellDetail && (
            <div className="bg-surface-card rounded-xl border border-hairline p-8">
              <h3 className="font-serif text-base font-normal text-ink mb-4">Current Cell Data</h3>
              <div className="space-y-3">
                <DataRow label="Air Temp (est.)" value={(cellDetail.air_temperature_celsius || cellDetail.temp) != null ? `${(cellDetail.air_temperature_celsius || cellDetail.temp).toFixed(1)}C` : '-'} />
                <DataRow label="NDVI" value={cellDetail.ndvi != null ? cellDetail.ndvi.toFixed(3) : '-'} />
                <DataRow label="NDVI Source" value={cellDetail.ndvi_source || '-'} />
                <DataRow label="Built-up Density" value={cellDetail.builtup_density != null ? `${(cellDetail.builtup_density * 100).toFixed(0)}%` : '-'} />
                <DataRow label="Road Density" value={cellDetail.road_density_km_km2 != null ? `${cellDetail.road_density_km_km2.toFixed(1)} km/km2` : '-'} />
                <DataRow label="Distance to Water" value={cellDetail.distance_water_m != null ? `${cellDetail.distance_water_m.toFixed(0)}m` : '-'} />
                <DataRow label="Data Source" value={cellDetail.temperature_source || '-'} />
              </div>
            </div>
          )}

          {drivers && (
            <div className="bg-surface-card rounded-xl border border-hairline p-8">
              <h3 className="font-serif text-base font-normal text-ink mb-3">Key Drivers</h3>
              <p className="text-xs text-muted-soft leading-relaxed">{drivers.summary}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SliderControl({ icon, label, value, onChange, min, max, unit, description }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-sm font-medium text-body">{label}</span>
        </div>
        <span className="text-sm font-mono font-bold text-primary">{value}{unit}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-2 bg-surface-cream-strong rounded-lg appearance-none cursor-pointer accent-primary"
      />
      <p className="text-xs text-muted-soft mt-1">{description}</p>
    </div>
  );
}

function DataRow({ label, value }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-muted">{label}</span>
      <span className="font-mono font-medium text-ink">{value}</span>
    </div>
  );
}
