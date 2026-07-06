export default function ChatInputBox({ value = '', onChange, onSubmit, disabled = false }) {
  const handleSubmit = (event) => {
    event.preventDefault();
    onSubmit?.();
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-center gap-3 rounded-[18px] border border-slate-300 bg-slate-50 px-4 py-3"
    >
      <input
        type="text"
        value={value}
        onChange={onChange}
        disabled={disabled}
        placeholder="메시지를 입력하세요..."
        className="min-w-0 flex-1 bg-transparent text-base font-semibold text-slate-700 outline-none placeholder:text-slate-500 disabled:cursor-not-allowed"
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        aria-label="메시지 전송"
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M4 5L20 12L4 19V14L14 12L4 10V5Z"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinejoin="round"
          />
        </svg>
      </button>
    </form>
  );
}
