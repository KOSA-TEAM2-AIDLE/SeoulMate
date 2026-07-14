import { useLangStore } from "../stores/useLangStore";

export default function Header() {
    const { lang, setLang } = useLangStore();

    return (
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-5">
            <div className="flex items-center gap-3">
                <div className="flex size-9 items-center justify-center rounded-lg bg-blue-600 text-lg font-bold text-white">
                    S
                </div>
                <h1 className="text-2xl font-bold text-blue-600">SeoulMate</h1>
            </div>

            {/* 라디오 버튼 그룹 Container */}
            <div className="flex items-center gap-1 rounded-full bg-slate-100 p-1">
                {/* 한국어 라디오 */}
                <label className="relative flex cursor-pointer items-center justify-center">
                    <input
                        type="radio"
                        name="language"
                        value="ko"
                        checked={lang === "ko"}
                        onChange={() => setLang("ko")}
                        className="peer sr-only" // 실제 input은 숨기고 peer 클래스로 스타일링 제어
                    />
                    <span className="rounded-full px-3.5 py-1.5 text-xs font-bold text-slate-500 transition-all peer-checked:bg-white peer-checked:text-blue-600 peer-checked:shadow-sm">
            KO
          </span>
                </label>

                {/* 영어 라디오 */}
                <label className="relative flex cursor-pointer items-center justify-center">
                    <input
                        type="radio"
                        name="language"
                        value="en"
                        checked={lang === "en"}
                        onChange={() => setLang("en")}
                        className="peer sr-only"
                    />
                    <span className="rounded-full px-3.5 py-1.5 text-xs font-bold text-slate-500 transition-all peer-checked:bg-white peer-checked:text-blue-600 peer-checked:shadow-sm">
            EN
          </span>
                </label>
            </div>
        </header>
    );
}