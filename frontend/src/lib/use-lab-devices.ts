"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback, useEffect, useRef, useState } from "react";

import { fetchLabDevices, type LabDevice } from "@/lib/api";

interface UseLabDevicesOptions {
  /** Poll cadence in ms while the page is visible. Default 2000. */
  intervalMs?: number;
  enabled?: boolean;
}

interface UseLabDevicesResult {
  devices: LabDevice[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

/**
 * Live device snapshot for a lab. Polls every ~2s — the backend derives
 * progress from `started_at + duration` on every read, so each poll gets a
 * fresh progress fraction and the UI can animate a bar by simply binding
 * `width: progress * 100%`.
 *
 * Why poll instead of SSE? `EventSource` doesn't carry an `Authorization`
 * header, and routing the Clerk JWT through a query string breaks our
 * standard auth path. Switch to SSE (or websockets) when we need sub-second
 * updates — for the demo, 2s polling looks just as live and is dramatically
 * simpler.
 */
export function useLabDevices(
  labId: string | null,
  { intervalMs = 2000, enabled = true }: UseLabDevicesOptions = {},
): UseLabDevicesResult {
  const { getToken } = useAuth();
  const [devices, setDevices] = useState<LabDevice[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlightRef = useRef(false);

  const load = useCallback(async () => {
    if (!labId || !enabled) return;
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    try {
      const token = await getToken();
      if (!token) {
        setError("No Clerk session token. Sign out and sign back in.");
        return;
      }
      const next = await fetchLabDevices(token, labId);
      setDevices(next);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load devices");
    } finally {
      inFlightRef.current = false;
      setLoading(false);
    }
  }, [enabled, getToken, labId]);

  useEffect(() => {
    if (!labId || !enabled) return;
    setLoading(true);
    void load();
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void load();
      }
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [enabled, intervalMs, labId, load]);

  return { devices, loading, error, refresh: load };
}
