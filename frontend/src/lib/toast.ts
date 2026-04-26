"use client";

export type ToastVariant = "default" | "destructive";

export interface Toast {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
}

interface ToastInput {
  title: string;
  description?: string;
  variant?: ToastVariant;
  durationMs?: number;
}

const DEFAULT_DURATION_MS = 4500;
const MAX_TOASTS = 5;

let toasts: Toast[] = [];
const listeners = new Set<() => void>();

export function toast(input: ToastInput): string {
  const id = createToastId();
  const nextToast: Toast = {
    id,
    title: input.title,
    description: input.description,
    variant: input.variant ?? "default",
  };

  toasts = [...toasts, nextToast].slice(-MAX_TOASTS);
  emit();
  globalThis.setTimeout(() => dismissToast(id), input.durationMs ?? DEFAULT_DURATION_MS);
  return id;
}

export function dismissToast(id: string): void {
  const nextToasts = toasts.filter((item) => item.id !== id);
  if (nextToasts.length === toasts.length) return;
  toasts = nextToasts;
  emit();
}

export function subscribeToasts(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getToasts(): Toast[] {
  return toasts;
}

function emit() {
  listeners.forEach((listener) => listener());
}

function createToastId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
}
