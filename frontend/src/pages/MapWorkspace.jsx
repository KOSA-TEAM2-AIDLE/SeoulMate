import { useCallback, useEffect, useMemo, useState } from 'react';
import NaverMap from '../components/map/NaverMap';
import LocationStatus from '../components/location/LocationStatus';
import useTravelStore from '../stores/useTravelStore';
import { useLangStore } from '../stores/useLangStore';
import { useTransitRoutes } from '../hooks/map/useTransitRoutes';
import TransitRouteCard from '../components/map/TransitRouteCard';
import RouteSegmentNavigator from '../components/map/RouteSegmentNavigator';
import { useTransitGeometry } from '../hooks/map/useTransitGeometry';
import { extractGeometryPaths } from '../services/map/transitGeometryService';

export default function MapWorkspace() {
    const selectedDay = useTravelStore((state) => state.selectedDay);
    const travelPath = useTravelStore((state) => state.travelPath);
    const accommodation = useTravelStore((state) => state.accommodation);
    const allDay = useTravelStore((state) => state.all_day);

    const routePlaces = useMemo(() => {
        const places = travelPath[selectedDay] ?? [];
        return (selectedDay < allDay && accommodation) ? [...places, accommodation] : places;
    }, [travelPath, selectedDay, accommodation, allDay]);
    const routeKey = routePlaces.map((place) => `${place.id}:${place.lat}:${place.lng}`).join('|');
    const language = useLangStore((state) => state.lang);
    const segments = useTransitRoutes(routePlaces, language);
    const [selectedSegment, setSelectedSegment] = useState(null);
    useEffect(() => setSelectedSegment(null), [selectedDay, routeKey]);
    const activeSegment = selectedSegment ?? segments[0] ?? null;
    const transitGeometry = useTransitGeometry(activeSegment);
    const activeSegmentIndex = activeSegment ? segments.indexOf(activeSegment) : -1;
    const hasTransitGeometry = extractGeometryPaths(transitGeometry).length > 0;
    const hiddenSegmentIndex = hasTransitGeometry && activeSegment?.route?.mode === 'transit' ? activeSegmentIndex : null;
    const handleSegmentSelect = useCallback((index) => setSelectedSegment(segments[index] ?? null), [segments]);

    return (
        <section className="relative min-h-[460px] overflow-hidden bg-blue-50">
            {/* NAVER SDK applies its base-map language when a map instance is created. */}
            <NaverMap key={`naver-map-${language}`} places={routePlaces} segments={segments} selectedSegment={activeSegment} selectedSegmentIndex={activeSegmentIndex} hiddenSegmentIndex={hiddenSegmentIndex} language={language} transitGeometry={transitGeometry} onSegmentSelect={handleSegmentSelect} />
            <LocationStatus />
            <RouteSegmentNavigator places={routePlaces} activeIndex={activeSegmentIndex} language={language} onSelect={handleSegmentSelect} />
            <TransitRouteCard segment={activeSegment} />
        </section>
    );
}
