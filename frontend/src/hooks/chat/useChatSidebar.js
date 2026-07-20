import { useState, useEffect, useRef } from "react";
import { streamChat } from "../../api/chat";
import { resumeTravelQuery, startTravelQuery } from "../../api/travelQuery";
import useTravelStore from "../../stores/useTravelStore";
import { useLangStore } from "../../stores/useLangStore";
import useLocationStore from "../../stores/useLocationStore";

const UI_TEXT = {
    ko: {
        welcome: "궁금한 점은 물어봐주세요!",
        headerTitle: "SeoulMate 챗봇",
        headerDesc: (day, allDay) => `외국인을 위한 서울 여행 가이드 챗봇 (현재: ${day} / ${allDay}일차)`,
        preparing: "답변을 준비하고 있어요...",
        errStreaming: "채팅 응답 중 오류가 발생했습니다.",
        errFallback: "채팅 응답을 불러오지 못했습니다."
    },
    en: {
        welcome: "Feel free to ask me anything!",
        headerTitle: "SeoulMate Chatbot",
        headerDesc: (day, allDay) => `Seoul travel guide chatbot for foreigners (Current: Day ${day} / ${allDay})`,
        preparing: "Preparing an answer...",
        errStreaming: "An error occurred while receiving the chat response.",
        errFallback: "Failed to load chat response."
    }
};

function toChatHistory(messages) {
    return messages
        .filter((msg) => msg.role === "user" || msg.role === "assistant")
        .map((msg) => ({
            role: msg.role,
            content: msg.content,
        }));
}

export default function useChatSidebar() {
    const lang = useLangStore((state) => state.lang);
    const t = UI_TEXT[lang] || UI_TEXT.ko;
    const coordinates = useLocationStore((state) => state.coordinates);

    const [messages, setMessages] = useState([
        {
            id: "welcome",
            role: "assistant",
            content: t.welcome,
        }
    ]);
    const [inputValue, setInputValue] = useState("");
    const [isStreaming, setIsStreaming] = useState(false);
    const [travelQueryThreadId, setTravelQueryThreadId] = useState(null);
    const messageEndRef = useRef(null);
    const previousStructuredQueryRef = useRef(null);

    const {
        setTravelPath,
        setAccommodation,
        setRecommendList,
        setAllDay,
        selectedDay,
        all_day
    } = useTravelStore();

    // 1. 다국어 설정 변경 시 환영 메시지 업데이트
    useEffect(() => {
        setMessages((current) =>
            current.map((msg) =>
                msg.id === "welcome"
                    ? { ...msg, content: t.welcome }
                    : msg
            )
        );
    }, [lang, t.welcome]);

    // 2. 메시지 추가되거나 스트리밍 중일 때 최하단 스크롤
    useEffect(() => {
        messageEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, isStreaming]);

    // 3. 스트리밍 토큰 누적 업데이트 함수
    const appendAssistantToken = (assistantId, token) => {
        setMessages((current) =>
            current.map((msg) =>
                msg.id === assistantId
                    ? { ...msg, content: `${msg.content}${token}` }
                    : msg
            )
        );
    };

    const setAssistantContent = (assistantId, content) => {
        setMessages((current) =>
            current.map((msg) =>
                msg.id === assistantId ? { ...msg, content } : msg
            )
        );
    };

    // 4. 메시지 전송 로직
    const handleSendMessage = async (messageText = inputValue) => {
        const trimmedMessage = messageText.trim();
        if (!trimmedMessage || isStreaming) return;

        const userMessage = {
            id: `user-${Date.now()}`,
            role: "user",
            content: trimmedMessage,
        };
        const assistantMessage = {
            id: `assistant-${Date.now()}`,
            role: "assistant",
            content: "",
        };

        setMessages((current) => [...current, userMessage, assistantMessage]);
        setInputValue("");
        setIsStreaming(true);

        try {
            const queryResponse = travelQueryThreadId
                ? await resumeTravelQuery(
                    travelQueryThreadId,
                    trimmedMessage,
                    coordinates
                )
                : await startTravelQuery({
                    message: trimmedMessage,
                    language: lang,
                    history: toChatHistory(messages).slice(-12),
                    previousStructuredQuery:
                        previousStructuredQueryRef.current ?? undefined,
                    lat: coordinates?.latitude,
                    lng: coordinates?.longitude,
                });

            if (queryResponse.status === "collecting") {
                setTravelQueryThreadId(queryResponse.thread_id);
                setAssistantContent(
                    assistantMessage.id,
                    queryResponse.assistant_message ?? t.errFallback
                );
                return;
            }

            if (queryResponse.status === "unsupported") {
                setTravelQueryThreadId(null);
                setAssistantContent(
                    assistantMessage.id,
                    queryResponse.assistant_message ?? t.errFallback
                );
                return;
            }

            const parsedQuery = queryResponse.structured_query;
            if (queryResponse.status !== "ready" || !parsedQuery) {
                throw new Error(t.errFallback);
            }

            setTravelQueryThreadId(null);
            previousStructuredQueryRef.current = parsedQuery;
            await streamChat({
                message: trimmedMessage,
                history: toChatHistory(messages),
                lang: lang,
                parsedIntent: parsedQuery.intent,
                sourceMode: parsedQuery.source_mode ?? undefined,
                parsedQuery,
                lat: coordinates?.latitude,
                lng: coordinates?.longitude,
                onMeta: (payload) => {
                    const result = payload?.result;
                    if (!result) return;

                    if (result.allDay !== undefined && result.allDay !== null) {
                        setAllDay(result.allDay);
                    }
                    if (result.travelPath) setTravelPath(result.travelPath);
                    if (result.responseType === "route") {
                        setAccommodation(result.accommodation ?? null);
                    }
                    if (Array.isArray(result.recommendList)) {
                        setRecommendList(result.recommendList);
                    }
                },
                onToken: (token) => appendAssistantToken(assistantMessage.id, token),
                onDone: () => {},
                onError: (payload) => {
                    throw new Error(payload.message ?? t.errStreaming);
                },
            });
        } catch (error) {
            setMessages((current) =>
                current.map((msg) =>
                    msg.id === assistantMessage.id
                        ? {
                            ...msg,
                            content: error instanceof Error ? error.message : t.errFallback,
                        }
                        : msg
                )
            );
        } finally {
            setIsStreaming(false);
        }
    };

    return {
        t,
        messages,
        inputValue,
        setInputValue,
        isStreaming,
        messageEndRef,
        selectedDay,
        all_day,
        handleSendMessage,
    };
}
