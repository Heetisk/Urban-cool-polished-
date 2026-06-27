import { useState } from 'react';
import { Target, Zap, DollarSign, TreePine, Home, Droplets, Wind, BarChart3 } from 'lucide-react';
import { runOptimization, compareScenarios } from '../api';

const INTERVENTION_TYPES = [
  { key: 'tree_cover', label: 'Tree Cover', icon: TreePine, color: 'text-green-600', cost: 5000 },
  { key: 'cool_roof', label: 'Albedo Modification (Cool Roofs)', icon: Home, color: 'text-blue-600', cost: 8000 },
  { key: 'green_roof', label: 'Green Roofs', icon: Home, color: 'text-emerald-600', cost: 12000 },
  { key: 'water_body', label: 'Water Bodies', icon: Droplets, color: 'text-cyan-600', cost: 50000 },
];

export default function Optimizer() {
  const [budget, setBudget] = useState(500000);
  const [intensity, setIntensity] = useState(50);
  const [allowedTypes, setAllowedTypes] = useState(['tree_cover', 'cool_roof', 'green_roof']);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [scenarios, setScenarios] = useState([]);
  const [comparison, setComparison] = useState(null);

  const handleOptimize = async () => {
    setLoading(true);
    try {
      const data = await runOptimization({
        budget,
        intensity,
        intervention_types: allowedTypes,
        max_per_cell: 1,
      });
      setResult(data);
    } catch (err) {
      console.error('Optimization failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const saveScenario = () => {
    if (!result) return;
    const name = `Scenario ${scenarios.length + 1} (${new Date().toLocaleTimeString()})`;
    setScenarios([...scenarios, { name, ...result }]);
  };

  const handleCompare = async () => {
    if (scenarios.length < 2) return;
    try {
      const data = await compareScenarios(
        scenarios[scenarios.length - 2],
        scenarios[scenarios.length - 1]
      );
      setComparison(data);
    } catch (err) {
      console.error('Comparison failed:', err);
    }
  };

  const toggleType = (key) => {
    setAllowedTypes((prev) =>
      prev.includes(key) ? prev.filter((t) => t !== key) : [...prev, key]
    );
  };

  return (
    <div className="pt-20 pb-8 px-4 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-[36px] font-serif font-normal text-ink tracking-tight flex items-center gap-3">
          <Target className="w-8 h-8 text-primary" />
          City-Wide Optimization
        </h1>
        <p className="text-muted mt-2">
          Greedy budget-constrained placement of cooling interventions across all grid cells
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Controls */}
        <div className="lg:col-span-1 space-y-6">
          {/* Budget */}
          <div className="bg-surface-card rounded-xl p-8 border border-hairline">
            <h3 className="font-semibold text-ink mb-4 flex items-center gap-2">
              <DollarSign className="w-5 h-5" />
              Budget (INR)
            </h3>
            <input
              type="number"
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
              className="w-full px-4 py-2 border border-hairline rounded-lg text-lg font-mono bg-canvas text-ink"
              step={100000}
              min={100000}
            />
            <div className="flex gap-2 mt-3">
              {[200000, 500000, 1000000, 2000000].map((b) => (
                <button
                  key={b}
                  onClick={() => setBudget(b)}
                  className={`px-3 py-1 rounded-lg text-sm font-medium transition ${
                    budget === b ? 'bg-primary text-white' : 'bg-surface-soft text-muted hover:bg-surface-cream-strong'
                  }`}
                >
                  {(b / 100000).toFixed(0)}L
                </button>
              ))}
            </div>
          </div>

          {/* Intensity */}
          <div className="bg-surface-card rounded-xl p-8 border border-hairline">
            <h3 className="font-semibold text-ink mb-4 flex items-center gap-2">
              <Zap className="w-5 h-5" />
              Intervention Intensity: {intensity}%
            </h3>
            <input
              type="range"
              min={10}
              max={100}
              value={intensity}
              onChange={(e) => setIntensity(Number(e.target.value))}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-muted mt-1">
              <span>10% (Light)</span>
              <span>100% (Full)</span>
            </div>
          </div>

          {/* Intervention Types */}
          <div className="bg-surface-card rounded-xl p-8 border border-hairline">
            <h3 className="font-semibold text-ink mb-4">Intervention Types</h3>
            <div className="space-y-3">
              {INTERVENTION_TYPES.map(({ key, label, icon: Icon, color, cost }) => (
                <label
                  key={key}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition ${
                    allowedTypes.includes(key)
                    ? 'border-primary bg-primary/5'
                    : 'border-hairline hover:border-muted'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={allowedTypes.includes(key)}
                    onChange={() => toggleType(key)}
                    className="w-4 h-4 text-primary rounded"
                  />
                  <Icon className={`w-5 h-5 ${color}`} />
                  <div className="flex-1">
                    <span className="font-medium text-ink">{label}</span>
                    <span className="text-xs text-muted ml-2">
                      INR {(cost / 1000).toFixed(0)}K/unit
                    </span>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Run Button */}
          <button
            onClick={handleOptimize}
            disabled={loading || allowedTypes.length === 0}
            className="w-full py-3 bg-primary text-on-primary rounded-lg font-medium hover:bg-primary-active transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Optimizing...
              </>
            ) : (
              <>
                <Target className="w-5 h-5" />
                Run Optimization
              </>
            )}
          </button>

          {/* Scenario Actions */}
          {result && (
            <div className="flex gap-2">
              <button
                onClick={saveScenario}
                className="flex-1 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition"
              >
                Save Scenario
              </button>
              {scenarios.length >= 2 && (
                <button
                  onClick={handleCompare}
                  className="flex-1 py-2 bg-purple-600 text-white rounded-lg font-medium hover:bg-purple-700 transition"
                >
                  Compare Last 2
                </button>
              )}
            </div>
          )}
        </div>

        {/* Right: Results */}
        <div className="lg:col-span-2 space-y-6">
          {/* Summary Cards */}
          {result && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                label="Total Cooling"
                value={`${result.summary.total_estimated_cooling_c.toFixed(2)}°C`}
                icon={<Wind className="w-5 h-5 text-blue-500" />}
              />
              <StatCard
                label="Budget Spent"
                value={`INR ${(result.summary.spent_inr / 1000).toFixed(0)}K`}
                icon={<DollarSign className="w-5 h-5 text-green-500" />}
              />
              <StatCard
                label="Cells Affected"
                value={`${result.summary.cells_affected} / ${result.summary.total_cells}`}
                icon={<Target className="w-5 h-5 text-orange-500" />}
              />
              <StatCard
                label="Budget Used"
                value={`${result.summary.budget_utilization_pct.toFixed(1)}%`}
                icon={<BarChart3 className="w-5 h-5 text-purple-500" />}
              />
            </div>
          )}

          {/* Intervention Mix */}
          {result && result.summary.intervention_mix && (
            <div className="bg-surface-card rounded-xl p-8 border border-hairline">
              <h3 className="font-semibold text-ink mb-4">Intervention Mix</h3>
              <div className="flex gap-4">
                {Object.entries(result.summary.intervention_mix).map(([type, count]) => {
                  const info = INTERVENTION_TYPES.find((t) => t.key === type);
                  return (
                    <div key={type} className="flex items-center gap-2">
                      {info && <info.icon className={`w-5 h-5 ${info.color}`} />}
                      <span className="font-medium">{info?.label || type}</span>
                      <span className="text-muted">×{count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Allocations Table */}
          {result && result.allocations.length > 0 && (
            <div className="bg-surface-card rounded-xl p-8 border border-hairline">
              <h3 className="font-semibold text-ink mb-4">
                Top Allocations ({result.allocations.length} total)
              </h3>
              <div className="overflow-x-auto max-h-96 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-surface-card">
                    <tr>
                      <th className="text-left py-2 px-3 font-medium text-muted text-xs uppercase tracking-wider">#</th>
                      <th className="text-left py-2 px-3 font-medium text-muted text-xs uppercase tracking-wider">Cell</th>
                      <th className="text-left py-2 px-3 font-medium text-muted text-xs uppercase tracking-wider">Intervention</th>
                      <th className="text-right py-2 px-3 font-medium text-muted text-xs uppercase tracking-wider">Cooling</th>
                      <th className="text-right py-2 px-3 font-medium text-muted text-xs uppercase tracking-wider">Cost</th>
                      <th className="text-right py-2 px-3 font-medium text-muted text-xs uppercase tracking-wider">Impact/₹</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.allocations.slice(0, 50).map((a, i) => {
                      const info = INTERVENTION_TYPES.find((t) => t.key === a.intervention);
                      return (
                        <tr key={i} className="border-t border-hairline-soft hover:bg-surface-soft">
                          <td className="py-2 px-3 text-muted">{i + 1}</td>
                          <td className="py-2 px-3 font-mono text-xs">{a.cell_id}</td>
                          <td className="py-2 px-3">
                            <span className={`font-medium ${info?.color || ''}`}>
                              {info?.label || a.intervention}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-right text-green-600 font-medium">
                            -{a.estimated_cooling_c.toFixed(3)}°C
                          </td>
                          <td className="py-2 px-3 text-right text-muted">
                            INR {(a.cost_inr / 1000).toFixed(0)}K
                          </td>
                          <td className="py-2 px-3 text-right text-primary">
                            {a.impact_per_dollar.toExponential(2)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Scenario Comparison Table */}
          {comparison && (
            <div className="bg-surface-card rounded-xl p-8 border border-hairline">
              <h3 className="font-semibold text-ink mb-4">Scenario Comparison</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-hairline">
                    <th className="text-left py-3 px-4 font-medium text-muted">Metric</th>
                    <th className="text-center py-3 px-4 font-medium text-primary">Scenario A</th>
                    <th className="text-center py-3 px-4 font-medium text-primary">Scenario B</th>
                    <th className="text-center py-3 px-4 font-medium text-muted">Winner</th>
                  </tr>
                </thead>
                <tbody>
                  <CompareRow
                    label="Total Cooling"
                    a={`${comparison.scenario_a.total_cooling_c.toFixed(2)}°C`}
                    b={`${comparison.scenario_b.total_cooling_c.toFixed(2)}°C`}
                    aVal={comparison.scenario_a.total_cooling_c}
                    bVal={comparison.scenario_b.total_cooling_c}
                  />
                  <CompareRow
                    label="Total Cost"
                    a={`INR ${(comparison.scenario_a.total_cost_inr / 1000).toFixed(0)}K`}
                    b={`INR ${(comparison.scenario_b.total_cost_inr / 1000).toFixed(0)}K`}
                    aVal={comparison.scenario_a.total_cost_inr}
                    bVal={comparison.scenario_b.total_cost_inr}
                  />
                  <CompareRow
                    label="Cells Affected"
                    a={String(comparison.scenario_a.cells_affected)}
                    b={String(comparison.scenario_b.cells_affected)}
                    aVal={comparison.scenario_a.cells_affected}
                    bVal={comparison.scenario_b.cells_affected}
                  />
                  <CompareRow
                    label="Avg Cooling/Cell"
                    a={`${comparison.scenario_a.avg_cooling_per_cell_c.toFixed(3)}°C`}
                    b={`${comparison.scenario_b.avg_cooling_per_cell_c.toFixed(3)}°C`}
                    aVal={comparison.scenario_a.avg_cooling_per_cell_c}
                    bVal={comparison.scenario_b.avg_cooling_per_cell_c}
                  />
                  <CompareRow
                    label="Budget Utilization"
                    a={`${comparison.scenario_a.budget_utilization_pct.toFixed(1)}%`}
                    b={`${comparison.scenario_b.budget_utilization_pct.toFixed(1)}%`}
                    aVal={comparison.scenario_a.budget_utilization_pct}
                    bVal={comparison.scenario_b.budget_utilization_pct}
                  />
                </tbody>
              </table>
            </div>
          )}

          {/* Saved Scenarios List */}
          {scenarios.length > 0 && (
            <div className="bg-surface-card rounded-xl p-8 border border-hairline">
              <h3 className="font-semibold text-ink mb-4">Saved Scenarios ({scenarios.length})</h3>
              <div className="space-y-2">
                {scenarios.map((s, i) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-surface-soft rounded-lg">
                    <div>
                      <span className="font-medium">{s.name}</span>
                      <span className="text-muted text-sm ml-3">
                        {s.summary.total_estimated_cooling_c.toFixed(2)}°C cooling, INR {(s.summary.spent_inr / 1000).toFixed(0)}K spent, {s.summary.cells_affected} cells
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Empty state */}
          {!result && !loading && (
            <div className="bg-surface-card rounded-xl p-12 border border-hairline text-center">
              <Target className="w-12 h-12 text-muted-soft mx-auto mb-4" />
              <p className="text-muted text-lg">Configure budget and run optimization</p>
              <p className="text-muted-soft text-sm mt-2">
                The greedy algorithm sorts all cell+intervention pairs by impact per dollar,
                then selects the best until the budget is exhausted.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon }) {
  return (
    <div className="bg-surface-card rounded-xl p-4 border border-hairline">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-xs text-muted font-medium">{label}</span>
      </div>
      <div className="text-xl font-bold text-ink font-mono">{value}</div>
    </div>
  );
}

function CompareRow({ label, a, b, aVal, bVal }) {
  const winner = aVal > bVal ? 'a' : bVal > aVal ? 'b' : 'tie';
  return (
    <tr className="border-b border-hairline-soft">
      <td className="py-3 px-4 text-body font-medium">{label}</td>
      <td className={`py-3 px-4 text-center font-mono ${winner === 'a' ? 'text-success font-semibold' : 'text-ink'}`}>
        {a}
      </td>
      <td className={`py-3 px-4 text-center font-mono ${winner === 'b' ? 'text-success font-semibold' : 'text-ink'}`}>
        {b}
      </td>
      <td className="py-3 px-4 text-center">
        {winner === 'a' && <span className="text-success font-bold">A</span>}
        {winner === 'b' && <span className="text-primary font-bold">B</span>}
        {winner === 'tie' && <span className="text-muted-soft">=</span>}
      </td>
    </tr>
  );
}
