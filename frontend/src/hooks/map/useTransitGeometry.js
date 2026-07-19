import { useEffect, useState } from 'react';
import { fetchTransitGeometry } from '../../api/transitRoutes';

export function useTransitGeometry(segment) {
  const [geometry, setGeometry] = useState(null);
  useEffect(() => {
    if (!segment?.route?.map_object) { setGeometry(null); return; }
    let alive = true;
    fetchTransitGeometry(segment.route.map_object).then((result) => { if (alive) setGeometry(result); }).catch(() => { if (alive) setGeometry(null); });
    return () => { alive = false; };
  }, [segment]);
  return geometry;
}
