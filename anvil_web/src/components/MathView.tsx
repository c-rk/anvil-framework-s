import { useEffect, useRef } from "react";
import katex from "katex";

interface Props {
  /** LaTeX source to typeset. */
  latex?: string | null;
  /** Fallback shown verbatim (monospace) when no LaTeX is available. */
  fallback: string;
}

/**
 * Renders an RSQ formula. If `latex` is provided (from the RSQ metadata) it is
 * typeset with KaTeX; otherwise the Python signature `fallback` is shown.
 */
export function MathView({ latex, fallback }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (latex && ref.current) {
      try {
        katex.render(latex, ref.current, {
          throwOnError: false,
          displayMode: true,
        });
      } catch {
        ref.current.textContent = latex;
      }
    }
  }, [latex]);

  if (latex) {
    return <div className="math" ref={ref} />;
  }
  return <code className="signature">{fallback}</code>;
}
