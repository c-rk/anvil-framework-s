// A tiny, safe arithmetic expression evaluator — NO eval(), NO Function().
//
// Supports: + - * / % ^ (right-assoc power), unary minus/plus, parentheses,
// numeric literals, named variables, and a fixed whitelist of math functions
// and constants. It is a hand-written recursive-descent parser over a small
// token stream, so nothing from the host JS scope is ever reachable.
//
// Used by the EXPRESSION node (free formula over named input ports) and by the
// "scale/offset" helper. Returns a number; throws Error on parse/eval problems.

type TokKind = "num" | "ident" | "op" | "lparen" | "rparen" | "comma";
interface Tok {
  kind: TokKind;
  value: string;
}

const FUNCS: Record<string, (...a: number[]) => number> = {
  sin: Math.sin,
  cos: Math.cos,
  tan: Math.tan,
  asin: Math.asin,
  acos: Math.acos,
  atan: Math.atan,
  atan2: Math.atan2,
  sqrt: Math.sqrt,
  cbrt: Math.cbrt,
  abs: Math.abs,
  exp: Math.exp,
  ln: Math.log,
  log: Math.log10,
  log10: Math.log10,
  log2: Math.log2,
  sign: Math.sign,
  floor: Math.floor,
  ceil: Math.ceil,
  round: Math.round,
  min: Math.min,
  max: Math.max,
  pow: Math.pow,
  hypot: Math.hypot,
  sinh: Math.sinh,
  cosh: Math.cosh,
  tanh: Math.tanh,
  deg: (x: number) => (x * 180) / Math.PI,
  rad: (x: number) => (x * Math.PI) / 180,
};

const CONSTS: Record<string, number> = {
  pi: Math.PI,
  e: Math.E,
  tau: Math.PI * 2,
};

function tokenize(src: string): Tok[] {
  const toks: Tok[] = [];
  let i = 0;
  const n = src.length;
  while (i < n) {
    const c = src[i];
    if (c === " " || c === "\t" || c === "\n" || c === "\r") {
      i++;
      continue;
    }
    if ((c >= "0" && c <= "9") || c === ".") {
      let j = i + 1;
      while (j < n && /[0-9.]/.test(src[j])) j++;
      // exponent (1e-3)
      if (j < n && (src[j] === "e" || src[j] === "E")) {
        j++;
        if (j < n && (src[j] === "+" || src[j] === "-")) j++;
        while (j < n && /[0-9]/.test(src[j])) j++;
      }
      const lit = src.slice(i, j);
      if (!Number.isFinite(Number(lit))) throw new Error(`bad number: ${lit}`);
      toks.push({ kind: "num", value: lit });
      i = j;
      continue;
    }
    if (/[A-Za-z_]/.test(c)) {
      let j = i + 1;
      while (j < n && /[A-Za-z0-9_]/.test(src[j])) j++;
      toks.push({ kind: "ident", value: src.slice(i, j) });
      i = j;
      continue;
    }
    if ("+-*/%^".includes(c)) {
      toks.push({ kind: "op", value: c });
      i++;
      continue;
    }
    if (c === "(") {
      toks.push({ kind: "lparen", value: c });
      i++;
      continue;
    }
    if (c === ")") {
      toks.push({ kind: "rparen", value: c });
      i++;
      continue;
    }
    if (c === ",") {
      toks.push({ kind: "comma", value: c });
      i++;
      continue;
    }
    throw new Error(`unexpected character: ${c}`);
  }
  return toks;
}

/** Names referenced as variables (not functions/constants) in an expression. */
export function expressionVariables(src: string): string[] {
  let toks: Tok[];
  try {
    toks = tokenize(src);
  } catch {
    return [];
  }
  const out = new Set<string>();
  for (let i = 0; i < toks.length; i++) {
    const t = toks[i];
    if (t.kind !== "ident") continue;
    const isCall = toks[i + 1]?.kind === "lparen";
    const lower = t.value.toLowerCase();
    if (isCall && FUNCS[lower]) continue;
    if (CONSTS[lower]) continue;
    out.add(t.value);
  }
  return [...out];
}

/**
 * Evaluate `src` against the supplied variable bindings.
 * Identifiers not found in `vars`, `FUNCS`, or `CONSTS` raise an error.
 */
export function evalExpression(
  src: string,
  vars: Record<string, number>,
): number {
  const toks = tokenize(src);
  let pos = 0;

  const peek = () => toks[pos];
  const next = () => toks[pos++];
  const expect = (kind: TokKind) => {
    const t = next();
    if (!t || t.kind !== kind) throw new Error(`expected ${kind}`);
    return t;
  };

  // expr := term (('+'|'-') term)*
  function parseExpr(): number {
    let v = parseTerm();
    while (peek()?.kind === "op" && (peek().value === "+" || peek().value === "-")) {
      const op = next().value;
      const r = parseTerm();
      v = op === "+" ? v + r : v - r;
    }
    return v;
  }

  // term := factor (('*'|'/'|'%') factor)*
  function parseTerm(): number {
    let v = parseFactor();
    while (
      peek()?.kind === "op" &&
      (peek().value === "*" || peek().value === "/" || peek().value === "%")
    ) {
      const op = next().value;
      const r = parseFactor();
      if (op === "*") v *= r;
      else if (op === "/") v /= r;
      else v %= r;
    }
    return v;
  }

  // factor := unary ('^' factor)?   (power is right-associative)
  function parseFactor(): number {
    const base = parseUnary();
    if (peek()?.kind === "op" && peek().value === "^") {
      next();
      const exp = parseFactor();
      return Math.pow(base, exp);
    }
    return base;
  }

  // unary := ('+'|'-') unary | primary
  function parseUnary(): number {
    if (peek()?.kind === "op" && (peek().value === "+" || peek().value === "-")) {
      const op = next().value;
      const v = parseUnary();
      return op === "-" ? -v : v;
    }
    return parsePrimary();
  }

  // primary := num | const | func '(' args ')' | var | '(' expr ')'
  function parsePrimary(): number {
    const t = peek();
    if (!t) throw new Error("unexpected end of expression");
    if (t.kind === "num") {
      next();
      return Number(t.value);
    }
    if (t.kind === "lparen") {
      next();
      const v = parseExpr();
      expect("rparen");
      return v;
    }
    if (t.kind === "ident") {
      next();
      const lower = t.value.toLowerCase();
      if (peek()?.kind === "lparen") {
        // function call
        const fn = FUNCS[lower];
        if (!fn) throw new Error(`unknown function: ${t.value}`);
        next(); // (
        const args: number[] = [];
        if (peek()?.kind !== "rparen") {
          args.push(parseExpr());
          while (peek()?.kind === "comma") {
            next();
            args.push(parseExpr());
          }
        }
        expect("rparen");
        return fn(...args);
      }
      if (t.value in vars) return vars[t.value];
      if (lower in CONSTS) return CONSTS[lower];
      throw new Error(`unknown variable: ${t.value}`);
    }
    throw new Error(`unexpected token: ${t.value}`);
  }

  const result = parseExpr();
  if (pos !== toks.length) throw new Error("trailing tokens in expression");
  if (!Number.isFinite(result)) throw new Error("result is not finite");
  return result;
}
