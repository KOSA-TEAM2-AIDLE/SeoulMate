import { useEffect, useRef, useState } from "react";
import { streamChat } from "../api/chat";
import AssistantMessage from "../components/chat/AssistantMessage";
import ChatInputBox from "../components/chat/ChatInputBox";
import UserMessage from "../components/chat/UserMessage";
import useTravelStore from "../stores/useTravelStore";

const INITIAL_MESSAGES = [
  {
    id: "welcome",
    role: "assistant",
    content: "궁금한 점은 물어봐주세요!",
  },
];

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
  const [messages, setMessages] = useState(INITIAL_MESSAGES);
  const [inputValue, setInputValue] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const messageEndRef = useRef(null);

  const {
    setRecommendList,
    setDay,
    setAllDay,
    day,
    all_day
  } = useTravelStore();

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
        lang: "ko",
        onToken: (token) => appendAssistantToken(assistantMessage.id, token),
        onError: (payload) => {
          throw new Error(
              payload.message ?? "채팅 응답 중 오류가 발생했습니다.",
          );
        },
      });

      const nextDayMockList = [
        {
          id: "ACCO003",
          name: "신라호텔 서울",
          category: "숙소",
          subCategory: "럭셔리",
          address: "서울 중구 동호로 249",
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
          rating: "4.7",
          reviews: "4,912",
          time: "19:00 - 21:00",
          image: "https://images.unsplash.com/photo-1578469550956-0e16b69c6a3d?auto=format&fit=crop&w=150&q=80"
        }
      ];

      setDay(1);
      setAllDay(3);
      setRecommendList(nextDayMockList);

    } catch (error) {
      setMessages((currentMessages) =>
          currentMessages.map((message) =>
              message.id === assistantMessage.id
                  ? {
                    ...message,
                    content:
                        error instanceof Error
                            ? error.message
                            : "채팅 응답을 불러오지 못했습니다.",
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
            <h2 className="font-bold text-blue-600">SeoulMate 챗봇</h2>
            <p className="text-[14px] font-normal text-slate-500">
              외국인을 위한 서울 여행 가이드 챗봇 (현재: {day} / {all_day}일차)
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
                        (isStreaming ? "답변을 준비하고 있어요..." : "")}
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