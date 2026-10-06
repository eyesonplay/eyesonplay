import { Fragment } from "react";

import { cn } from "@/lib/utils";

const TOKEN = /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;

/** Pretty-printed, syntax-coloured JSON (no dangerouslySetInnerHTML). */
export function JsonView({ value, className }: { value: unknown; className?: string }) {
  const text = JSON.stringify(value, null, 2) ?? "undefined";
  const parts: React.ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(TOKEN)) {
    const index = match.index ?? 0;
    if (index > last) parts.push(text.slice(last, index));
    const [whole, str, colon, keyword, num] = match;
    if (str && colon) {
      parts.push(
        <Fragment key={index}>
          <span className="text-sky-300">{str}</span>
          {colon}
        </Fragment>,
      );
    } else if (str) {
      parts.push(<span key={index} className="text-emerald-300">{str}</span>);
    } else if (keyword) {
      parts.push(<span key={index} className="text-violet-300">{keyword}</span>);
    } else if (num) {
      parts.push(<span key={index} className="text-amber-200">{num}</span>);
    } else {
      parts.push(whole);
    }
    last = index + whole.length;
  }
  parts.push(text.slice(last));
  return <pre className={cn("font-mono text-[12px] leading-relaxed whitespace-pre text-zinc-300", className)}>{parts}</pre>;
}
