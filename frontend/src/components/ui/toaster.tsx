"use client";

import { useSyncExternalStore } from "react";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";
import { dismissToast, getToasts, subscribeToasts } from "@/lib/toast";
import type { Toast } from "@/lib/toast";

const EMPTY_TOASTS: Toast[] = [];

export function Toaster() {
  const toasts = useSyncExternalStore(subscribeToasts, getToasts, getServerToasts);

  if (toasts.length === 0) return null;

  return (
    <div
      aria-label="Notifications"
      className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[min(calc(100vw-2rem),24rem)] flex-col gap-2"
      role="region"
    >
      {toasts.map((item) => (
        <div
          key={item.id}
          role={item.variant === "destructive" ? "alert" : "status"}
          className={cn(
            "pointer-events-auto rounded-md border bg-background p-3 text-sm shadow-lg",
            item.variant === "destructive" &&
              "border-destructive/30 bg-destructive/10 text-destructive",
          )}
        >
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              <p className="font-medium">{item.title}</p>
              {item.description && (
                <p className="mt-1 text-muted-foreground">{item.description}</p>
              )}
            </div>
            <button
              type="button"
              onClick={() => dismissToast(item.id)}
              className="rounded-sm p-1 text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label="Dismiss notification"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

function getServerToasts() {
  return EMPTY_TOASTS;
}
