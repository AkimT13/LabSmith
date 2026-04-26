"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  fetchMessages,
  postChat,
  type ArtifactType,
  type Message,
  type PartRequest,
  type PrintabilityReport,
  type ValidationIssue,
} from "@/lib/api";

export interface GenerationState {
  status: "idle" | "generating" | "complete" | "error";
  template?: string;
  artifactId?: string;
  artifactType?: ArtifactType;
  fileSizeBytes?: number | null;
  version?: number;
}

interface UseChatOptions {
  sessionId: string;
  initialSpec?: PartRequest | null;
  onArtifactGenerated?: () => void | Promise<void>;
}

interface ParsedSseEvent {
  event: string;
  data: string;
}

interface TextDeltaPayload {
  message_id: string;
  delta: string;
}

interface SpecParsedPayload {
  part_request: PartRequest;
  validation: ValidationIssue[];
  printability?: PrintabilityReport;
}

interface GenerationStartedPayload {
  template: string;
}

interface GenerationCompletePayload {
  artifact_id: string;
  artifact_type: ArtifactType;
  file_size_bytes: number | null;
  version: number;
}

interface MessageCompletePayload {
  message_id: string;
  content: string;
}

interface ErrorPayload {
  code: string;
  detail: string;
}

// M9 onboarding event payloads (per docs/M9_CONTRACT.md §4)
interface TopicSuggestedPayload {
  topic: string;
  label: string;
  rationale: string;
  suggested_questions?: string[];
}

interface ChecklistStepPayload {
  step_id: string;
  title: string;
  detail: string;
  status: string;
}

interface DocReferencedPayload {
  document_id?: string;
  title: string;
  source: string;
  url: string | null;
  score?: number;
}

export interface OnboardingTopic {
  topic: string;
  label: string;
  rationale: string;
  suggestedQuestions: string[];
}

export interface OnboardingChecklistItem {
  stepId: string;
  title: string;
  detail: string;
  status: string;
}

export interface OnboardingCitation {
  documentId: string | null;
  title: string;
  source: string;
  url: string | null;
  score: number | null;
}

export function useChat({ sessionId, initialSpec = null, onArtifactGenerated }: UseChatOptions) {
  const { getToken, isLoaded, isSignedIn } = useAuth();

  const [messages, setMessages] = useState<Message[]>([]);
  const [currentSpec, setCurrentSpec] = useState<PartRequest | null>(initialSpec);
  const [validationIssues, setValidationIssues] = useState<ValidationIssue[]>([]);
  const [printability, setPrintability] = useState<PrintabilityReport | null>(null);
  const [generation, setGeneration] = useState<GenerationState>({ status: "idle" });
  // M9 onboarding turn state — reset at the start of each new chat turn.
  const [onboardingTopic, setOnboardingTopic] = useState<OnboardingTopic | null>(null);
  const [onboardingChecklist, setOnboardingChecklist] = useState<OnboardingChecklistItem[]>([]);
  const [onboardingCitations, setOnboardingCitations] = useState<OnboardingCitation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refreshMessages = useCallback(
    async ({ showLoading = true }: { showLoading?: boolean } = {}) => {
      if (!isLoaded || !isSignedIn || !sessionId) return;

      if (showLoading) {
        setIsLoading(true);
      }
      setError(null);

      try {
        const token = await getToken();
        if (!token) {
          setError("No Clerk session token. Sign out and sign back in.");
          return;
        }

        setMessages(await fetchMessages(token, sessionId));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load messages");
      } finally {
        if (showLoading) {
          setIsLoading(false);
        }
      }
    },
    [getToken, isLoaded, isSignedIn, sessionId],
  );

  const handleStreamEvent = useCallback(
    (streamEvent: ParsedSseEvent) => {
      const payload = parseJson(streamEvent.data);

      if (streamEvent.event === "text_delta") {
        const data = payload as TextDeltaPayload;
        setMessages((previous) =>
          appendAssistantDelta(previous, sessionId, data.message_id, data.delta),
        );
        return;
      }

      if (streamEvent.event === "spec_parsed") {
        const data = payload as SpecParsedPayload;
        setCurrentSpec(data.part_request);
        setValidationIssues(data.validation ?? []);
        setPrintability(data.printability ?? null);
        return;
      }

      if (streamEvent.event === "generation_started") {
        const data = payload as GenerationStartedPayload;
        setGeneration({ status: "generating", template: data.template });
        return;
      }

      if (streamEvent.event === "generation_complete") {
        const data = payload as GenerationCompletePayload;
        setGeneration({
          status: "complete",
          artifactId: data.artifact_id,
          artifactType: data.artifact_type,
          fileSizeBytes: data.file_size_bytes,
          version: data.version,
        });

        if (onArtifactGenerated) {
          void Promise.resolve(onArtifactGenerated()).catch((err: unknown) => {
            setError(err instanceof Error ? err.message : "Failed to refresh artifacts");
          });
        }
        return;
      }

      if (streamEvent.event === "message_complete") {
        const data = payload as MessageCompletePayload;
        setMessages((previous) =>
          setAssistantContent(previous, sessionId, data.message_id, data.content),
        );
        return;
      }

      if (streamEvent.event === "topic_suggested") {
        const data = payload as TopicSuggestedPayload;
        setOnboardingTopic({
          topic: data.topic,
          label: data.label,
          rationale: data.rationale,
          suggestedQuestions: data.suggested_questions ?? [],
        });
        // Reset the per-turn onboarding pieces so a re-run of the same
        // session doesn't leak the previous turn's checklist or citations.
        setOnboardingChecklist([]);
        setOnboardingCitations([]);
        return;
      }

      if (streamEvent.event === "checklist_step") {
        const data = payload as ChecklistStepPayload;
        setOnboardingChecklist((previous) => [
          ...previous,
          {
            stepId: data.step_id,
            title: data.title,
            detail: data.detail,
            status: data.status,
          },
        ]);
        return;
      }

      if (streamEvent.event === "doc_referenced") {
        const data = payload as DocReferencedPayload;
        setOnboardingCitations((previous) => [
          ...previous,
          {
            documentId: data.document_id ?? null,
            title: data.title,
            source: data.source,
            url: data.url,
            score: typeof data.score === "number" ? data.score : null,
          },
        ]);
        return;
      }

      if (streamEvent.event === "error") {
        const data = payload as ErrorPayload;
        setGeneration({ status: "error" });
        setError(data.detail || data.code || "Chat stream failed");
      }
    },
    [onArtifactGenerated, sessionId],
  );

  const sendMessage = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed || isStreaming) return;

      if (!isLoaded || !isSignedIn) {
        setError("Sign in before sending a message.");
        return;
      }

      const optimisticMessage: Message = {
        id: `local-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        session_id: sessionId,
        role: "user",
        content: trimmed,
        metadata: null,
        created_at: new Date().toISOString(),
      };

      abortRef.current?.abort();
      const abortController = new AbortController();
      abortRef.current = abortController;

      setMessages((previous) => [...previous, optimisticMessage]);
      setGeneration({ status: "idle" });
      // Clear M9 onboarding state so the new turn starts from a blank slate.
      setOnboardingTopic(null);
      setOnboardingChecklist([]);
      setOnboardingCitations([]);
      setError(null);
      setIsStreaming(true);

      try {
        const token = await getToken();
        if (!token) {
          throw new ApiError(401, "No Clerk session token. Sign out and sign back in.");
        }

        const response = await postChat(
          token,
          sessionId,
          { content: trimmed },
          abortController.signal,
        );

        if (!response.body) {
          throw new ApiError(0, "Chat endpoint returned an empty stream.");
        }

        await readSseStream(response.body, handleStreamEvent);
        await refreshMessages({ showLoading: false });
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setGeneration({ status: "error" });
        setError(err instanceof Error ? err.message : "Failed to send message");
      } finally {
        if (abortRef.current === abortController) {
          abortRef.current = null;
        }
        setIsStreaming(false);
      }
    },
    [
      getToken,
      handleStreamEvent,
      isLoaded,
      isSignedIn,
      isStreaming,
      refreshMessages,
      sessionId,
    ],
  );

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- async data fetch
    refreshMessages();

    return () => {
      abortRef.current?.abort();
    };
  }, [refreshMessages]);

  return {
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
  };
}

function appendAssistantDelta(
  messages: Message[],
  sessionId: string,
  messageId: string,
  delta: string,
): Message[] {
  const existingIndex = messages.findIndex((message) => message.id === messageId);

  if (existingIndex >= 0) {
    return messages.map((message, index) =>
      index === existingIndex ? { ...message, content: `${message.content}${delta}` } : message,
    );
  }

  return [
    ...messages,
    {
      id: messageId,
      session_id: sessionId,
      role: "assistant",
      content: delta,
      metadata: null,
      created_at: new Date().toISOString(),
    },
  ];
}

function setAssistantContent(
  messages: Message[],
  sessionId: string,
  messageId: string,
  content: string,
): Message[] {
  const existingIndex = messages.findIndex((message) => message.id === messageId);

  if (existingIndex >= 0) {
    return messages.map((message, index) =>
      index === existingIndex ? { ...message, content } : message,
    );
  }

  return [
    ...messages,
    {
      id: messageId,
      session_id: sessionId,
      role: "assistant",
      content,
      metadata: null,
      created_at: new Date().toISOString(),
    },
  ];
}

async function readSseStream(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: ParsedSseEvent) => void,
) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();

      if (value) {
        buffer += decoder.decode(value, { stream: !done });
        const blocks = buffer.split(/\r?\n\r?\n/);
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          const event = parseSseBlock(block);
          if (event) {
            onEvent(event);
          }
        }
      }

      if (done) break;
    }

    buffer += decoder.decode();
    if (buffer.trim()) {
      const finalBlock = parseSseBlock(buffer);
      if (finalBlock) {
        onEvent(finalBlock);
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function parseSseBlock(block: string): ParsedSseEvent | null {
  let event = "message";
  const dataLines: string[] = [];

  for (const rawLine of block.split(/\r?\n/)) {
    const line = rawLine.trimEnd();
    if (!line || line.startsWith(":")) continue;

    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    }

    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  if (!dataLines.length) return null;

  return {
    event,
    data: dataLines.join("\n"),
  };
}

function parseJson(data: string): unknown {
  try {
    return JSON.parse(data);
  } catch {
    return {};
  }
}
