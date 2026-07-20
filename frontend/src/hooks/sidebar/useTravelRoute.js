import { useEffect } from 'react';
import useTravelStore from '../../stores/useTravelStore';
import { useLangStore } from '../../stores/useLangStore';
import usePdfGenerator from './usePdfGenerator';

const UI_TEXT = {
    ko: {
        title: '내 여행 루트',
        saveBtn: '전체 저장',
        shareBtn: 'PDF 공유',
        noImage: '이미지 없음',
        deleteRoute: '루트 삭제',
        toastSave: '전체 여행 루트 PDF 다운로드가 시작되었습니다.',
        toastShare: '공유 창을 열고 있습니다...',
        toastShareSuccess: '공유 창을 열었습니다.',
        toastShareFallback: '파일 공유가 지원되지 않아 PDF 다운로드로 대체합니다.',
        toastDelete: (name) => `${name}이 루트에서 삭제되었습니다.`,
        noRouteTitle: (day) => `${day}일차는 아직 루트가 없습니다`,
        noRouteDesc: '장소 검색 탭에서 갈 곳들을 추가해보세요!',
        changeCandidate: '변경',
        reviewButton: '리뷰',
        moreInfo: '바로가기',
        travelerReviews: '리뷰',
        bookingLink: '예약',
        accommodation: '숙소'
    },
    en: {
        title: 'My Travel Route',
        saveBtn: 'Save All',
        shareBtn: 'Share PDF',
        noImage: 'No Image',
        deleteRoute: 'Delete route',
        toastSave: 'Full travel route PDF download has started.',
        toastShare: 'Opening share menu...',
        toastShareSuccess: 'Opened share menu.',
        toastShareFallback: 'File sharing not supported. Falling back to PDF download.',
        toastDelete: (name) => `'${name}' has been deleted from the route.`,
        noRouteTitle: (day) => `No route for Day ${day} yet`,
        noRouteDesc: 'Try adding places from the Search tab!',
        changeCandidate: 'Change',
        reviewButton: 'Reviews',
        moreInfo: 'Link',
        travelerReviews: 'Traveler reviews',
        bookingLink: 'Book',
        accommodation: 'Accommodation'
    }
};

export default function useTravelRoute(showToast) {
    const allDay = useTravelStore((state) => state.all_day);
    const travelPath = useTravelStore((state) => state.travelPath);
    const accommodation = useTravelStore((state) => state.accommodation);
    const removePathItem = useTravelStore((state) => state.removePathItem);
    const cycleRouteCandidate = useTravelStore((state) => state.cycleRouteCandidate);
    const cycleAccommodationCandidate = useTravelStore((state) => state.cycleAccommodationCandidate);
    const clearAccommodation = useTravelStore((state) => state.clearAccommodation);
    const selectedDay = useTravelStore((state) => state.selectedDay);
    const setSelectedDayStore = useTravelStore((state) => state.setSelectedDay);
    const clearSelectedPlace = useTravelStore((state) => state.clearSelectedPlace);

    const setSelectedDay = (day) => {
        setSelectedDayStore(day);
        clearSelectedPlace();
    };

    const lang = useLangStore((state) => state.lang);
    const t = UI_TEXT[lang] || UI_TEXT.ko;

    const days = Array.from({ length: allDay }, (_, i) => i + 1);

    useEffect(() => {
        if (selectedDay > allDay) {
            setSelectedDayStore(1);
        }
    }, [selectedDay, allDay, setSelectedDayStore]);

    const currentDay = selectedDay > allDay ? 1 : selectedDay;
    const currentRoute = travelPath[currentDay] || [];
    const currentAccommodation = currentDay < allDay ? accommodation : null;

    const { savePDF, sharePDF } = usePdfGenerator(t);

    const handleDeleteItem = (place) => {
        removePathItem(place.slotId ?? place.id);
        showToast(t.toastDelete(place.name));
    };

    const handleCycleCandidate = (place) => {
        cycleRouteCandidate(place.slotId ?? place.id);
    };

    const handleDeleteAccommodation = () => {
        if (!accommodation) return;
        clearAccommodation();
        showToast(t.toastDelete(accommodation.name));
    };

    const handleSavePDF = () => savePDF(showToast);
    const handleSharePDF = () => sharePDF(showToast);

    return {
        t,
        days,
        currentDay,
        currentRoute,
        currentAccommodation,
        setSelectedDay,
        handleDeleteItem,
        handleCycleCandidate,
        handleCycleAccommodation: cycleAccommodationCandidate,
        handleDeleteAccommodation,
        handleSavePDF,
        handleSharePDF
    };
}
