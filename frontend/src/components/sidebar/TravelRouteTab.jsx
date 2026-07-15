import React, { useRef } from 'react';
import html2pdf from 'html2pdf.js';
import useTravelStore from '../../stores/useTravelStore';
import { useLangStore } from '../../stores/useLangStore';
import {
  getPlaceDisplayCategory,
  getPlaceDisplaySubCategory,
  getPlaceDisplayRating,
  getPlaceDisplayImage,
} from '../../services/map/placeDisplayAdapter';

const UI_TEXT = {
  ko: {
    title: '내 여행 루트',
    saveBtn: '전체 저장',
    shareBtn: '공유',
    noImage: '이미지 없음',
    deleteRoute: '루트 삭제',
    toastSave: '전체 여행 루트 PDF 다운로드가 시작되었습니다.',
    toastShare: '공유 링크가 클립보드에 복사되었습니다.',
    toastDelete: (name) => `${name}이 루트에서 삭제되었습니다.`,
    noRouteTitle: (day) => `${day}일차는 아직 루트가 없습니다`,
    noRouteDesc: '장소 검색 탭에서 갈 곳들을 추가해보세요!'
  },
  en: {
    title: 'My Travel Route',
    saveBtn: 'Save All',
    shareBtn: 'Share',
    noImage: 'No Image',
    deleteRoute: 'Delete route',
    toastSave: 'Full travel route PDF download has started.',
    toastShare: 'Share link has been copied to clipboard.',
    toastDelete: (name) => `'${name}' has been deleted from the route.`,
    noRouteTitle: (day) => `No route for Day ${day} yet`,
    noRouteDesc: 'Try adding places from the Search tab!'
  }
};

export default function TravelRouteTab({ showToast }) {
  const allDay = useTravelStore((state) => state.all_day);
  const travelPath = useTravelStore((state) => state.travelPath);
  const removePathItem = useTravelStore((state) => state.removePathItem);
  const selectedDay = useTravelStore((state) => state.selectedDay);
  const setSelectedDay = useTravelStore((state) => state.setSelectedDay);

  const lang = useLangStore((state) => state.lang);
  const t = UI_TEXT[lang];

  const days = Array.from({ length: allDay }, (_, i) => i + 1);

  let currentDay = selectedDay;
  if (selectedDay > allDay) {
    currentDay = 1;
    setSelectedDay(1);
  }

  const currentRoute = travelPath[currentDay] || [];

  // [핵심] 외부 이미지 URL을 CORS 우회 가능한 Base64 데이터로 변환하는 함수
  const getBase64ImageFromUrl = async (imageUrl) => {
    try {
      const res = await fetch(imageUrl, { method: 'GET', mode: 'cors' });
      const blob = await res.blob();
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
    } catch (err) {
      // 이미지 호스트 측에서 CORS를 완강하게 막은 경우 폴백 처리
      console.warn("CORS 제한으로 이미지를 불러오지 못했습니다. 원본 URL을 사용합니다.", err);
      return imageUrl;
    }
  };

  // 이미지까지 포함된 전체 일차 통합 HTML 템플릿 생성 함수 (비동기 처리)
  const generateAllDaysPdfTemplate = async () => {
    const container = document.createElement('div');
    container.style.fontFamily = 'Arial, sans-serif';
    container.style.padding = '20px';
    container.style.color = '#334155';
    container.style.backgroundColor = '#ffffff';

    // 메인 헤더
    const mainHeader = document.createElement('div');
    mainHeader.style.borderBottom = '3px double #cbd5e1';
    mainHeader.style.paddingBottom = '16px';
    mainHeader.style.marginBottom = '30px';
    mainHeader.innerHTML = `
      <h1 style="margin: 0; font-size: 28px; color: #0f172a; font-weight: 800; text-align: center;">🗺️ ${t.title}</h1>
      <p style="margin: 6px 0 0 0; font-size: 13px; color: #94a3b8; text-align: center; font-weight: 500;">
        Total Schedule: 1 - ${allDay} Days
      </p>
    `;
    container.appendChild(mainHeader);

    // 각 일차별 순회
    for (let dayIndex = 0; dayIndex < days.length; dayIndex++) {
      const dayNum = days[dayIndex];
      const dayRoute = travelPath[dayNum] || [];

      const daySection = document.createElement('div');
      daySection.style.marginBottom = '40px';

      // 페이지 자동 나눔 처리 (2일차부터 신규 페이지 시작)
      if (dayIndex > 0) {
        daySection.style.pageBreakBefore = 'always';
      }

      const dayHeader = document.createElement('div');
      dayHeader.style.backgroundColor = '#2563eb';
      dayHeader.style.color = '#ffffff';
      dayHeader.style.padding = '8px 18px';
      dayHeader.style.borderRadius = '30px';
      dayHeader.style.fontSize = '15px';
      dayHeader.style.fontWeight = 'bold';
      dayHeader.style.display = 'inline-block';
      dayHeader.style.marginBottom = '20px';
      dayHeader.innerText = `Day ${dayNum}`;
      daySection.appendChild(dayHeader);

      if (dayRoute.length === 0) {
        const emptyMsg = document.createElement('div');
        emptyMsg.style.border = '2px dashed #e2e8f0';
        emptyMsg.style.borderRadius = '12px';
        emptyMsg.style.padding = '30px';
        emptyMsg.style.textAlign = 'center';
        emptyMsg.style.color = '#94a3b8';
        emptyMsg.innerHTML = `
          <p style="margin: 0; font-size: 14px; font-weight: 600;">${t.noRouteTitle(dayNum)}</p>
          <p style="margin: 4px 0 0 0; font-size: 12px; color: #cbd5e1;">${t.noRouteDesc}</p>
        `;
        daySection.appendChild(emptyMsg);
      } else {
        // 일차 내 장소 순회 (Base64 변환을 위해 for-of 루프 사용)
        for (let index = 0; index < dayRoute.length; index++) {
          const place = dayRoute[index];
          const category = getPlaceDisplayCategory(place);
          const subCategory = getPlaceDisplaySubCategory(place);
          const rating = getPlaceDisplayRating(place);
          const originalImage = getPlaceDisplayImage(place);

          // 이미지 Base64 사전 변환 작업 진행
          let safeImageSrc = null;
          if (originalImage) {
            safeImageSrc = await getBase64ImageFromUrl(originalImage);
          }

          let badgeColor = '#ef4444';
          let badgeBg = '#fef2f2';
          if (category === '카페') { badgeColor = '#f97316'; badgeBg = '#fff7ed'; }
          else if (category === '맛집') { badgeColor = '#22c55e'; badgeBg = '#f0fdf4'; }
          else if (category === '숙소') { badgeColor = '#a855f7'; badgeBg = '#faf5ff'; }
          else if (category === '보관소') { badgeColor = '#06b6d4'; badgeBg = '#ecfeff'; }

          const card = document.createElement('div');
          card.style.border = '1px solid #e2e8f0';
          card.style.borderRadius = '12px';
          card.style.padding = '16px';
          card.style.marginBottom = '14px';
          card.style.backgroundColor = '#ffffff';
          card.style.pageBreakInside = 'avoid';

          card.innerHTML = `
            <div style="display: flex; align-items: flex-start; gap: 16px;">
              <!-- 왼쪽: 순서 번호 & 썸네일 이미지 영역 -->
              <div style="display: flex; align-items: center; gap: 12px; flex-shrink: 0;">
                <div style="display: flex; width: 28px; height: 28px; flex-shrink: 0; align-items: center; justify-content: center; border-radius: 50%; background-color: #2563eb; color: #ffffff; font-weight: bold; font-size: 14px;">
                  ${index + 1}
                </div>
                <!-- 안전한 Base64 또는 원본 이미지를 받아와 바인딩 -->
                <div style="display: flex; width: 64px; height: 64px; flex-shrink: 0; align-items: center; justify-content: center; overflow: hidden; border-radius: 8px; border: 1px solid #f1f5f9; background-color: #f8fafc;">
                  ${safeImageSrc ? `
                    <img src="${safeImageSrc}" alt="${place.name}" style="height: 100%; width: 100%; object-fit: cover;" />
                  ` : `
                    <span style="font-size: 11px; font-weight: 600; color: #94a3b8;">${t.noImage}</span>
                  `}
                </div>
              </div>

              <!-- 오른쪽: 텍스트 정보 -->
              <div style="flex: 1; min-width: 0;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                  <h3 style="margin: 0; font-size: 16px; font-weight: bold; color: #1e293b;">${place.name}</h3>
                  <span style="font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; color: ${badgeColor}; background-color: ${badgeBg};">
                    ${subCategory}
                  </span>
                </div>
                <p style="margin: 0 0 4px 0; font-size: 13px; color: #64748b;">${place.address}</p>
                <p style="margin: 0; font-size: 13px; color: #f59e0b; font-weight: bold;">★ ${rating}</p>
              </div>
            </div>
            <!-- 추천 이유 -->
            ${place.selectionReason ? `
              <div style="margin-top: 12px; padding: 10px 14px; background-color: #f8fafc; border: 1px solid #f1f5f9; border-radius: 8px; font-size: 13px; color: #475569; line-height: 1.5;">
                💡 ${place.selectionReason}
              </div>
            ` : ''}
          `;
          daySection.appendChild(card);
        }
      }

      container.appendChild(daySection);
    }

    return container;
  };

  // 비동기로 작동하도록 async 선언
  const handleSavePDF = async () => {
    showToast(t.toastSave);

    // 1. 이미지 변환(Base64) 로직이 완료될 때까지 비동기 대기
    const element = await generateAllDaysPdfTemplate();

    const options = {
      margin: [20, 15, 20, 15],
      filename: `Travel_Route_Full_Days.pdf`,
      image: { type: 'jpeg', quality: 0.98 },
      html2canvas: {
        scale: 2,
        useCORS: true, // CORS 허용 옵션도 유지
        logging: false
      },
      jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
    };

    // 2. 가상의 DOM 엘리먼트를 타겟으로 삼아 PDF 최종 변환 후 저장
    html2pdf().set(options).from(element).save();
  };

  return (
      <div className="flex-1 flex flex-col min-h-0 p-5 space-y-6">
        {/* 상단 타이틀 및 버튼 영역 */}
        <div className="flex items-center justify-between shrink-0">
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
            {t.title}
          </h2>
          <div className="flex gap-2">
            <button
                type="button"
                onClick={handleSavePDF}
                className="flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-all shadow-sm"
            >
              {t.saveBtn}
            </button>
            <button
                type="button"
                onClick={() => showToast(t.toastShare)}
                className="flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-all shadow-sm"
            >
              {t.shareBtn}
            </button>
          </div>
        </div>

        {/* Day 선택 Chip 영역 */}
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          {days.map((d) => (
              <button
                  key={d}
                  type="button"
                  onClick={() => setSelectedDay(d)}
                  className={`rounded-full px-5 py-2.5 text-sm font-semibold transition-all shadow-sm ${
                      currentDay === d
                          ? 'bg-blue-600 text-white border border-blue-600'
                          : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                  }`}
              >
                Day {d}
              </button>
          ))}
        </div>

        {/* 루트 리스트 영역 */}
        <div className="flex-1 overflow-y-auto space-y-4 min-h-0 pr-1">
          {currentRoute.length > 0 ? (
              currentRoute.map((place, index) => {
                const category = getPlaceDisplayCategory(place);
                const subCategory = getPlaceDisplaySubCategory(place);
                const rating = getPlaceDisplayRating(place);
                const image = getPlaceDisplayImage(place);

                return (
                    <article
                        key={place.id}
                        className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:border-slate-300 transition-all duration-200 relative"
                    >
                      {/* [상단 영역] 번호 + 이미지 + 텍스트 정보 */}
                      <div className="flex items-start gap-4">
                        <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white shadow-sm">
                          {index + 1}
                        </div>

                        <div className="flex size-16 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-100 bg-slate-50">
                          {image ? (
                              <img
                                  src={image}
                                  alt={place.name}
                                  className="h-full w-full object-cover"
                              />
                          ) : (
                              <span className="text-xs font-semibold text-slate-400">
                                {t.noImage}
                              </span>
                          )}
                        </div>

                        <div className="flex-1 min-w-0 pr-8 space-y-1">
                          <div className="flex items-center gap-2">
                            <h3 className="font-bold text-slate-800 text-lg leading-snug truncate">
                              {place.name}
                            </h3>
                            <span
                                className={`text-[10px] font-bold px-1.5 py-0.5 rounded whitespace-nowrap shrink-0 ${
                                    category === '카페'
                                        ? 'text-orange-500 bg-orange-50'
                                        : category === '맛집'
                                            ? 'text-green-500 bg-green-50'
                                            : category === '숙소'
                                                ? 'text-purple-500 bg-purple-50'
                                                : category === '보관소'
                                                    ? 'text-cyan-500 bg-cyan-50'
                                                    : 'text-red-500 bg-red-50'
                                }`}
                            >
                              {subCategory}
                            </span>
                          </div>

                          <p className="text-sm text-slate-400 break-keep">
                            {place.address}
                          </p>

                          <p className="text-sm text-amber-500 font-semibold flex items-center gap-1 mt-0.5">
                            ★ {rating}
                          </p>
                        </div>
                      </div>

                      {/* [하단 전체 영역] 추천 이유 박스 */}
                      {place.selectionReason && (
                          <div className="rounded-xl bg-slate-50 p-3.5 border border-slate-100 relative mt-1 mx-1">
                            <div
                                className="absolute top-0 left-[116px] -translate-y-[11px] w-4 h-3 bg-slate-50 border-t border-l border-slate-100"
                                style={{
                                  clipPath: 'polygon(50% 0%, 0% 100%, 100% 100%)',
                                }}
                            />
                            <p className="text-[13px] text-slate-600 leading-relaxed font-normal whitespace-pre-wrap break-keep relative z-10">
                              💡 {place.selectionReason}
                            </p>
                          </div>
                      )}

                      {/* [우측 상단] X자 삭제 버튼 */}
                      <div className="absolute top-4 right-4 z-10">
                        <button
                            type="button"
                            onClick={() => {
                              const targetDay = Number(currentDay);
                              removePathItem(targetDay, place.id);
                              showToast(t.toastDelete(place.name));
                            }}
                            className="rounded-full p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 active:bg-slate-200 transition-colors"
                            title={t.deleteRoute}
                        >
                          <svg className="size-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    </article>
                );
              })
          ) : (
              <div className="flex flex-col items-center justify-center py-12 text-center border-2 border-dashed border-slate-100 rounded-2xl">
                <span className="text-3xl mb-2">📍</span>
                <p className="text-sm font-semibold text-slate-700">
                  {t.noRouteTitle(currentDay)}
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  {t.noRouteDesc}
                </p>
              </div>
          )}
        </div>
      </div>
  );
}