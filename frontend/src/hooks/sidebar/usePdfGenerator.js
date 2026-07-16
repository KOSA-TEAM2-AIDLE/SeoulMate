import html2pdf from 'html2pdf.js';
import useTravelStore from '../../stores/useTravelStore';
import {
    getPlaceDisplayCategory,
    getPlaceDisplaySubCategory,
    getPlaceDisplayRating,
    getPlaceDisplayImage,
} from '../../services/map/placeDisplayAdapter';

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

export default function usePdfGenerator(t) {
    const allDay = useTravelStore((state) => state.all_day);
    const travelPath = useTravelStore((state) => state.travelPath);
    const days = Array.from({ length: allDay }, (_, i) => i + 1);

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

    const getPdfOptions = (filename) => ({
        margin: [20, 15, 20, 15],
        filename,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true, logging: false },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
    });

    const savePDF = async (showToast) => {
        showToast(t.toastSave);
        const element = await generateAllDaysPdfTemplate();
        const options = getPdfOptions('Travel_Route_Full_Days.pdf');
        html2pdf().set(options).from(element).save();
    };

    const sharePDF = async (showToast) => {
        showToast(t.toastShare);
        const element = await generateAllDaysPdfTemplate();
        const fileName = 'SeoulMate_Travel_Route.pdf';
        const options = getPdfOptions(fileName);

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

    return { savePDF, sharePDF };
}