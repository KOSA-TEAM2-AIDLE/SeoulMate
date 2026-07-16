import { memo } from "react";
import UserMessage from "../../components/chat/UserMessage";
import AssistantMessage from "../../components/chat/AssistantMessage";

const MessageList = memo(({ messages, isStreaming, preparingText, messageEndRef }) => {
    return (
        <div className="flex-1 space-y-5 overflow-y-auto px-4 py-5">
            {messages.map((message) =>
                message.role === "user" ? (
                    <UserMessage key={message.id}>{message.content}</UserMessage>
                ) : (
                    <AssistantMessage key={message.id}>
                        {message.content || (isStreaming ? preparingText : "")}
                    </AssistantMessage>
                )
            )}
            <div ref={messageEndRef} />
        </div>
    );
});

MessageList.displayName = "MessageList";
export default MessageList;