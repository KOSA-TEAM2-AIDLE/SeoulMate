import { create } from 'zustand';

const mockRecommendList = [
    { id: "ACCO001", name: "파크 하얏트 서울", category: "숙소", subCategory: "럭셔리", address: "서울 강남구 테헤란로 606", rating: "4.7", reviews: "1,842", time: "15:00 (체크인)", image: "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=150&q=80" },
    { id: "ACCO002", name: "롯데호텔 서울", category: "숙소", subCategory: "럭셔리", address: "서울 중구 을지로 30", rating: "4.6", reviews: "3,124", time: "15:00 (체크인)", image: "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=150&q=80" },
    { id: "CAFE002", name: "블루보틀 삼청", category: "카페", subCategory: "스페셜티 커피", address: "서울 종로구 삼청로 87", rating: "4.5", reviews: "120", time: "14:00 - 15:00", image: "https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&w=150&q=80" },
    { id: "CAFE003", name: "어니언 성수", category: "카페", subCategory: "베이커리 카페", address: "서울 성동구 아차산로9길 8", rating: "4.7", reviews: "1,450", time: "16:30 - 17:30", image: "https://images.unsplash.com/photo-1498804103079-a6351b050096?auto=format&fit=crop&w=150&q=80" },
    { id: "EVT006", name: "경복궁 야간개장", category: "명소", subCategory: "궁궐/야간", address: "서울 종로구 사직로 161", rating: "4.9", reviews: "2,840", time: "19:30 - 21:00", image: "https://images.unsplash.com/photo-1578469550956-0e16b69c6a3d?auto=format&fit=crop&w=150&q=80" },
    { id: "REST002", name: "광장시장 박가네 빈대떡", category: "맛집", subCategory: "한식/분식", address: "서울 종로구 창경궁로 88", rating: "4.6", reviews: "934", time: "12:00 - 13:00", image: "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=150&q=80" },
    { id: "LOCKER003", name: "경복궁역 물품보관소", category: "보관소", subCategory: "지하철역 내", address: "서울 종로구 사직로 130", rating: "4.4", reviews: "45", time: "09:00 (짐 보관)", image: "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=150&q=80" }
];

const useTravelStore = create((set) => ({
    recommendList: mockRecommendList,
    travelPath: {
        1: [mockRecommendList[6], mockRecommendList[4], mockRecommendList[2]],
        2: [mockRecommendList[5], mockRecommendList[3]],
        3: [mockRecommendList[0]],
    },

    setRecommendList: (newList) => set({ recommendList: newList }),

    addPathItem: (day, item) =>
        set((state) => ({
            travelPath: {
                ...state.travelPath,
                [day]: [...(state.travelPath[day] || []), item]
            }
        })),

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