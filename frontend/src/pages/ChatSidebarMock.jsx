import { useEffect, useRef, useState } from "react";
import AssistantMessage from "../components/chat/AssistantMessage";
import ChatInputBox from "../components/chat/ChatInputBox";
import UserMessage from "../components/chat/UserMessage";
import useTravelStore from "../stores/useTravelStore";
import { useLangStore } from "../stores/useLangStore";

const UI_TEXT = {
    ko: {
        welcome: "안녕하세요! 궁금한 점은 물어봐주세요! (테스트용 Mock 모드)",
        headerTitle: "SeoulMate 챗봇 (Mock)",
        headerDesc: (day, allDay) => `외국인을 위한 서울 여행 가이드 챗봇 (현재: ${day} / ${allDay}일차)`,
        preparing: "답변을 준비하고 있어요...",
        errFallback: "채팅 응답을 불러오지 못했습니다."
    },
    en: {
        welcome: "Feel free to ask me anything! (Test Mock Mode)",
        headerTitle: "SeoulMate Chatbot (Mock)",
        headerDesc: (day, allDay) => `Seoul travel guide chatbot for foreigners (Current: Day ${day} / ${allDay})`,
        preparing: "Preparing an answer...",
        errFallback: "Failed to load chat response."
    }
};

// 📍 테스트용 숙소 링크 포함 목데이터
const MOCK_RECOMMEND_DATA = {
    responseType: "recommendation",
    recommendList: [
        {
            id: "HOTEL_MOCK_01",
            name: "그랜드 하얏트 서울",
            category: "숙소",
            subCategory: "5성급 호텔",
            address: "서울특별시 용산구 소월로 322",
            lat: 37.5394,
            lng: 126.9975,
            rating: "4.7",
            reviews: "2,450",
            time: null,
            image: "https://images.unsplash.com/photo-1566073771259-6a8506099945?q=80&w=300",
            selectionReason: "전망이 우수하며 도심 접근성과 럭셔리한 휴식을 동시에 만족하는 숙소입니다.",
            link: "https://www.hyatt.com/ko-KR/hotel/south-korea/grand-hyatt-seoul/selrs"
        },
        {
            id: "HOTEL_MOCK_02",
            name: "한옥 게스트하우스 혜화",
            category: "숙소",
            subCategory: "게스트하우스",
            address: "서울특별시 종로구 혜화로 12길",
            lat: 37.5878,
            lng: 127.0012,
            rating: "4.5",
            reviews: "310",
            time: null,
            image: null,
            selectionReason: "전통적인 한옥의 고즈넉한 멋을 체험하기 좋은 가성비 높은 숙소입니다.",
            link: "https://www.booking.com"
        },
        {
            id: "REST_MOCK_01",
            name: "맛있는 정원",
            category: "맛집",
            subCategory: "한식",
            address: "서울특별시 종로구 삼청로 12-1",
            lat: 37.5795,
            lng: 126.9814,
            rating: "4.5",
            reviews: "1,824",
            time: null,
            image: null,
            selectionReason: "정갈하고 깔끔한 한정식 코스로, 사용자의 선호 분위기와 일치합니다.",
            link: null
        }
    ]
};

const MOCK_ROUTE_DATA = {
    responseType: "route",
    travelPath: {
        "1": [
            {
                id: "REST_MOCK_02",
                name: "명동교자 본점",
                category: "맛집",
                subCategory: "한식/칼국수",
                address: "서울 중구 명동10길 29",
                lat: 37.5626,
                lng: 126.9854,
                rating: "4.6",
                reviews: "5,842",
                time: "12:00 - 13:00",
                image: null,
                selectionReason: "첫 방문지와 다음 장소 사이의 동선과 점심 조건에 적합합니다.",
                link: null
            },
            {
                id: "HOTEL_MOCK_03",
                name: "롯데호텔 서울",
                category: "숙소",
                subCategory: "5성급 호텔",
                address: "서울특별시 중구 을지로 30",
                lat: 37.5651,
                lng: 126.9808,
                rating: "4.8",
                reviews: "3,120",
                time: "15:00 - 익일 11:00",
                image: "https://images.unsplash.com/photo-1566073771259-6a8506099945?q=80&w=300",
                selectionReason: "도심 관광 후 바로 휴식을 취하기 가장 편리한 동선 상에 위치한 고급 호텔입니다.",
                link: "https://www.lottehotel.com/seoul-hotel/ko.html"
            }
        ],
        "2": [
            {
                id: "CAFE_MOCK_01",
                name: "블루보틀 삼청 한옥",
                category: "카페",
                subCategory: "카페/디저트",
                address: "서울특별시 종로구 북촌로 5길",
                lat: 37.5802,
                lng: 126.9821,
                rating: "4.4",
                reviews: "920",
                time: "10:00 - 11:30",
                image: null,
                selectionReason: "이른 아침 고즈넉한 한옥 분위기에서 조용히 커피를 즐기기 좋습니다.",
                link: null
            }
        ]
    }
};

export default function ChatSidebarMock() {
    const lang = useLangStore((state) => state.lang);
    const t = UI_TEXT[lang];

    const [messages, setMessages] = useState([
        {
            id: "welcome",
            role: "assistant",
            content: UI_TEXT[lang].welcome,
        }
    ]);
    const [inputValue, setInputValue] = useState("");
    const [isStreaming, setIsStreaming] = useState(false);
    const messageEndRef = useRef(null);

    const {
        setTravelPath,
        setRecommendList,
        setAllDay,
        selectedDay,
        all_day
    } = useTravelStore();

    useEffect(() => {
        setMessages((currentMessages) =>
            currentMessages.map((msg) =>
                msg.id === "welcome"
                    ? { ...msg, content: UI_TEXT[lang].welcome }
                    : msg
            )
        );
    }, [lang]);

    useEffect(() => {
        messageEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, isStreaming]);

    const appendAssistantToken = (assistantId, token) => {
        setMessages((currentMessages) =>
            currentMessages.map((message) =>
                message.id === assistantId
                    ? { ...message, content: `${message.content}${token}` }
                    : message,
            ),
        );
    };

    const handleSendMessage = async (messageText = inputValue) => {
        const trimmedMessage = messageText.trim();

        if (!trimmedMessage || isStreaming) {
            return;
        }

        const userMessage = {
            id: `user-${Date.now()}`,
            role: "user",
            content: trimmedMessage,
        };
        const assistantMessage = {
            id: `assistant-${Date.now()}`,
            role: "assistant",
            content: "",
        };

        setMessages((currentMessages) => [
            ...currentMessages,
            userMessage,
            assistantMessage,
        ]);
        setInputValue("");
        setIsStreaming(true);

        // 가상 대답 및 가상 스트리밍 시작
        setTimeout(() => {
            let textResponse = "";
            let payload = null;

            // 🔍 질문 키워드에 따라 응답 데이터 분기
            const query = trimmedMessage.toLowerCase();
            if (query.includes("추천") || query.includes("recommend") || query.includes("맛집") || query.includes("숙소")) {
                textResponse = lang === 'ko'
                    ? "요청하신 조건에 가장 어울리는 서울의 추천 리스트를 준비했습니다! 바로가기 링크를 통해 바로 상세 정보를 보실 수 있습니다."
                    : "I have found the perfect recommendations in Seoul matching your conditions! Check out the details via the 'Link' buttons.";
                payload = { recommendList: MOCK_RECOMMEND_DATA.recommendList, travelPath: null };
            } else {
                textResponse = lang === 'ko'
                    ? "일정을 알차게 채워줄 1~2일차 여행 루트 동선을 최적화해서 지도에 표시해 드렸어요! 마음에 드시나요?"
                    : "I have optimized and mapped out your travel path for Days 1 and 2! Let me know if you would like to adjust it.";
                payload = { recommendList: null, travelPath: MOCK_ROUTE_DATA.travelPath, allDay: 2 };
            }

            let index = 0;
            const interval = setInterval(() => {
                if (index < textResponse.length) {
                    // 글자를 끊어서 스트리밍하는 효과 모사
                    const token = textResponse.slice(index, index + 3);
                    appendAssistantToken(assistantMessage.id, token);
                    index += 3;
                } else {
                    clearInterval(interval);
                    setIsStreaming(false);

                    // 💾 스트리밍 완료 시점에 전역 Zustand 스토어 업데이트
                    if (payload) {
                        if (payload.allDay) {
                            setAllDay(payload.allDay);
                        }
                        if (payload.travelPath) {
                            setTravelPath(payload.travelPath);
                            setRecommendList([]); // 기존 추천 리스트 초기화
                        }
                        if (payload.recommendList) {
                            setRecommendList(payload.recommendList);
                            // setTravelPath({}); // 원한다면 기존 패스를 초기화하거나 유지
                        }
                    }
                }
            }, 50);

        }, 800); // 0.8초 딜레이 뒤 답변 스트리밍 시작
    };

    return (
        <aside className="flex min-h-[360px] flex-col border-l border-slate-200 bg-white">
            <div className="flex items-center gap-3 border-b border-slate-200 p-5 bg-slate-50/50">
                <div className="flex size-11 items-center justify-center rounded-xl bg-blue-50 text-2xl shadow-sm">
                    🧪
                </div>
                <div>
                    <h2 className="font-bold text-blue-600">{t.headerTitle}</h2>
                    <p className="text-[14px] font-normal text-slate-500">
                        {t.headerDesc(selectedDay, all_day)}
                    </p>
                </div>
            </div>

            <div className="flex-1 space-y-5 overflow-y-auto px-4 py-5">
                {messages.map((message) =>
                    message.role === "user" ? (
                        <UserMessage key={message.id}>{message.content}</UserMessage>
                    ) : (
                        <AssistantMessage key={message.id}>
                            {message.content ||
                                (isStreaming ? t.preparing : "")}
                        </AssistantMessage>
                    ),
                )}
                <div ref={messageEndRef} />
            </div>

            <div className="border-t border-slate-200 p-3">
                <ChatInputBox
                    value={inputValue}
                    onChange={(event) => setInputValue(event.target.value)}
                    onSubmit={() => handleSendMessage()}
                    disabled={isStreaming}
                />
            </div>
        </aside>
    );
}