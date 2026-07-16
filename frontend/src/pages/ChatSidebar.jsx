import useChatSidebar from "../hooks/chat/useChatSidebar";
import MessageList from "../components/chat/MessageList";
import ChatInputBox from "../components/chat/ChatInputBox";

export default function ChatSidebar() {
  const {
    t,
    messages,
    inputValue,
    setInputValue,
    isStreaming,
    messageEndRef,
    selectedDay,
    all_day,
    handleSendMessage,
  } = useChatSidebar();

  return (
      <aside className="flex min-h-[360px] flex-col border-l border-slate-200 bg-white">
        {/* 챗봇 헤더 */}
        <div className="flex items-center gap-3 border-b border-slate-200 p-5 shrink-0">
          <div className="flex size-11 items-center justify-center rounded-xl bg-blue-50 text-2xl shadow-sm">
            🤖
          </div>
          <div>
            <h2 className="font-bold text-blue-600">{t.headerTitle}</h2>
            <p className="text-[14px] font-normal text-slate-500">
              {t.headerDesc(selectedDay, all_day)}
            </p>
          </div>
        </div>

        {/* 메시지 스트림 리스트 */}
        <MessageList
            messages={messages}
            isStreaming={isStreaming}
            preparingText={t.preparing}
            messageEndRef={messageEndRef}
        />

        {/* 입력창 인터페이스 */}
        <div className="border-t border-slate-200 p-3 shrink-0">
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