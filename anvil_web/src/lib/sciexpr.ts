// Safe scientific-expression evaluator for the calculator pad. Recursive
// descent over a small grammar — no eval(), no Function().
//
//   expr    := term (("+"|"-") term)*
//   term    := unary (("*"|"/"|"%") unary)*
//   unary   := ("-"|"+") unary | power
//   power   := atom ("^" unary)?            (right-assoc)
//   atom    := NUMBER | CONST | FUNC "(" expr ")" | "(" expr ")"
//
// Trig honors an angle mode ("rad" | "deg") for sin/cos/tan and their inverses.

export type AngleMode = "rad" | "deg";

const CONSTS: Record<string, number> = {
  pi: Math.PI,
  e: Math.E,
  tau: 2 * Math.PI,
  g0: 9.80665,
};

const FUNCS: Record<string, (x: number, mode: AngleMode) => number> = {
  sin: (x, m) => Math.sin(m === "deg" ? (x * Math.PI) / 180 : x),
  cos: (x, m) => Math.cos(m === "deg" ? (x * Math.PI) / 180 : x),
  tan: (x, m) => Math.tan(m === "deg" ? (x * Math.PI) / 180 : x),
  asin: (x, m) => (m === "deg" ? (Math.asin(x) * 180) / Math.PI : Math.asin(x)),
  acos: (x, m) => (m === "deg" ? (Math.acos(x) * 180) / Math.PI : Math.acos(x)),
  atan: (x, m) => (m === "deg" ? (Math.atan(x) * 180) / Math.PI : Math.atan(x)),
  sqrt: (x) => Math.sqrt(x),
  ln: (x) => Math.log(x),
  log: (x) => Math.log10(x),
  exp: (x) => Math.exp(x),
  abs: (x) => Math.abs(x),
};

class Parser {
  private i = 0;
  constructor(
    private readonly s: string,
    private readonly mode: AngleMode,
  ) {}

  parse(): number {
    const v = this.expr();
    this.ws();
    if (this.i < this.s.length) throw new Error(`unexpected '${this.s[this.i]}'`);
    return v;
  }

  private ws() {
    while (this.i < this.s.length && /\s/.test(this.s[this.i])) this.i++;
  }

  private peek(): string {
    this.ws();
    return this.s[this.i] ?? "";
  }

  private expr(): number {
    let v = this.term();
    for (;;) {
      const c = this.peek();
      if (c === "+") {
        this.i++;
        v += this.term();
      } else if (c === "-") {
        this.i++;
        v -= this.term();
      } else return v;
    }
  }

  private term(): number {
    let v = this.unary();
    for (;;) {
      const c = this.peek();
      if (c === "*") {
        this.i++;
        v *= this.unary();
      } else if (c === "/") {
        this.i++;
        v /= this.unary();
      } else if (c === "%") {
        this.i++;
        v %= this.unary();
      } else return v;
    }
  }

  private unary(): number {
    const c = this.peek();
    if (c === "-") {
      this.i++;
      return -this.unary();
    }
    if (c === "+") {
      this.i++;
      return this.unary();
    }
    return this.power();
  }

  private power(): number {
    const base = this.atom();
    if (this.peek() === "^") {
      this.i++;
      return Math.pow(base, this.unary());
    }
    return base;
  }

  private atom(): number {
    const c = this.peek();
    if (c === "(") {
      this.i++;
      const v = this.expr();
      if (this.peek() !== ")") throw new Error("missing ')'");
      this.i++;
      return v;
    }
    // number
    const num = /^(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?/.exec(this.s.slice(this.i));
    if (num) {
      this.i += num[0].length;
      return parseFloat(num[0]);
    }
    // identifier: constant or function
    const id = /^[a-zA-Z_][a-zA-Z0-9_]*/.exec(this.s.slice(this.i));
    if (id) {
      const name = id[0];
      this.i += name.length;
      if (this.peek() === "(") {
        const fn = FUNCS[name.toLowerCase()];
        if (!fn) throw new Error(`unknown function '${name}'`);
        this.i++;
        const arg = this.expr();
        if (this.peek() !== ")") throw new Error("missing ')'");
        this.i++;
        return fn(arg, this.mode);
      }
      const k = CONSTS[name.toLowerCase()];
      if (k === undefined) throw new Error(`unknown name '${name}'`);
      return k;
    }
    throw new Error(c ? `unexpected '${c}'` : "unexpected end of expression");
  }
}

/** Evaluate an expression; throws Error with a short message on bad input. */
export function evaluate(expr: string, mode: AngleMode = "rad"): number {
  const v = new Parser(expr, mode).parse();
  if (!Number.isFinite(v)) throw new Error("result is not finite");
  return v;
}
