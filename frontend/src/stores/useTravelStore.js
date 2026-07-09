import { create } from 'zustand';

const useTravelStore = create((set) => ({
    recommendList: [],
    travelPath: {},
    day: 1,
    all_day: 1,
    allPlaces : [],

    setRecommendList: (newList) => set({ recommendList: newList }),
    setDay: (newDay) => set({ day: newDay }),
    setAllDay: (newDay) => set({ all_day: newDay }),
    
    setAllPlaces: (places) => set({allPlaces: places}),

    selectedPlace: null,
    setSelectedPlace: (place) => set({ selectedPlace: place }),
    clearSelectedPlace: () => set({ selectedPlace: null }),

    addPathItem: (day, item) => {
        let isAdded = false;

        set((state) => {
            const currentDayPath = state.travelPath[day] || [];

            const alreadyExists = currentDayPath.some((p) => p.id === item.id);

            if (alreadyExists) {
                isAdded = false;
                return state;
            }

            isAdded = true;
            return {
                travelPath: {
                    ...state.travelPath,
                    [day]: [...currentDayPath, item]
                }
            };
        });

        return isAdded;
    },

    removePathItem: (day, itemId) =>
        set((state) => ({
            travelPath: {
                ...state.travelPath,
                [day]: (state.travelPath[day] || []).filter((item) => item.id !== itemId)
            }
        })),

    clearTravelPath: () => set({ travelPath: {} }),
}));

export default useTravelStore;