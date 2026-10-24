import { useCallback, useEffect, useState } from "react";

export type ApiState<T> =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

/** Runs `load` whenever `key` changes; aborts stale requests; `retry` re-runs it. */
export function useApi<T>(load: (signal: AbortSignal) => Promise<T>, key: string): [ApiState<T>, () => void] {
  const [state, setState] = useState<ApiState<T>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading" });
    load(controller.signal)
      .then((data) => setState({ status: "ready", data }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setState({ status: "error", message: err instanceof Error ? err.message : "Unexpected error." });
      });
    return () => controller.abort();
    // `load` is recreated every render; `key` captures its real inputs.
  }, [key, attempt]);

  const retry = useCallback(() => setAttempt((a) => a + 1), []);
  return [state, retry];
}
