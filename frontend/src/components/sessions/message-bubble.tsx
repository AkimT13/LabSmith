import { Bot, User } from "lucide-react";

import { cn } from "@/lib/utils";
import type { Message } from "@/lib/api";

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3", isUser && "justify-end")}>
      {!isUser && (
        <div className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-md border bg-muted">
          <Bot className="h-4 w-4" />
        </div>
      )}

      <div
        className={cn(
          "max-w-[82%] rounded-md border px-3 py-2 text-sm shadow-xs",
          isUser ? "bg-primary text-primary-foreground" : "bg-card",
        )}
      >
        <div className="whitespace-pre-wrap break-words leading-6">{message.content}</div>
        <p
          className={cn(
            "mt-2 text-[11px]",
            isUser ? "text-primary-foreground/70" : "text-muted-foreground",
          )}
        >
          {new Date(message.created_at).toLocaleTimeString([], {
            hour: "numeric",
            minute: "2-digit",
          })}
        </p>
      </div>

      {isUser && (
        <div className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-md border bg-muted">
          <User className="h-4 w-4" />
        </div>
      )}
    </div>
  );
}
