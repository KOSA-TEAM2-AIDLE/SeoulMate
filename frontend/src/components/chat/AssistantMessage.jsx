export default function AssistantMessage({ children }) {
  return (
    <div className="flex items-end gap-2">
      <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-blue-50 text-lg shadow-sm">
        🤖
      </div>
      <div className="relative max-w-[75%] rounded-3xl border border-[#E7EAF2] bg-white px-4 py-3 text-[15px] font-medium leading-[1.5] text-slate-900 shadow-[0_8px_22px_rgba(15,23,42,0.06)]">
        <span className="relative">{children}</span>
      </div>
    </div>
  );
}
