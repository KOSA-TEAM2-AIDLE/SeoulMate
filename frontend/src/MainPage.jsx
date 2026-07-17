import Header from "./layout/Header";
import ChatSidebar from "./pages/ChatSidebar";
import MapWorkspace from "./pages/MapWorkspace";
import PlaceSidebar from "./pages/PlaceSidebar";
import ChatSidebarMock from "./pages/ChatSidebarMock.jsx";
import {useCurrentLocation} from "./hooks/location/useCurrentLocation";


export default function MainPage() {
    useCurrentLocation();

    return (
        <div className="flex h-screen w-screen flex-col bg-slate-50 text-slate-900 overflow-hidden">
            <Header/>
            <main
                className="grid h-[calc(100vh-64px)] flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[380px_minmax(420px,1fr)_380px]">
                <PlaceSidebar/>
                <MapWorkspace/>
                <ChatSidebar/>
                {/*<ChatSidebarMock/>*/}
            </main>
        </div>
    );
}