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
    moreInfo: '바로가기' // 링크 다국어 추가
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
    moreInfo: 'Link' // 링크 다국어 추가
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
      console.warn("CORS 제한으로 이미지를 불러오지 못했습니다. 원본 URL을 사용합니다.", err);
      return imageUrl;
    }
  };

  const generateAllDaysPdfTemplate = async () => {
    const container = document.createElement('div');
    container.style.fontFamily = 'Arial, sans-serif';
    container.style.padding = '20px';
    container.style.color = '#334155';
    container.style.backgroundColor = '#ffffff';

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

    for (let dayIndex = 0; dayIndex < days.length; dayIndex++) {
      const dayNum = days[dayIndex];
      const dayRoute = travelPath[dayNum] || [];

      const daySection = document.createElement('div');
      daySection.style.marginBottom = '40px';

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
        for (let index = 0; index < dayRoute.length; index++) {
          const place = dayRoute[index];
          const category = getPlaceDisplayCategory(place);
          const subCategory = getPlaceDisplaySubCategory(place);
          const rating = getPlaceDisplayRating(place);
          const originalImage = getPlaceDisplayImage(place);

          // 링크 데이터가 존재하는지 검증
          const hasLink = !!place.link;

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
              <div style="display: flex; align-items: center; gap: 12px; flex-shrink: 0;">
                <div style="display: flex; width: 28px; height: 28px; flex-shrink: 0; align-items: center; justify-content: center; border-radius: 50%; background-color: #2563eb; color: #ffffff; font-weight: bold; font-size: 14px;">
                  ${index + 1}
                </div>
                <div style="display: flex; width: 64px; height: 64px; flex-shrink: 0; align-items: center; justify-content: center; overflow: hidden; border-radius: 8px; border: 1px solid #f1f5f9; background-color: #f8fafc;">
                  ${safeImageSrc ? `
                    <img src="${safeImageSrc}" alt="${place.name}" style="height: 100%; width: 100%; object-fit: cover;" />
                  ` : `
                    <span style="font-size: 11px; font-weight: 600; color: #94a3b8;">${t.noImage}</span>
                  `}
                </div>
              </div>

              <div style="flex: 1; min-width: 0;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                  <h3 style="margin: 0; font-size: 16px; font-weight: bold; color: #1e293b;">${place.name}</h3>
                  <span style="font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; color: ${badgeColor}; background-color: ${badgeBg};">
                    ${subCategory}
                  </span>
                </div>
                <p style="margin: 0 0 4px 0; font-size: 13px; color: #64748b;">${place.address}</p>
                <div style="display: flex; align-items: center; justify-content: space-between;">
                  <p style="margin: 0; font-size: 13px; color: #f59e0b; font-weight: bold;">★ ${rating}</p>
                  ${hasLink ? `
                    <a href="${place.link}" target="_blank" rel="noopener noreferrer" style="font-size: 11px; text-decoration: none; font-weight: bold; padding: 2px 8px; border-radius: 4px; color: #475569; background-color: #f1f5f9; border: 1px solid #e2e8f0; display: inline-flex; align-items: center; gap: 4px;">
                      🔗 ${t.moreInfo}
                    </a>
                  ` : ''}
                </div>
              </div>
            </div>
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

  const handleSavePDF = async () => {
    showToast(t.toastSave);
    const element = await generateAllDaysPdfTemplate();

    const options = {
      margin: [20, 15, 20, 15],
      filename: `Travel_Route_Full_Days.pdf`,
      image: { type: 'jpeg', quality: 0.98 },
      html2canvas: {
        scale: 2,
        useCORS: true,
        logging: false
      },
      jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
    };

    html2pdf().set(options).from(element).save();
  };

  const handleSharePDF = async () => {
    showToast(t.toastShare);
    const element = await generateAllDaysPdfTemplate();
    const fileName = 'SeoulMate_Travel_Route.pdf';

    const options = {
      margin: [20, 15, 20, 15],
      filename: fileName,
      image: { type: 'jpeg', quality: 0.98 },
      html2canvas: {
        scale: 2,
        useCORS: true,
        logging: false
      },
      jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
    };

    try {
      const pdfWorker = html2pdf().set(options).from(element);
      const pdfBlob = await pdfWorker.output('blob');

      const file = new File([pdfBlob], fileName, { type: 'application/pdf' });

      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({
          files: [file],
          title: `✈️ SeoulMate - ${t.title}`,
          text: `제가 생성한 전체 일정(${allDay}일간) 여행 루트 PDF 문서입니다.`,
        });
        showToast(t.toastShareSuccess);
      } else {
        showToast(t.toastShareFallback);
        html2pdf().set(options).from(element).save();
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error('PDF 공유 중 에러가 발생했습니다:', err);
        showToast(t.toastShareFallback);
        html2pdf().set(options).from(element).save();
      }
    }
  };

  return (
      <div className="flex-1 flex flex-col min-h-0 p-5 space-y-6">
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
                onClick={handleSharePDF}
                className="flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-all shadow-sm"
            >
              {t.shareBtn}
            </button>
          </div>
        </div>

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

        <div className="flex-1 overflow-y-auto space-y-4 min-h-0 pr-1">
          {currentRoute.length > 0 ? (
              currentRoute.map((place, index) => {
                const category = getPlaceDisplayCategory(place);
                const subCategory = getPlaceDisplaySubCategory(place);
                const rating = getPlaceDisplayRating(place);
                const image = getPlaceDisplayImage(place);

                // 리스트 아이템에 실제로 link 프로퍼티가 존재하는지 체크
                const hasLink = !!place.link;

                return (
                    <article
                        key={place.id}
                        className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:border-slate-300 transition-all duration-200 relative"
                    >
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

                          {/* 별점 라인과 링크 버튼 정렬 */}
                          <div className="flex items-center justify-between mt-1 min-h-[24px]">
                            <p className="text-sm text-amber-500 font-semibold flex items-center gap-1">
                              ★ {rating}
                            </p>

                            {/* 화면에 표시되는 🔗 바로가기 버튼 */}
                            {hasLink && (
                                <a
                                    href={place.link}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    onClick={(e) => {
                                      // 카드 삭제 이벤트 등이 클릭 인터셉트하지 않도록 버블링 방지
                                      e.stopPropagation();
                                    }}
                                    className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600 hover:bg-slate-200 border border-slate-200 transition-colors"
                                >
                                  🔗 {t.moreInfo}
                                </a>
                            )}
                          </div>
                        </div>
                      </div>

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

                      <div className="absolute top-4 right-4 z-10">
                        <button
                            type="button"
                            onClick={() => {
                              removePathItem(place.id);
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