const API_BASE = import.meta.env.VITE_API_URL || '/api';

// City is stored in localStorage for persistence across page reloads
// and passed as parameter to avoid module-level mutable state race conditions
export function setCity(cityKey) {
  localStorage.setItem('urbancity_current_city', cityKey);
}

export function getCity() {
  return localStorage.getItem('urbancity_current_city') || 'ahmedabad';
}

function cityParam() {
  return `city=${getCity()}`;
}

export async function fetchCities() {
  const res = await fetch(`${API_BASE}/cities`);
  if (!res.ok) throw new Error('Failed to fetch cities');
  return res.json();
}

export async function fetchCells() {
  const res = await fetch(`${API_BASE}/cells?${cityParam()}`);
  if (!res.ok) throw new Error('Failed to fetch cells');
  return res.json();
}

export async function fetchCell(cellId) {
  const res = await fetch(`${API_BASE}/cells/${cellId}?${cityParam()}`);
  if (!res.ok) throw new Error('Failed to fetch cell');
  return res.json();
}

export async function fetchCellDrivers(cellId) {
  const res = await fetch(`${API_BASE}/cells/${cellId}/drivers?${cityParam()}`);
  if (!res.ok) throw new Error('Failed to fetch drivers');
  return res.json();
}

export async function fetchGlobalDrivers() {
  const res = await fetch(`${API_BASE}/drivers/global?${cityParam()}`);
  if (!res.ok) throw new Error('Failed to fetch global drivers');
  return res.json();
}

export async function fetchHotspots(limit = 20) {
  const res = await fetch(`${API_BASE}/hotspots?limit=${limit}&${cityParam()}`);
  if (!res.ok) throw new Error('Failed to fetch hotspots');
  return res.json();
}

export async function fetchDashboard() {
  const res = await fetch(`${API_BASE}/dashboard?${cityParam()}`);
  if (!res.ok) throw new Error('Failed to fetch dashboard');
  return res.json();
}

export async function simulateIntervention(cellId, params) {
  const res = await fetch(`${API_BASE}/simulate?${cityParam()}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cell_id: cellId, ...params }),
  });
  if (!res.ok) throw new Error('Simulation failed');
  return res.json();
}

export async function fetchPriorityRankings(sortBy = 'score') {
  const res = await fetch(`${API_BASE}/priority?sort_by=${sortBy}&${cityParam()}`);
  if (!res.ok) throw new Error('Failed to fetch priority rankings');
  return res.json();
}

export async function fetchTopPriority(n = 10) {
  const res = await fetch(`${API_BASE}/priority/top?n=${n}&${cityParam()}`);
  if (!res.ok) throw new Error('Failed to fetch top priority');
  return res.json();
}

export async function fetchDataInfo() {
  const res = await fetch(`${API_BASE}/data-info?${cityParam()}`);
  if (!res.ok) throw new Error('Failed to fetch data info');
  return res.json();
}

export async function fetchValidation() {
  const res = await fetch(`${API_BASE}/validation?${cityParam()}`);
  if (!res.ok) throw new Error('Failed to fetch validation');
  return res.json();
}

export async function runOptimization(params) {
  const res = await fetch(`${API_BASE}/optimize?${cityParam()}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error('Optimization failed');
  return res.json();
}

export async function compareScenarios(scenarioA, scenarioB) {
  const res = await fetch(`${API_BASE}/scenarios/compare?${cityParam()}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario_a: scenarioA, scenario_b: scenarioB }),
  });
  if (!res.ok) throw new Error('Scenario comparison failed');
  return res.json();
}
