/**
 * Catches a crash inside one page so the rest of the app (header, back
 * button, other pages) keeps working. App.tsx keys it by pathname, so
 * navigating anywhere resets it.
 */
import { Component, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Poster } from "../art/Poster";

type State = { error: Error | null };

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error("Page crashed:", error);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <main id="main" className="mx-auto grid max-w-5xl items-center gap-10 px-4 py-16 sm:px-6 md:grid-cols-2">
        <Poster city="Munnar" seed={500} className="aspect-[4/5] rounded-[2rem]" />
        <div>
          <p className="eyebrow">Something broke on this page</p>
          <h1 className="display mt-3 text-5xl">A pothole on an otherwise good road.</h1>
          <p className="mt-4 text-ink-2">The rest of YupReserved is fine — go back, or start again from home.</p>
          <p className="mt-3 font-mono text-xs text-ink-3">{this.state.error.message}</p>
          <div className="mt-8 flex gap-3">
            <button onClick={() => window.history.back()} className="rounded-full border border-line px-6 py-3">← Go back</button>
            <Link to="/" className="rounded-full bg-sindoor px-6 py-3 font-semibold text-sindoor-ink">Home</Link>
          </div>
        </div>
      </main>
    );
  }
}
