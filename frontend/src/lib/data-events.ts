"use client";

import { useEffect } from "react";

const EVENT_NAME = "labsmith:data-changed";

export function emitDataChanged(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(EVENT_NAME));
  }
}

export function useDataChangedListener(handler: () => void): void {
  useEffect(() => {
    if (typeof window === "undefined") return;
    window.addEventListener(EVENT_NAME, handler);
    return () => window.removeEventListener(EVENT_NAME, handler);
  }, [handler]);
}
