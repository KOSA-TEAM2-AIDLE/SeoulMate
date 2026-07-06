const CHAT_MESSAGES = [
  { id: 1, sender: 'ai', text: '서울 여행 루트를 추천해드릴게요.' },
  { id: 2, sender: 'user', text: '사람이 너무 많지 않은 곳이면 좋겠어.' },
];

const QUESTION_OPTIONS = ['조용한 분위기와 감성적인 사진', '맛집과 카페 탐방'];

export default function ChatSidebar() {
  return (
    <aside className="flex min-h-[360px] flex-col border-l border-slate-200 bg-white">
      <div className="flex items-center gap-3 border-b border-slate-200 p-5">
        <div className="flex size-11 items-center justify-center rounded-xl bg-blue-100 text-xl font-bold text-blue-700">
          AI
        </div>
        <div>
          <h2 className="font-bold text-blue-600">SeoulMate 챗봇</h2>
          <p className="text-sm text-slate-500">여행 추천 대화 영역</p>
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-5">
        {CHAT_MESSAGES.map((message) => (
          <div
            key={message.id}
            className={`max-w-[85%] rounded-xl px-4 py-3 text-sm ${
              message.sender === 'user'
                ? 'ml-auto bg-blue-600 text-white'
                : 'border border-slate-200 bg-slate-50 text-slate-700'
            }`}
          >
            {message.text}
          </div>
        ))}

        <div className="rounded-xl border border-slate-200 p-4">
          <p className="text-sm font-bold">추천 질문 카드 영역</p>
          <div className="mt-3 space-y-2">
            {QUESTION_OPTIONS.map((option, index) => (
              <button
                key={option}
                type="button"
                className={`w-full rounded-lg border px-3 py-2 text-left text-sm ${
                  index === 0
                    ? 'border-blue-600 text-blue-600'
                    : 'border-slate-200 text-slate-600'
                }`}
              >
                {option}
              </button>
            ))}
          </div>
        </div>
      </div>

      <form className="flex gap-2 border-t border-slate-200 p-4">
        <input
          type="text"
          placeholder="메시지를 입력하세요..."
          className="min-w-0 flex-1 rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none"
        />
        <button type="button" className="rounded-xl bg-blue-600 px-4 py-3 font-bold text-white">
          전송
        </button>
      </form>
    </aside>
  );
}
