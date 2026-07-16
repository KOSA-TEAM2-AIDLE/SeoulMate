import { create } from 'zustand';

const useTravelStore = create((set) => ({
    recommendList: [],
    travelPath: {},
    selectedDay: 1,
    all_day: 1,
    allPlaces : [],

    setRecommendList: (newList) => set({ recommendList: newList }),
    setSelectedDay: (newSelectedDay) => set({ selectedDay: newSelectedDay }),
    setAllDay: (newDay) => set({ all_day: newDay }),
    setTravelPath: (newPath) => set({ travelPath: newPath }),
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

    removePathItem: (itemId) =>
        set((state) => {
            const currentDay = state.selectedDay;
            return {
                travelPath: {
                    ...state.travelPath,
                    [currentDay]: (state.travelPath[currentDay] || []).filter((item) => item.id !== itemId)
                }
            };
        }),

    clearTravelPath: () => set({ travelPath: {} }),
}));

export default useTravelStore;