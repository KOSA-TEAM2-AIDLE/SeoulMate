import { create } from 'zustand';

const useTravelStore = create((set) => ({
    recommendList: [],
    travelPath: {},
    accommodation: null,
    selectedDay: 1,
    all_day: 1,
    allPlaces : [],

    setRecommendList: (newList) => set({ recommendList: newList }),
    setSelectedDay: (newSelectedDay) => set({ selectedDay: newSelectedDay }),
    setAllDay: (newDay) => set({ all_day: newDay }),
    setTravelPath: (newPath) => set({ travelPath: newPath }),
    setAccommodation: (place) => set({ accommodation: place }),
    setAllPlaces: (places) => set({allPlaces: places}),

    selectedPlace: null,
    setSelectedPlace: (place) => set({ selectedPlace: place }),
    clearSelectedPlace: () => set({ selectedPlace: null }),

    addPathItem: (item) => {
        let isAdded = false;

        set((state) => {
            const currentDay = state.selectedDay;
            const currentDayPath = state.travelPath[currentDay] || [];
            const alreadyExists = currentDayPath.some((p) => p.id === item.id);

            if (alreadyExists) {
                isAdded = false;
                return state;
            }

            isAdded = true;
            return {
                travelPath: {
                    ...state.travelPath,
                    [currentDay]: [...currentDayPath, item]
                }
            };
        });

        return isAdded;
    },

    removePathItem: (itemKey) =>
        set((state) => {
            const currentDay = state.selectedDay;
            return {
                travelPath: {
                    ...state.travelPath,
                    [currentDay]: (state.travelPath[currentDay] || []).filter(
                        (item) => (item.slotId ?? item.id) !== itemKey
                    )
                }
            };
        }),

    cycleRouteCandidate: (itemKey) =>
        set((state) => {
            const currentDay = state.selectedDay;
            const currentDayPath = state.travelPath[currentDay] || [];
            return {
                travelPath: {
                    ...state.travelPath,
                    [currentDay]: currentDayPath.map((item) => {
                        if ((item.slotId ?? item.id) !== itemKey) {
                            return item;
                        }
                        const choices = item.rotationChoices || [item, ...(item.alternatives || [])];
                        if (choices.length < 2) return item;
                        const nextIndex = ((item.rotationIndex || 0) + 1) % choices.length;
                        const next = choices[nextIndex];
                        return {
                            ...next,
                            slotId: item.slotId,
                            time: item.time,
                            alternatives: item.alternatives,
                            rotationChoices: choices,
                            rotationIndex: nextIndex,
                        };
                    }),
                },
            };
        }),

    cycleAccommodationCandidate: () =>
        set((state) => {
            const item = state.accommodation;
            if (!item) return state;
            const choices = item.rotationChoices || [item, ...(item.alternatives || [])];
            if (choices.length < 2) return state;
            const nextIndex = ((item.rotationIndex || 0) + 1) % choices.length;
            const next = choices[nextIndex];
            return {
                accommodation: {
                    ...next,
                    alternatives: item.alternatives,
                    rotationChoices: choices,
                    rotationIndex: nextIndex,
                },
            };
        }),

    clearAccommodation: () => set({ accommodation: null }),

    clearTravelPath: () => set({ travelPath: {}, accommodation: null }),
}));

export default useTravelStore;
