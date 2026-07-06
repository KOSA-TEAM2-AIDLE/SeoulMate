import AssistantMessage from '../components/chat/AssistantMessage';
import ChatInputBox from '../components/chat/ChatInputBox';
import QuestionCard from '../components/chat/QuestionCard';
import UserMessage from '../components/chat/UserMessage';

const QUESTION_OPTIONS = ['조용한 분위기와 감성적인 사진', '맛집과 카페 탐방', '전통문화 및 역사 체험'];

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
        <AssistantMessage>서울에서 2박 3일 감성 여행을 원하시는군요!</AssistantMessage>
        <UserMessage>사람이 너무 많지 않은 곳이면 좋겠어</UserMessage>
        <QuestionCard
          question="Q1. 여행에서 가장 중요하게 생각하는 것은 무엇인가요?"
          options={QUESTION_OPTIONS}
          selectedOption={QUESTION_OPTIONS[0]}
        />
      </div>

      <div className="border-t border-slate-200 p-4">
        <ChatInputBox />
      </div>
    </aside>
  );
}
