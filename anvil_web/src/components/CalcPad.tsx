import { useCallback, useEffect, useState } from "react";
import { evaluate, type AngleMode } from "../lib/sciexpr";
import { fmtNum } from "../lib/numbers";
import {
  MEMORY_EVENT,
  clearAllMemory,
  clearHistory,
  clearMemory,
  memoryLabel,
  nextSlotName,
  pushHistory,
  readHistory,
  readMemory,
  setMemory,
  type HistoryEntry,
  type MemoryMap,
} from "../lib/memory";

/**
 * Right-hand work pane for the Calculator page: a scientific keypad on top and
 * the memory plane (named slots + an auto-log of recent results) below it.
 *
 * Slots and history live in localStorage and sync with the RSQ calculator via
 * the MEMORY_EVENT window event (M+ on a result lands here instantly).
 */
export function CalcPad() {
  const [expr, setExpr] = useState("");
  const [out, setOut] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [mode, setMode] = useState<AngleMode>("rad");
  const [memory, setMem] = useState<MemoryMap>(() => readMemory());
  const [history, setHist] = useState<HistoryEntry[]>(() => readHistory());

  useEffect(() => {
    const refresh = () => {
      setMem(readMemory());
      setHist(readHistory());
    };
    window.addEventListener(MEMORY_EVENT, refresh);
    return () => window.removeEventListener(MEMORY_EVENT, refresh);
  }, []);

  const put = useCallback((tok: string) => {
    setErr(null);
    setExpr((e) => e + tok);
  }, []);

  const run = useCallback(() => {
    const text = expr.trim();
    if (!text) return;
    try {
      const v = evaluate(text, mode);
      setOut(v);
      setErr(null);
      pushHistory({
        kind: "calc",
        label: text,
        items: [{ name: "=", value: v, unit: "" }],
        t: Date.now(),
      });
    } catch (e: any) {
      setOut(null);
      setErr(String(e?.message ?? e));
    }
  }, [expr, mode]);

  const storeResult = useCallback(() => {
    if (out === null) return;
    const map = readMemory();
    setMem(setMemory(nextSlotName(map), { kind: "scalar", value: out, unit: "" }));
  }, [out]);

  const keys: [string, string][] = [
    ["7", "7"], ["8", "8"], ["9", "9"], ["(", "("], [")", ")"],
    ["4", "4"], ["5", "5"], ["6", "6"], ["×", "*"], ["÷", "/"],
    ["1", "1"], ["2", "2"], ["3", "3"], ["+", "+"], ["−", "-"],
    ["0", "0"], [".", "."], ["EXP", "e"], ["^", "^"], ["π", "pi"],
    ["sin", "sin("], ["cos", "cos("], ["tan", "tan("], ["√", "sqrt("], ["x²", "^2"],
    ["ln", "ln("], ["log", "log("], ["eˣ", "exp("], ["abs", "abs("], ["%", "%"],
  ];

  return (
    <aside className="calcpad" aria-label="Scientific calculator and memory">
      {/* ------------------------- keypad ------------------------- */}
      <div className="calcpad-section">
        <div className="calcpad-head">
          <span className="calcpad-title">calculator</span>
          <button
            className={`calcpad-mode ${mode}`}
            onClick={() => setMode((m) => (m === "rad" ? "deg" : "rad"))}
            title="Toggle trig angle mode"
          >
            {mode}
          </button>
        </div>

        <input
          className="calcpad-display"
          value={expr}
          placeholder="2 * pi * sqrt(8 / g0)"
          onChange={(e) => {
            setExpr(e.target.value);
            setErr(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") run();
          }}
          aria-label="Expression"
          spellCheck={false}
        />
        <div className={`calcpad-out ${err ? "err" : ""}`} aria-live="polite">
          {err ? err : out !== null ? `= ${fmtNum(out)}` : " "}
        </div>

        <div className="calcpad-keys">
          {keys.map(([label, tok]) => (
            <button key={label} className="calcpad-key" onClick={() => put(tok)}>
              {label}
            </button>
          ))}
          <button
            className="calcpad-key calcpad-key-dim"
            onClick={() => {
              setExpr("");
              setOut(null);
              setErr(null);
            }}
          >
            C
          </button>
          <button
            className="calcpad-key calcpad-key-dim"
            onClick={() => setExpr((e) => e.slice(0, -1))}
          >
            ⌫
          </button>
          <button
            className="calcpad-key calcpad-key-dim"
            onClick={storeResult}
            disabled={out === null}
            title="Store result into the next free memory slot"
          >
            MS
          </button>
          <button className="calcpad-key calcpad-key-eq" onClick={run}>
            =
          </button>
        </div>
      </div>

      {/* ------------------------- memory slots ------------------------- */}
      <div className="calcpad-section">
        <div className="calcpad-head">
          <span className="calcpad-title">memory</span>
          {Object.keys(memory).length > 0 && (
            <button
              className="calcpad-clear"
              onClick={() => setMem(clearAllMemory())}
              title="Clear all memory slots"
            >
              MC
            </button>
          )}
        </div>
        {Object.keys(memory).length === 0 ? (
          <p className="calcpad-empty">
            Empty — use M+ on a result, or MS on the keypad.
          </p>
        ) : (
          <ul className="calcpad-slots">
            {Object.entries(memory).map(([n, slot]) => (
              <li key={n} className="calcpad-slot">
                <button
                  className="calcpad-slot-main"
                  onClick={() => {
                    if (slot.kind === "scalar") put(String(slot.value));
                  }}
                  title={
                    slot.kind === "scalar"
                      ? `Insert ${slot.value} into the expression`
                      : "Array slot (recall it from an array input)"
                  }
                >
                  <span className="calcpad-slot-name">{n}</span>
                  <span className="calcpad-slot-val">{memoryLabel(slot)}</span>
                </button>
                <button
                  className="calcpad-slot-x"
                  onClick={() => setMem(clearMemory(n))}
                  title={`Clear ${n}`}
                  aria-label={`Clear memory ${n}`}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* ------------------------- history ------------------------- */}
      <div className="calcpad-section calcpad-history">
        <div className="calcpad-head">
          <span className="calcpad-title">history</span>
          {history.length > 0 && (
            <button
              className="calcpad-clear"
              onClick={() => setHist(clearHistory())}
              title="Clear history"
            >
              clear
            </button>
          )}
        </div>
        {history.length === 0 ? (
          <p className="calcpad-empty">Solve results and = evaluations land here.</p>
        ) : (
          <ul className="calcpad-log">
            {history.map((h) => (
              <li key={h.t} className="calcpad-log-entry">
                <span className="calcpad-log-label" title={h.label}>
                  {h.kind === "calc" ? h.label : h.label}
                </span>
                <span className="calcpad-log-items">
                  {h.items.slice(0, 4).map((it) => (
                    <button
                      key={it.name}
                      className="calcpad-log-val"
                      onClick={() => put(String(it.value))}
                      title={`Insert ${it.value} into the expression`}
                    >
                      {h.kind === "solve" && (
                        <span className="calcpad-log-name">{it.name}</span>
                      )}
                      {fmtNum(it.value)}
                      {it.unit ? ` ${it.unit}` : ""}
                    </button>
                  ))}
                  {h.items.length > 4 && (
                    <span className="calcpad-log-more">+{h.items.length - 4}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
