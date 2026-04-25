"use client";

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { Loader2, MessageSquare, RefreshCw, Send } from "lucide-react";

import { MessageBubble } from "@/components/sessions/message-bubble";
import { SpecCard } from "@/components/sessions/spec-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useChat } from "@/lib/use-chat";

interface ChatPanelProps {
  sessionId: string;
  disabled?: boolean;
  disabledReason?: string;
  onArtifactGenerated?: () => void | Promise<void>;
}

export function ChatPanel({
  sessionId,
  disabled = false,
  disabledReason,
  onArtifactGenerated,
}: ChatPanelProps) {
  const [draft, setDraft] = useState("");
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const {
    messages,
    currentSpec,
    validationIssues,
    generation,
    isLoading,
    isStreaming,
    error,
    sendMessage,
    refreshMessages,
  } = useChat({ sessionId, onArtifactGenerated });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages, isStreaming]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextMessage = draft.trim();
    if (!nextMessage || disabled || isStreaming) return;

    setDraft("");
    await sendMessage(nextMessage);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <Card className="min-h-[680px]">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <MessageSquare className="h-4 w-4" />
            Design chat
          </CardTitle>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => void refreshMessages()}
            disabled={isLoading || isStreaming}
            aria-label="Refresh messages"
          >
            <RefreshCw className={isLoading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex min-h-[600px] flex-col gap-4">
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
          {isLoading && messages.length === 0 && (
            <p className="text-sm text-muted-foreground">Loading messages...</p>
          )}

          {!isLoading && messages.length === 0 && (
            <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
              Start with a part request or a design change.
            </div>
          )}

          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {isStreaming && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Assistant is responding
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <SpecCard spec={currentSpec} validationIssues={validationIssues} generation={generation} />

        {error && (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        {disabled && disabledReason && (
          <p className="rounded-md border bg-muted px-3 py-2 text-sm text-muted-foreground">
            {disabledReason}
          </p>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe the part or change..."
            rows={3}
            disabled={disabled || isStreaming}
            className="min-h-24 w-full resize-y rounded-md border bg-background px-3 py-2 text-sm outline-none transition focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-60"
          />
          <div className="flex justify-end">
            <Button type="submit" disabled={!draft.trim() || disabled || isStreaming}>
              {isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Send
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
