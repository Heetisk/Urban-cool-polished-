import { X, TrendingUp, Wind, Droplets, Sun, Satellite, Calendar, MapPin, Leaf, Building2, Droplet, TreePine, ArrowUpRight, ArrowDownRight, Lightbulb } from 'lucide-react';

const HEAT_SOLUTIONS = {
  builtup_density: { solution: "Cool roofs (high-albedo coating)", coeff: 0.05, unit: "per 1% coverage", icon: Building2 },
  ndvi: { solution: "Tree planting & urban greening", coeff: 0.08, unit: "per 1% increase", icon: TreePine },
  distance_water_m: { solution: "Water features (fountains, ponds)", coeff: 0.3, unit: "per 100sqm", icon: Droplet },
  road_density_km_km2: { solution: "Permeable pavements + street trees", coeff: 0.06, unit: "per 1% reduction", icon: Wind },
  building_density_per_km2: { solution: "Green roofs on existing buildings", coeff: 0.06, unit: "per 1% coverage", icon: Leaf },
  sky_view_factor: { solution: "Urban canyon ventilation design", coeff: null, unit: "design guidance", icon: Wind },
  albedo: { solution: "Cool pavements & reflective surfaces", coeff: 0.04, unit: "per 1% increase", icon: Sun },
  ndvi_x_builtup: { solution: "Green corridors in dense areas", coeff: 0.07, unit: "per 1% increase", icon: TreePine },
  distance_x_builtup: { solution: "Distributed water features", coeff: 0.3, unit: "per 100sqm", icon: Droplet },
  emissivity: { solution: "Cool roof coatings", coeff: 0.04, unit: "per 1% increase", icon: Building2 },
  bowen_ratio: { solution: "Increase vegetation for evapotranspiration", coeff: 0.08, unit: "per 1% NDVI increase", icon: TreePine },
  ndvi_spatial_lag: { solution: "Neighborhood-scale tree planting", coeff: 0.08, unit: "per 1% increase", icon: TreePine },
  builtup_density_spatial_lag: { solution: "District-level greening programs", coeff: 0.06, unit: "per 1% reduction", icon: Leaf },
};

const DRIVER_EXPLANATIONS = {
  builtup_density: "High concrete/asphalt absorbs solar radiation and re-radiates as heat",
  ndvi: "Vegetation provides shade and cooling via evapotranspiration",
  distance_water_m: "Distance from water bodies reduces evaporative cooling benefit",
  road_density_km_km2: "Dense road networks increase impervious surfaces and heat absorption",
  building_density_per_km2: "Dense buildings trap heat and reduce wind ventilation",
  sky_view_factor: "Low sky view traps longwave radiation in urban canyons",
  albedo: "Low surface albedo means more solar energy absorbed as heat",
  ndvi_x_builtup: "Low vegetation in dense areas amplifies heat",
  distance_x_builtup: "Dense areas far from water miss cooling benefits",
  ndvi_spatial_lag: "Surrounding vegetation provides neighborhood-level cooling",
  builtup_density_spatial_lag: "Surrounding built-up areas contribute to regional warming",
  emissivity: "Surface emissivity affects how efficiently surfaces radiate heat",
  bowen_ratio: "High Bowen ratio indicates more sensible heat vs evaporative cooling",
};

const SOURCE_STYLES = {
  landsat8_satellite: { label: 'Landsat 8 LST', bg: 'bg-emerald-50 border-emerald-100', text: 'text-emerald-600', textBold: 'text-emerald-700', badgeBg: 'bg-emerald-100', badgeText: 'text-emerald-600', badge: 'GEE', dateRange: 'Apr–Aug 2024' },
  satellite: { label: 'MODIS LST', bg: 'bg-emerald-50 border-emerald-100', text: 'text-emerald-600', textBold: 'text-emerald-700', badgeBg: 'bg-emerald-100', badgeText: 'text-emerald-600', badge: 'NASA Earthdata', dateRange: 'Apr–Jun 2024' },
  ecostress_satellite: { label: 'ECOSTRESS LST', bg: 'bg-cyan-50 border-cyan-100', text: 'text-cyan-600', textBold: 'text-cyan-700', badgeBg: 'bg-cyan-100', badgeText: 'text-cyan-600', badge: 'AppEEARS', dateRange: 'Jun 2024' },
  era5_model: { label: 'ERA5 + Spatial Model', bg: 'bg-blue-50 border-blue-100', text: 'text-blue-600', textBold: 'text-blue-700', badgeBg: 'bg-blue-100', badgeText: 'text-blue-600', badge: 'CDS API', dateRange: 'Apr–Aug 2024' },
  none: { label: 'No Data', bg: 'bg-canvas border-hairline', text: 'text-muted', textBold: 'text-body', badgeBg: 'bg-surface-soft', badgeText: 'text-muted', badge: '', dateRange: '' },
};

export default function CellPanel({ cell, drivers, dataInfo, onClose }) {
  if (!cell || !drivers) return null;

  const maxImpact = Math.max(...drivers.drivers.map((d) => Math.abs(d.impact)), 0.01);
  const tempSource = SOURCE_STYLES[cell.temperature_source] || SOURCE_STYLES.none;

  return (
    <div className="fixed bottom-16 left-0 right-0 z-[100] max-h-[60vh] bg-surface-card rounded-t-2xl border-t border-hairline overflow-hidden pointer-events-auto flex flex-col md:absolute md:top-20 md:right-4 md:left-auto md:w-[380px] md:max-w-[calc(100vw-32px)] md:rounded-xl md:border md:border-hairline md:max-h-[calc(100vh-80px)] md:bottom-auto">
      {/* Drag handle — mobile only */}
      <div className="md:hidden flex justify-center pt-2 pb-1">
        <div className="w-10 h-1 bg-surface-cream-strong rounded-full" />
      </div>
      <div className="bg-surface-dark p-5 flex items-center justify-between">
        <div>
          <h3 className="text-on-dark font-serif text-lg font-normal tracking-wide">{cell.cell_id}</h3>
          <p className="text-on-dark-soft text-xs mt-0.5">Physics-Informed Cell Analysis</p>
        </div>
        <button
          onClick={onClose}
          className="text-on-dark-soft hover:text-on-dark transition-colors cursor-pointer p-1"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Data Source Badge */}
      {cell.temperature_source && cell.temperature_source !== 'none' && (
        <div className={`${tempSource.bg} border-b px-5 py-2.5 flex items-center gap-2`}>
          <Satellite className={`w-4 h-4 ${tempSource.text}`} />
          <span className={`text-xs font-semibold ${tempSource.textBold}`}>{tempSource.badge}</span>
          <span className={`text-[10px] ${tempSource.badgeBg} ${tempSource.badgeText} px-1.5 py-0.5 rounded-full font-medium`}>{tempSource.dateRange}</span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-5">
        {/* Temperature Section - Air Temp first, then LST */}
        <div className="grid grid-cols-2 gap-3 mb-3">
          <StatCard label="Air Temp (est.)" value={`${cell.air_temperature_celsius?.toFixed(1)}°C`} accent="red" />
          <StatCard label="Predicted Air" value={`${cell.predicted_air_temp?.toFixed(1)}°C`} accent="orange" />
        </div>
        <div className="grid grid-cols-2 gap-3 mb-4">
          <StatCard label="Satellite LST" value={`${cell.lst_landsat8_celsius?.toFixed(1) || cell.temp?.toFixed(1)}°C`} accent="green" />
          <StatCard label="Predicted LST" value={`${cell.predicted_temp?.toFixed(1)}°C`} accent="blue" />
        </div>
        <div className="grid grid-cols-2 gap-3 mb-4">
          <StatCard label="UHI Intensity" value={`${cell.uhi_intensity?.toFixed(1)}°C`} accent="orange" />
          <StatCard label="Heat Stress" value={cell.heat_stress_score?.toFixed(0)} accent="red" />
        </div>

        {/* Temperature Source */}
        {cell.temperature_source && (
          <div className="bg-canvas rounded-xl px-3 py-2 mb-4 flex items-center gap-2">
            <MapPin className="w-3.5 h-3.5 text-muted-soft" />
            <span className="text-[11px] text-muted">Source: <span className="font-semibold text-body-strong">{tempSource.label}</span></span>
          </div>
        )}

        {/* Satellite Observations */}
        {(cell.lst_satellite_celsius || cell.lst_landsat8_celsius || cell.ndvi_satellite || cell.ndvi_sentinel2) && (
          <div className="bg-emerald-50 rounded-xl p-3 mb-4 border border-emerald-100">
            <div className="flex items-center gap-2 mb-2">
              <Satellite className="w-3.5 h-3.5 text-emerald-600" />
              <span className="text-xs font-semibold text-emerald-800">Satellite Observations</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {cell.lst_landsat8_celsius && (
                <div>
                  <p className="text-emerald-600 font-medium">Landsat 8 LST</p>
                  <p className="font-mono font-bold text-ink">{cell.lst_landsat8_celsius?.toFixed(1)}°C</p>
                  <p className="text-[10px] text-muted-soft">30m resolution</p>
                </div>
              )}
              {cell.lst_satellite_celsius && (
                <div>
                  <p className="text-emerald-600 font-medium">MODIS LST</p>
                  <p className="font-mono font-bold text-ink">{cell.lst_satellite_celsius?.toFixed(1)}°C</p>
                  <p className="text-[10px] text-muted-soft">1km resolution</p>
                </div>
              )}
              {cell.ndvi_satellite && (
                <div>
                  <p className="text-emerald-600 font-medium">MODIS NDVI</p>
                  <p className="font-mono font-bold text-ink">{cell.ndvi_satellite?.toFixed(3)}</p>
                </div>
              )}
              {cell.ndvi_sentinel2 && (
                <div>
                  <p className="text-emerald-600 font-medium">Sentinel-2 NDVI</p>
                  <p className="font-mono font-bold text-ink">{cell.ndvi_sentinel2?.toFixed(3)}</p>
                  <p className="text-[10px] text-muted-soft">10m resolution</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* CPCB Air Quality */}
        {cell.aqi != null && (
          <div className="bg-amber-50 rounded-xl p-3 mb-4 border border-amber-100">
            <div className="flex items-center gap-2 mb-2">
              <Wind className="w-3.5 h-3.5 text-amber-600" />
              <span className="text-xs font-semibold text-amber-800">Air Quality (CPCB)</span>
              {cell.cpcb_station && <span className="text-[10px] text-amber-500">{cell.cpcb_station}</span>}
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div>
                <p className="text-amber-600 font-medium">AQI</p>
                <p className="font-mono font-bold text-ink">{cell.aqi}</p>
              </div>
              <div>
                <p className="text-amber-600 font-medium">PM2.5</p>
                <p className="font-mono font-bold text-ink">{cell.pm25} ug/m3</p>
              </div>
              <div>
                <p className="text-amber-600 font-medium">PM10</p>
                <p className="font-mono font-bold text-ink">{cell.pm10} ug/m3</p>
              </div>
            </div>
          </div>
        )}

        {/* Physics Features */}
        <div className="border-t border-hairline-soft pt-4 mb-4">
          <h4 className="font-serif text-base font-normal text-ink mb-3 flex items-center gap-2">
            <div className="p-1.5 bg-blue-100 rounded-lg">
              <Sun className="w-3.5 h-3.5 text-blue-600" />
            </div>
            Surface Energy Balance
          </h4>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-blue-50 rounded-lg p-2">
              <p className="text-blue-600 font-medium">Albedo</p>
              <p className="font-mono font-bold text-ink">{cell.albedo?.toFixed(3)}</p>
            </div>
            <div className="bg-blue-50 rounded-lg p-2">
              <p className="text-blue-600 font-medium">Emissivity</p>
              <p className="font-mono font-bold text-ink">{cell.emissivity?.toFixed(3)}</p>
            </div>
            <div className="bg-blue-50 rounded-lg p-2">
              <p className="text-blue-600 font-medium">Sky View Factor</p>
              <p className="font-mono font-bold text-ink">{cell.sky_view_factor?.toFixed(3)}</p>
            </div>
            <div className="bg-blue-50 rounded-lg p-2">
              <p className="text-blue-600 font-medium">Bowen Ratio</p>
              <p className="font-mono font-bold text-ink">{cell.bowen_ratio?.toFixed(2)}</p>
            </div>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <div className="bg-orange-50 rounded-lg p-2">
              <p className="text-orange-600 font-medium">Net Radiation</p>
              <p className="font-mono font-bold text-ink">{cell.net_radiation?.toFixed(0)} W/m²</p>
            </div>
            <div className="bg-red-50 rounded-lg p-2">
              <p className="text-red-600 font-medium">Sensible Heat</p>
              <p className="font-mono font-bold text-ink">{cell.sensible_heat_flux?.toFixed(0)} W/m²</p>
            </div>
            <div className="bg-green-50 rounded-lg p-2">
              <p className="text-green-600 font-medium">Latent Heat</p>
              <p className="font-mono font-bold text-ink">{cell.latent_heat_flux?.toFixed(0)} W/m²</p>
            </div>
            <div className="bg-yellow-50 rounded-lg p-2">
              <p className="text-yellow-600 font-medium">Ground Heat</p>
              <p className="font-mono font-bold text-ink">{cell.ground_heat_flux?.toFixed(0)} W/m²</p>
            </div>
          </div>
        </div>

        {/* Land Cover */}
        <div className="border-t border-hairline-soft pt-4 mb-4">
          <h4 className="font-serif text-base font-normal text-ink mb-3 flex items-center gap-2">
            <div className="p-1.5 bg-green-100 rounded-lg">
              <Wind className="w-3.5 h-3.5 text-green-600" />
            </div>
            Land Cover Properties
          </h4>

          <div className="grid grid-cols-2 gap-3">
            <StatCard label="NDVI" value={cell.ndvi?.toFixed(3)} accent="green" />
            <StatCard label="Built-up" value={`${((cell.builtup_density ?? 0) * 100).toFixed(0)}%`} accent="orange" />
            <StatCard label="Road Density" value={`${cell.road_density_km_km2?.toFixed(1)}`} unit="km/km2" />
            <StatCard label="Distance Water" value={`${cell.distance_water_m?.toFixed(0)}`} unit="m" />
          </div>
        </div>

        {/* Weather */}
        <div className="border-t border-hairline-soft pt-4 mb-4">
          <h4 className="font-serif text-base font-normal text-ink mb-3 flex items-center gap-2">
            <div className="p-1.5 bg-cyan-100 rounded-lg">
              <Droplets className="w-3.5 h-3.5 text-cyan-600" />
            </div>
            Weather Conditions (ERA5)
          </h4>

          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="text-center">
              <p className="text-muted">Humidity</p>
              <p className="font-mono font-bold text-ink">{cell.humidity_pct?.toFixed(0)}%</p>
            </div>
            <div className="text-center">
              <p className="text-muted">Wind</p>
              <p className="font-mono font-bold text-ink">{cell.wind_speed_ms?.toFixed(1)} m/s</p>
            </div>
            <div className="text-center">
              <p className="text-muted">Solar</p>
              <p className="font-mono font-bold text-ink">{cell.solar_wm2?.toFixed(0)} W/m²</p>
            </div>
          </div>
        </div>

        {/* SHAP Drivers */}
        <div className="border-t border-hairline-soft pt-4 mb-4">
          <h4 className="font-serif text-base font-normal text-ink mb-4 flex items-center gap-2">
            <div className="p-1.5 bg-primary/10 rounded-lg">
              <TrendingUp className="w-3.5 h-3.5 text-primary" />
            </div>
            Spatial Drivers (ML Residual)
          </h4>
          <p className="text-[10px] text-muted-soft mb-3">Predicted: {cell.predicted_temp?.toFixed(1)}°C | Actual: {cell.temp?.toFixed(1)}°C | Error: {cell.prediction_error?.toFixed(2)}°C</p>

          <div className="space-y-3">
            {drivers.drivers
              .filter((d) => Math.abs(d.impact) > 0.001)
              .slice(0, 8)
              .map((d) => {
                const barWidth = Math.min((Math.abs(d.impact) / maxImpact) * 100, 100);
                const isPositive = d.impact > 0;
                return (
                  <div key={d.feature}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-medium text-body">{d.feature_name}</span>
                      <span
                        className={`text-xs font-mono font-bold ${
                          isPositive ? 'text-red-500' : 'text-emerald-500'
                        }`}
                      >
                        {isPositive ? '+' : ''}{d.impact.toFixed(2)}°C
                      </span>
                    </div>
                    <div className="w-full bg-surface-soft rounded-full h-2.5 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          isPositive ? 'bg-red-400' : 'bg-emerald-400'
                        }`}
                        style={{ width: `${barWidth}%` }}
                      />
                    </div>
                  </div>
                );
              })}
          </div>

          {/* What's Driving the Heat */}
          <div className="mt-4 bg-surface-soft rounded-xl p-3 border border-hairline-soft">
            <h5 className="text-[11px] font-semibold text-muted uppercase tracking-wider mb-2">What's Driving the Heat</h5>
            <div className="space-y-2">
              {drivers.drivers
                .filter((d) => Math.abs(d.impact) > 0.001)
                .slice(0, 5)
                .map((d) => {
                  const isPositive = d.impact > 0;
                  const explanation = DRIVER_EXPLANATIONS[d.feature];
                  return (
                    <div key={d.feature} className="flex items-start gap-2">
                      <div className={`mt-0.5 flex-shrink-0 ${isPositive ? 'text-red-500' : 'text-emerald-500'}`}>
                        {isPositive ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-semibold text-body">{d.feature_name}</span>
                          <span className={`text-[10px] font-mono font-bold ${isPositive ? 'text-red-500' : 'text-emerald-500'}`}>
                            {isPositive ? '+' : ''}{d.impact.toFixed(2)}°C
                          </span>
                        </div>
                        {explanation && (
                          <p className="text-[10px] text-muted-soft leading-relaxed mt-0.5">{explanation}</p>
                        )}
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>

          {/* How to Cool This Cell */}
          <div className="mt-3 bg-emerald-50 rounded-xl p-3 border border-emerald-100">
            <h5 className="text-[11px] font-semibold text-emerald-800 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Lightbulb className="w-3 h-3" />
              How to Cool This Cell
            </h5>
            <div className="space-y-2">
              {drivers.drivers
                .filter((d) => d.impact > 0.001 && HEAT_SOLUTIONS[d.feature])
                .slice(0, 4)
                .map((d) => {
                  const sol = HEAT_SOLUTIONS[d.feature];
                  const Icon = sol.icon;
                  const estCooling = sol.coeff ? (sol.coeff * 20).toFixed(2) : null;
                  return (
                    <div key={d.feature} className="flex items-start gap-2">
                      <div className="mt-0.5 flex-shrink-0 text-emerald-600">
                        <Icon className="w-3.5 h-3.5" />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-semibold text-emerald-900">{sol.solution}</span>
                        </div>
                        <p className="text-[10px] text-emerald-700 mt-0.5">
                          Est. cooling: <span className="font-mono font-bold">{estCooling ? `-${estCooling}°C` : 'design guidance'}</span>
                          <span className="text-emerald-600 ml-1">{sol.unit}</span>
                        </p>
                      </div>
                    </div>
                  );
                })}
              {drivers.drivers.filter((d) => d.impact > 0.001 && HEAT_SOLUTIONS[d.feature]).length === 0 && (
                <p className="text-[10px] text-emerald-700 italic">No high-impact heat drivers with available interventions.</p>
              )}
            </div>
          </div>
        </div>

        <div className="bg-surface-soft rounded-xl p-4 border border-hairline-soft">
          <p className="text-xs text-body leading-relaxed">{drivers.summary}</p>
        </div>

        {/* Data Timeline */}
        {dataInfo?.sources?.length > 0 && (
          <div className="mt-4 border-t border-hairline-soft pt-4">
            <h4 className="font-serif text-base font-normal text-ink mb-3 flex items-center gap-2">
              <div className="p-1.5 bg-slate-100 rounded-lg">
                <Calendar className="w-3.5 h-3.5 text-slate-600" />
              </div>
              Data Timeline
            </h4>
            <div className="space-y-1.5">
              {dataInfo.sources.map((src, i) => (
                <p key={i} className="text-[11px] text-muted font-mono leading-relaxed">{src}</p>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, unit, accent }) {
  const accentColors = {
    red: 'text-error',
    blue: 'text-primary',
    green: 'text-success',
    orange: 'text-accent-amber',
  };

  return (
    <div className="bg-canvas rounded-xl p-3 border border-hairline-soft shadow-sm">
      <p className="text-[11px] text-muted-soft mb-1 uppercase tracking-wide font-medium">{label}</p>
      <p className={`text-base font-bold font-mono ${accent ? accentColors[accent] : 'text-ink'}`}>
        {value}
        {unit && <span className="text-[10px] text-muted-soft font-normal ml-0.5">{unit}</span>}
      </p>
    </div>
  );
}
