/* zustand 도입 전 MainPages 에서 사이드패널 및 지도에서 정보를 모두 알기 위한 임시 import */
import { useState } from "react";
import { INITIAL_ROUTES } from "./data/mockRoutePlaces";

import Header from "./layout/Header";
import ChatSidebar from "./pages/ChatSidebar";
import MapWorkspace from "./pages/MapWorkspace";
import PlaceSidebar from "./pages/PlaceSidebar";


export default function MainPage() {
    const [selectedDay, setSelectedDay] = useState(1);
    const [routes, setRoutes] = useState(INITIAL_ROUTES);
    
    return (
        <div className="flex h-screen w-screen flex-col bg-slate-50 text-slate-900 overflow-hidden">
            <Header />
            <main className="grid h-[calc(100vh-64px)] flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[380px_minmax(420px,1fr)_380px]">
                <PlaceSidebar
                    selectedDay = {selectedDay}
                    setSelectedDay = {setSelectedDay}
                    routes = {routes}
                    setRoutes = {setRoutes}/>
                <MapWorkspace
                    selectedDay = {selectedDay}
                    routes = {routes} />
                <ChatSidebar />
            </main>
        </div>
    );
}