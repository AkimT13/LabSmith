"use client";

import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, MessageSquare, RefreshCw, Send } from "lucide-react";

import { MessageBubble } from "@/components/sessions/message-bubble";
import { OnboardingTurnPanel } from "@/components/sessions/onboarding-turn-panel";
import { SpecCard } from "@/components/sessions/spec-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { PartRequest, SessionType } from "@/lib/api";
import { toast } from "@/lib/toast";
import { useChat } from "@/lib/use-chat";

interface ChatPanelProps {
  sessionId: string;
  sessionType?: SessionType;
  initialSpec?: PartRequest | null;
  disabled?: boolean;
  disabledReason?: string;
  onArtifactGenerated?: () => void | Promise<void>;
}

const VISIBLE_MESSAGE_LIMIT = 80;

interface CopyForType {
  cardTitle: string;
  emptyState: string;
  inputPlaceholder: string;
}

const COPY_BY_SESSION_TYPE: Record<SessionType, CopyForType> = {
  part_design: {
    cardTitle: "Design chat",
    emptyState: "Start with a part request or a design change.",
    inputPlaceholder: "Describe the part or change...",
  },
  onboarding: {
    cardTitle: "Onboarding chat",
    emptyState:
      "Ask about anything — protocols, equipment, who owns what, where things live, " +
      "how to get access, or how to find your way around the lab.",
    inputPlaceholder:
      "Ask an onboarding question (e.g. 'How do I reserve the microscope?')",
  },
};

export function ChatPanel({
  sessionId,
  sessionType = "part_design",
  initialSpec = null,
  disabled = false,
  disabledReason,
  onArtifactGenerated,
}: ChatPanelProps) {
  const [draft, setDraft] = useState("");
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const lastErrorToastRef = useRef<string | null>(null);
  const {
    messages,
    currentSpec,
    validationIssues,
    printability,
    generation,
    onboardingTopic,
    onboardingChecklist,
    onboardingCitations,
    isLoading,
    isStreaming,
    error,
    sendMessage,
    refreshMessages,
  } = useChat({ sessionId, initialSpec, onArtifactGenerated });
  const visibleMessages = useMemo(
    () => messages.slice(-VISIBLE_MESSAGE_LIMIT),
    [messages],
  );
  const hiddenMessageCount = Math.max(messages.length - visibleMessages.length, 0);
  const copy = COPY_BY_SESSION_TYPE[sessionType];
  const isOnboarding = sessionType === "onboarding";

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [
    visibleMessages,
    currentSpec,
    generation.status,
    isStreaming,
    onboardingTopic,
    onboardingChecklist,
    onboardingCitations,
  ]);

  useEffect(() => {
    if (!error) {
      lastErrorToastRef.current = null;
      return;
    }
    if (lastErrorToastRef.current === error) return;

    lastErrorToastRef.current = error;
    toast({
      title: "Chat issue",
      description: error,
      variant: "destructive",
    });
  }, [error]);

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
    <Card className="flex h-[680px] flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <MessageSquare className="h-4 w-4" />
            {copy.cardTitle}
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
      <CardContent className="flex min-h-0 flex-1 flex-col gap-4">
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
          {isLoading && messages.length === 0 && (
            <div className="space-y-3" aria-label="Loading messages">
              <Skeleton className="ml-auto h-16 w-2/5" />
              <Skeleton className="h-16 w-3/5" />
              <Skeleton className="h-40 w-full" />
            </div>
          )}

          {!isLoading && messages.length === 0 && (
            <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
              {copy.emptyState}
            </div>
          )}

          {hiddenMessageCount > 0 && (
            <p className="text-center text-xs text-muted-foreground">
              Showing latest {visibleMessages.length} of {messages.length} messages.
            </p>
          )}

          {visibleMessages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {/* Per-session-type extras: design sessions get the spec card; */}
          {/* onboarding sessions get the topic + checklist + citation panel. */}
          {!isOnboarding && (
            <SpecCard
              spec={currentSpec}
              validationIssues={validationIssues}
              printability={printability}
              generation={generation}
            />
          )}

          {isOnboarding && (
            <OnboardingTurnPanel
              topic={onboardingTopic}
              checklist={onboardingChecklist}
              citations={onboardingCitations}
            />
          )}

          {isStreaming && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Assistant is responding
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

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
            placeholder={copy.inputPlaceholder}
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
