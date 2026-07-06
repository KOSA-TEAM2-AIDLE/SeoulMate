import Header from "./layout/Header";
import ChatSidebar from "./pages/ChatSidebar";
import MapWorkspace from "./pages/MapWorkspace";
import PlaceSidebar from "./pages/PlaceSidebar";

export default function MainPage() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <Header />
      <main className="grid flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[360px_minmax(420px,1fr)_380px]">
        <PlaceSidebar />
        <MapWorkspace />
        <ChatSidebar />
      </main>
    </div>
  );
}
