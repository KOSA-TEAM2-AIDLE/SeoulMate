import { useEffect, useRef, useState } from "react";
import { streamChat } from "../api/chat";
import AssistantMessage from "../components/chat/AssistantMessage";
import ChatInputBox from "../components/chat/ChatInputBox";
import UserMessage from "../components/chat/UserMessage";
import useTravelStore from "../stores/useTravelStore";
import { useLangStore } from "../stores/useLangStore";

const UI_TEXT = {
  ko: {
    welcome: "궁금한 점은 물어봐주세요!",
    headerTitle: "SeoulMate 챗봇",
    headerDesc: (day, allDay) => `외국인을 위한 서울 여행 가이드 챗봇 (현재: ${day} / ${allDay}일차)`,
    preparing: "답변을 준비하고 있어요...",
    errStreaming: "채팅 응답 중 오류가 발생했습니다.",
    errFallback: "채팅 응답을 불러오지 못했습니다."
  },
  en: {
    welcome: "Feel free to ask me anything!",
    headerTitle: "SeoulMate Chatbot",
    headerDesc: (day, allDay) => `Seoul travel guide chatbot for foreigners (Current: Day ${day} / ${allDay})`,
    preparing: "Preparing an answer...",
    errStreaming: "An error occurred while receiving the chat response.",
    errFallback: "Failed to load chat response."
  }
};

function toChatHistory(messages) {
  return messages
      .filter(
          (message) => message.role === "user" || message.role === "assistant",
      )
      .map((message) => ({
        role: message.role,
        content: message.content,
      }));
}

export default function ChatSidebar() {
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
    setDay,
    setAllDay,
    day,
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

    try {
      await streamChat({
        message: trimmedMessage,
        history: toChatHistory(messages),
        lang: lang, // 4. API 호출 시 현재 설정된 언어('ko' 또는 'en')를 동적으로 전달!
        onToken: (token) => appendAssistantToken(assistantMessage.id, token),
        onError: (payload) => {
          throw new Error(
              payload.message ?? t.errStreaming,
          );
        },
      });

      const mockTravelPath = {
        1: [
          {
            id: "REST005",
            name: "명동교자 본점",
            category: "맛집",
            subCategory: "한식/칼국수",
            address: "서울 중구 명동10길 29",
            lat: 37.5626,
            lng: 126.9854,
            rating: "4.6",
            reviews: "5,842",
            time: "13:00 - 14:00",
            image: "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=150&q=80"
          },
          {
            id: "CAFE001",
            name: "블루보틀 삼청 카페",
            category: "카페",
            subCategory: "스페셜티 커피",
            address: "서울 종로구 북촌로5길 76",
            lat: 37.5791,
            lng: 126.9814,
            rating: "4.4",
            reviews: "1,204",
            time: "14:30 - 15:30",
            image: "https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&w=150&q=80"
          },
          {
            id: "SPOT001",
            name: "경복궁",
            category: "관광지",
            subCategory: "역사/고궁",
            address: "서울 종로구 사직로 161",
            lat: 37.5796,
            lng: 126.9770,
            rating: "4.7",
            reviews: "9,150",
            time: "16:00 - 18:00",
            image: "https://images.unsplash.com/photo-1540959733332-eab4deceeaf7?auto=format&fit=crop&w=150&q=80"
          }
        ],
        2: [
          {
            id: "SPOT002",
            name: "N서울타워",
            category: "관광지",
            subCategory: "전망대/랜드마크",
            address: "서울 용산구 남산공원길 105",
            lat: 37.5511,
            lng: 126.9882,
            rating: "4.5",
            reviews: "8,402",
            time: "10:30 - 12:30",
            image: "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?auto=format&fit=crop&w=150&q=80"
          },
          {
            id: "REST002",
            name: "우래옥",
            category: "맛집",
            subCategory: "평양냉면",
            address: "서울 중구 창경궁로 62-29",
            lat: 37.5684,
            lng: 126.9995,
            rating: "4.5",
            reviews: "4,103",
            time: "13:00 - 14:00",
            image: "https://images.unsplash.com/photo-1552611052-33e04de081de?auto=format&fit=crop&w=150&q=80"
          }
        ],
        3: [
          {
            id: "SPOT003",
            name: "롯데월드타워 서울스카이",
            category: "관광지",
            subCategory: "전망대",
            address: "서울 송파구 올림픽로 300",
            lat: 37.5126,
            lng: 127.1025,
            rating: "4.8",
            reviews: "6,712",
            time: "15:00 - 17:00",
            image: "https://images.unsplash.com/photo-1517089531969-5cba861611a1?auto=format&fit=crop&w=150&q=80"
          },
          {
            id: "CAFE002",
            name: "서울앵무새 성수점",
            category: "카페",
            subCategory: "디저트/베이커리",
            address: "서울 성동구 서울숲9길 3",
            lat: 37.5471,
            lng: 127.0427,
            rating: "4.3",
            reviews: "2,350",
            time: "17:30 - 18:30",
            image: "https://images.unsplash.com/photo-1555507036-ab1f4038808a?auto=format&fit=crop&w=150&q=80"
          }
        ]
      };

      const nextDayMockList = [
        {
          id: "ACCO003",
          name: "신라호텔 서울",
          category: "숙소",
          subCategory: "럭셔리",
          address: "서울 중구 동호로 249",
          lat: 37.5559,
          lng: 127.0051,
          rating: "4.8",
          reviews: "2,541",
          time: "15:00 (체크인)",
          image: "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=150&q=80"
        },
        {
          id: "REST005",
          name: "명동교자 본점",
          category: "맛집",
          subCategory: "한식/칼국수",
          address: "서울 중구 명동10길 29",
          lat: 37.5626,
          lng: 126.9854,
          rating: "4.6",
          reviews: "5,842",
          time: "13:00 - 14:00",
          image: "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=150&q=80"
        },
        {
          id: "CAFE005",
          name: "대충유원지 인왕산",
          category: "카페",
          subCategory: "뷰 맛집",
          address: "서울 종로구 필운대로 46",
          lat: 37.5802,
          lng: 126.9687,
          rating: "4.5",
          reviews: "423",
          time: "15:30 - 16:30",
          image: "https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&w=150&q=80"
        },
        {
          id: "EVT009",
          name: "N서울타워 전망대",
          category: "명소",
          subCategory: "야경/랜드마크",
          address: "서울 용산구 남산공원길 105",
          lat: 37.5512,
          lng: 126.9882,
          rating: "4.7",
          reviews: "4,912",
          time: "19:00 - 21:00",
          image: "https://images.unsplash.com/photo-1578469550956-0e16b69c6a3d?auto=format&fit=crop&w=150&q=80"
        },
        {
          id: "EVT009",
          name: "N Seoul Tower Observatory",
          category: "Attraction",
          subCategory: "Night View/Landmark",
          address: "105 Namsangongwon-gil, Yongsan-gu, Seoul",
          lat: 37.5512,
          lng: 126.9882,
          rating: "4.7",
          reviews: "4,912",
          time: "19:00 - 21:00",
          image: "https://images.unsplash.com/photo-1578469550956-0e16b69c6a3d?auto=format&fit=crop&w=150&q=80"
        }
      ];

      setDay(1);
      setAllDay(3);
      setRecommendList(nextDayMockList);
      setTravelPath(mockTravelPath)

    } catch (error) {
      setMessages((currentMessages) =>
          currentMessages.map((message) =>
              message.id === assistantMessage.id
                  ? {
                    ...message,
                    content:
                        error instanceof Error
                            ? error.message
                            : t.errFallback,
                  }
                  : message,
          ),
      );
    } finally {
      setIsStreaming(false);
    }
  };

  return (
      <aside className="flex min-h-[360px] flex-col border-l border-slate-200 bg-white">
        <div className="flex items-center gap-3 border-b border-slate-200 p-5">
          <div className="flex size-11 items-center justify-center rounded-xl bg-blue-50 text-2xl shadow-sm">
            🤖
          </div>
          <div>
            <h2 className="font-bold text-blue-600">{t.headerTitle}</h2>
            <p className="text-[14px] font-normal text-slate-500">
              {t.headerDesc(day, all_day)}
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