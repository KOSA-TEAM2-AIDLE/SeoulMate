export function getRouteSegmentNavigationItems(places = []) {
  return places.slice(0, -1).map((place, index) => ({
    index,
    label: `${place.name} → ${places[index + 1].name}`,
    description: `${place.name} → ${places[index + 1].name}`,
  }));
}

export function getRouteViewportPlaces(places = [], selectedSegment, isSegmentSelected = false) {
  if (isSegmentSelected && selectedSegment) {
    return [selectedSegment.origin, selectedSegment.destination].filter(Boolean);
  }

  return places;
}
