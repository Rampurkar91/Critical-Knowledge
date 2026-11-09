import { useCallback, useEffect, useState } from 'react';

export function useApiData(fetcher, deps = [], { enabled = true } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState(null);
  const [refreshIndex, setRefreshIndex] = useState(0);

  const refresh = useCallback(() => setRefreshIndex((value) => value + 1), []);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return undefined;
    }
    let active = true;
    setLoading(true);
    setError(null);
    Promise.resolve()
      .then(() => fetcher())
      .then((result) => {
        if (active) setData(result);
      })
      .catch((err) => {
        if (active) setError(err);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, refreshIndex, ...deps]);

  return { data, loading, error, refresh, setData };
}
