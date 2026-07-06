export default function UserMessage({ children }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[92%] rounded-[18px] bg-blue-600 px-5 py-4 text-base font-semibold leading-relaxed text-white shadow-sm">
        {children}
      </div>
    </div>
  );
}
