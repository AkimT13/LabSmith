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

export function useChat({ sessionId, initialSpec = null, onArtifactGenerated }: UseChatOptions) {
  const { getToken, isLoaded, isSignedIn } = useAuth();

  const [messages, setMessages] = useState<Message[]>([]);
  const [currentSpec, setCurrentSpec] = useState<PartRequest | null>(initialSpec);
  const [validationIssues, setValidationIssues] = useState<ValidationIssue[]>([]);
  const [generation, setGeneration] = useState<GenerationState>({ status: "idle" });
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
    generation,
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
