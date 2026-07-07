import { useEffect, useRef, useState } from "react";
import { streamChat } from "../api/chat";
import AssistantMessage from "../components/chat/AssistantMessage";
import ChatInputBox from "../components/chat/ChatInputBox";
import UserMessage from "../components/chat/UserMessage";

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
            외국인을 위한 서울 여행 가이드 챗봇
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
