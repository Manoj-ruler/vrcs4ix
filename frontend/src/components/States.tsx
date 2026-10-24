import type { ReactNode } from "react";

import type { ApiState } from "../lib/useApi";

export function Skeleton({ height = 160 }: { height?: number }) {
  return <div className="skeleton" style={{ height }} aria-hidden="true" />;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="state state-error" role="alert">
      <p>{message}</p>
      <button type="button" className="btn btn-secondary" onClick={onRetry}>Try again</button>
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="state"><p>{children}</p></div>;
}

/** Renders a block's loading / error / ready state; never shows figures before data arrives. */
export function Loadable<T>({
  state, onRetry, height, children,
}: { state: ApiState<T>; onRetry: () => void; height?: number; children: (data: T) => ReactNode }) {
  if (state.status === "loading") return <Skeleton {...(height ? { height } : {})} />;
  if (state.status === "error") return <ErrorState message={state.message} onRetry={onRetry} />;
  return <>{children(state.data)}</>;
}
