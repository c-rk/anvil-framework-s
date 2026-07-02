import { useEffect } from "react";
import { DOCS_URL, NEW_TAB } from "../lib/docs";

interface Props {
  open: boolean;
  onClose: () => void;
}

interface Shortcut {
  keys: string[];
  desc: string;
}

const SHORTCUTS: Shortcut[] = [
  { keys: ["Ctrl", "K"], desc: "Open spotlight search (⌘K on macOS)" },
  { keys: ["?"], desc: "Show / hide this shortcuts sheet" },
  { keys: ["g", "c"], desc: "Go to the Calculator page" },
  { keys: ["g", "v"], desc: "Go to the Canvas page" },
  { keys: ["t"], desc: "Toggle dark / light theme" },
  { keys: ["Esc"], desc: "Close any open overlay" },
];

/**
 * "?" cheat-sheet overlay listing keyboard shortcuts. Serif copy throughout;
 * key caps are mono. Includes a docs link that opens in a new tab.
 */
export function ShortcutsHelp({ open, onClose }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="help-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="help-sheet" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts">
        <div className="help-head">
          <h2>Keyboard shortcuts</h2>
          <button className="help-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <dl className="help-list">
          {SHORTCUTS.map((s) => (
            <div className="help-row" key={s.desc}>
              <dt className="help-keys">
                {s.keys.map((k, i) => (
                  <kbd key={i} className="kbd">
                    {k}
                  </kbd>
                ))}
              </dt>
              <dd className="help-desc">{s.desc}</dd>
            </div>
          ))}
        </dl>
        <p className="help-foot">
          Full documentation:{" "}
          <a href={DOCS_URL} {...NEW_TAB}>
            Anvil docs ↗
          </a>
        </p>
      </div>
    </div>
  );
}
