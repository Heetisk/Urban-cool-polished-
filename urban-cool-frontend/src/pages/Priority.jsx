import { useState, useEffect } from 'react';
import { AlertTriangle, Shield, Eye, ChevronDown, ChevronUp } from 'lucide-react';
import { fetchPriorityRankings } from '../api';
import { useCity } from '../context/CityContext';

const RISK_COLORS = {
  critical: { bg: 'bg-red-50', text: 'text-error', border: 'border-red-200', dot: 'bg-error' },
  high: { bg: 'bg-orange-50', text: 'text-accent-amber', border: 'border-orange-200', dot: 'bg-accent-amber' },
  moderate: { bg: 'bg-yellow-50', text: 'text-warning', border: 'border-yellow-200', dot: 'bg-warning' },
  low: { bg: 'bg-green-50', text: 'text-success', border: 'border-green-200', dot: 'bg-success' },
};

export default function Priority() {
  const { currentCity } = useCity();
  const [rankings, setRankings] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [sortBy, setSortBy] = useState('temperature');
  const [expandedRow, setExpandedRow] = useState(null);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (!currentCity) return;
    setLoading(true);
    fetchPriorityRankings(sortBy)
      .then((data) => {
        setRankings(data.rankings);
        setSummary(data.summary);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [sortBy, currentCity, currentCity?.key]);

  const filtered = filter === 'all'
    ? rankings
    : rankings.filter((r) => r.risk_level === filter);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full w-full">
        <div className="text-muted text-lg font-serif">Loading priority rankings...</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-6 pt-20 md:pt-24">
      <h1 className="text-[36px] font-serif font-normal text-ink tracking-tight mb-2">Priority Ranking</h1>
      <p className="text-muted mb-8">Where authorities should act first</p>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <SummaryCard
            label="Critical"
            value={summary.critical_zones}
            color="bg-red-500"
            icon={<AlertTriangle className="w-4 h-4 text-red-500" />}
          />
          <SummaryCard
            label="High"
            value={summary.high_priority_zones}
            color="bg-orange-500"
            icon={<Shield className="w-4 h-4 text-orange-500" />}
          />
          <SummaryCard
            label="Moderate"
            value={summary.moderate_zones}
            color="bg-yellow-500"
            icon={<Eye className="w-4 h-4 text-yellow-500" />}
          />
          <SummaryCard
            label="Low"
            value={summary.low_priority_zones}
            color="bg-green-500"
            icon={<Eye className="w-4 h-4 text-green-500" />}
          />
        </div>
      )}

      <div className="flex flex-col md:flex-row md:items-center gap-3 md:gap-4 mb-6">
        <div className="flex flex-wrap gap-2">
          {['all', 'critical', 'high', 'moderate', 'low'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer capitalize ${
                filter === f
                  ? 'bg-primary text-on-primary'
                  : 'bg-surface-card text-muted border border-hairline hover:bg-surface-soft'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2 md:ml-auto">
          <button
            onClick={() => setSortBy('temperature')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
              sortBy === 'temperature'
                ? 'bg-error text-on-primary'
                : 'bg-surface-card text-muted border border-hairline hover:bg-surface-soft'
            }`}
          >
            Sort by Temp
          </button>
          <button
            onClick={() => setSortBy('score')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
              sortBy === 'score'
                ? 'bg-error text-on-primary'
                : 'bg-surface-card text-muted border border-hairline hover:bg-surface-soft'
            }`}
          >
            Sort by Score
          </button>
        </div>
      </div>

      <div className="bg-surface-card rounded-xl border border-hairline overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-surface-soft border-b border-hairline">
                <th className="text-left px-6 py-3 text-xs font-semibold text-muted uppercase tracking-wider">Rank</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-muted uppercase tracking-wider">Zone</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-muted uppercase tracking-wider">Temp</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-muted uppercase tracking-wider">NDVI</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-muted uppercase tracking-wider">Risk</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-muted uppercase tracking-wider">Score</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-muted uppercase tracking-wider">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline-soft">
              {filtered.map((r) => {
                const colors = RISK_COLORS[r.risk_level];
                const isExpanded = expandedRow === r.cell_id;
                return (
                  <tr
                    key={r.cell_id}
                    className="hover:bg-surface-soft cursor-pointer transition-colors border-b border-hairline-soft"
                    onClick={() => setExpandedRow(isExpanded ? null : r.cell_id)}
                  >
                    <td className="px-6 py-4 text-sm font-mono font-bold text-ink">#{r.rank}</td>
                    <td className="px-6 py-4">
                      <div className="text-sm font-medium text-ink">{r.cell_id}</div>
                      <div className="text-xs text-muted-soft">{r.lat?.toFixed(4)}, {r.lon?.toFixed(4)}</div>
                    </td>
                    <td className="px-6 py-4 text-sm font-mono text-body">{r.air_temperature_celsius || r.temperature}C</td>
                    <td className="px-6 py-4 text-sm font-mono text-body">{r.ndvi?.toFixed(3) || '-'}</td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${colors.bg} ${colors.text} ${colors.border} border`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${colors.dot}`}></span>
                        {r.risk_level}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-surface-cream-strong rounded-full h-2">
                          <div
                            className={`h-2 rounded-full ${
                              r.risk_level === 'critical' ? 'bg-error' :
                              r.risk_level === 'high' ? 'bg-accent-amber' :
                              r.risk_level === 'moderate' ? 'bg-warning' : 'bg-success'
                            }`}
                            style={{ width: `${r.priority_score * 100}%` }}
                          />
                        </div>
                        <span className="text-xs font-mono text-muted">{r.priority_score}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-muted max-w-[200px] truncate">{r.recommendation}</span>
                        {isExpanded ? <ChevronUp className="w-3 h-3 text-muted-soft" /> : <ChevronDown className="w-3 h-3 text-muted-soft" />}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ label, value, color, icon }) {
  return (
    <div className="bg-surface-card rounded-xl border border-hairline p-5">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${color}/10`}>{icon}</div>
        <div>
          <p className="text-xs text-muted">{label}</p>
          <p className="text-2xl font-bold text-ink font-mono">{value}</p>
        </div>
      </div>
    </div>
  );
}
