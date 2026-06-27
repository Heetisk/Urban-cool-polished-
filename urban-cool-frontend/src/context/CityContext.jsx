import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { setCity } from '../api';

const CityContext = createContext(null);

const API_BASE = import.meta.env.VITE_API_URL || '/api';

export function CityProvider({ children }) {
  const [cities, setCities] = useState([]);
  const [currentCity, setCurrentCity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchCitiesRef = useRef(null);

  const fetchCities = useCallback(async (retryCount = 0) => {
    const MAX_RETRIES = 3;
    const RETRY_DELAY = 1000;
    try {
      const res = await fetch(`${API_BASE}/cities`);
      if (!res.ok) throw new Error(`API returned ${res.status}`);
      const data = await res.json();
      setCities(data);
      setError(null);
      const withData = data.find((c) => c.has_data);
      if (withData) {
        setCurrentCity(withData);
        setCity(withData.key);
      } else if (data.length > 0) {
        setCurrentCity(data[0]);
        setCity(data[0].key);
      }
    } catch (err) {
      console.error(err);
      if (retryCount < MAX_RETRIES) {
        setTimeout(() => fetchCitiesRef.current?.(retryCount + 1), RETRY_DELAY * (retryCount + 1));
        return;
      }
      setError('Failed to connect to backend. Make sure the server is running.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCitiesRef.current = fetchCities;
  }, [fetchCities]);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    fetchCities();
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [fetchCities]);

  const switchCity = useCallback((cityKey) => {
    const city = cities.find((c) => c.key === cityKey);
    if (city) {
      setCurrentCity(city);
      setCity(cityKey);
    }
  }, [cities]);

  const retry = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchCities();
  }, [fetchCities]);

  return (
    <CityContext.Provider value={{ cities, currentCity, switchCity, loading, error, retry }}>
      {children}
    </CityContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useCity() {
  const context = useContext(CityContext);
  if (!context) {
    throw new Error('useCity must be used within a CityProvider');
  }
  return context;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useCityKey() {
  const { currentCity, loading } = useCity();
  if (!loading && !currentCity) {
    throw new Error('No city available — check API connection');
  }
  return currentCity?.key;
}
