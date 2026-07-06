export default function UserMessage({ children }) {
  return (
    <div className="flex justify-end">
      <div className="relative max-w-[75%] rounded-3xl bg-[#2F6BFF] px-4 py-3 text-[15px] font-semibold leading-[1.5] text-white shadow-[0_8px_18px_rgba(47,107,255,0.18)]">
        <span className="relative">{children}</span>
      </div>
    </div>
  );
}
