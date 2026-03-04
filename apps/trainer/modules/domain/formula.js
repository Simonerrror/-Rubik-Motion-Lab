import { AUTO_MERGE_UD_PAIRS, POSITIVE_BASES } from "../core/constants.js";

export function normalizeFormula(raw) {
  return String(raw || "")
    .replace(/\s*\+\s*/g, "+")
    .trim()
    .replace(/\s+/g, " ");
}

export function parseMove(rawMove) {
  const move = String(rawMove || "").trim();
  if (!move) throw new Error("Empty move token");

  let modifier = "";
  let body = move;
  if (body.endsWith("'") || body.endsWith("2")) {
    modifier = body.slice(-1);
    body = body.slice(0, -1);
    if (!body) throw new Error(`Invalid move token: ${move}`);
  }

  let normalizedBody = body;
  if (/^[URFDLB][wW]$/.test(body)) {
    normalizedBody = body[0].toLowerCase();
  }

  if (/^[xyzXYZ]$/.test(normalizedBody)) {
    normalizedBody = normalizedBody.toLowerCase();
  }

  if (normalizedBody.length !== 1) {
    throw new Error(`Unsupported move token: ${move}`);
  }

  const base = normalizedBody;
  const supported = "URFDLBMESxyzfrblud";
  if (!supported.includes(base)) {
    throw new Error(`Unsupported move token: ${move}`);
  }

  return `${base}${modifier}`;
}

export function splitMove(move) {
  const token = String(move || "").trim();
  if (!token) throw new Error("Empty move token");

  if (token.endsWith("'") || token.endsWith("2")) {
    return [token.slice(0, -1), token.slice(-1)];
  }
  return [token, ""];
}

export function moveAxis(base) {
  if (["F", "B", "S", "f", "b", "z"].includes(base)) return "x";
  if (["U", "D", "E", "u", "d", "y"].includes(base)) return "z";
  if (["L", "R", "M", "l", "r", "x"].includes(base)) return "y";
  return "";
}

export function moveSelector(base) {
  const selectors = {
    F: (p) => p[0] === -1,
    B: (p) => p[0] === 1,
    S: (p) => p[0] === 0,
    f: (p) => p[0] === -1 || p[0] === 0,
    b: (p) => p[0] === 0 || p[0] === 1,
    U: (p) => p[2] === 1,
    D: (p) => p[2] === -1,
    E: (p) => p[2] === 0,
    u: (p) => p[2] === 0 || p[2] === 1,
    d: (p) => p[2] === -1 || p[2] === 0,
    L: (p) => p[1] === 1,
    R: (p) => p[1] === -1,
    M: (p) => p[1] === 0,
    l: (p) => p[1] === 0 || p[1] === 1,
    r: (p) => p[1] === -1 || p[1] === 0,
    x: () => true,
    y: () => true,
    z: () => true,
  };
  return selectors[base];
}

export function moveTurns(base, modifier) {
  let turns = POSITIVE_BASES.has(base) ? 1 : -1;
  if (modifier === "'") turns *= -1;
  if (modifier === "2") turns *= 2;
  return turns;
}

export function parseFormulaSteps(formula) {
  const normalized = normalizeFormula(formula);
  if (!normalized) throw new Error("Formula is empty");

  const tokens = normalized.split(/\s+/).filter(Boolean);
  const steps = [];

  tokens.forEach((token) => {
    const parts = token
      .split("+")
      .map((part) => part.trim())
      .filter(Boolean);
    if (!parts.length) {
      throw new Error(`Invalid token: ${token}`);
    }

    const step = parts.map((part) => parseMove(part));
    let axis = null;
    step.forEach((move) => {
      const [base] = splitMove(move);
      const currentAxis = moveAxis(base);
      if (!currentAxis) throw new Error(`Unsupported move: ${move}`);
      if (axis == null) {
        axis = currentAxis;
      } else if (axis !== currentAxis) {
        throw new Error("Simultaneous moves must share axis");
      }
    });

    steps.push(step);
  });

  return steps;
}

export function mergeParallelUdPairs(steps) {
  const merged = [];
  let i = 0;
  while (i < steps.length) {
    const current = steps[i];
    const next = steps[i + 1];
    if (current && next && current.length === 1 && next.length === 1) {
      const pair = `${current[0]}|${next[0]}`;
      if (AUTO_MERGE_UD_PAIRS.has(pair)) {
        merged.push([current[0], next[0]]);
        i += 2;
        continue;
      }
    }
    merged.push([...current]);
    i += 1;
  }
  return merged;
}

export function invertMove(move) {
  if (move.endsWith("'")) return move.slice(0, -1);
  if (move.endsWith("2")) return move;
  return `${move}'`;
}

export function normalizeMoveSteps(formula) {
  const parsed = parseFormulaSteps(formula);
  const merged = mergeParallelUdPairs(parsed);
  return {
    steps: merged,
    movesFlat: merged.flat(),
    highlights: merged.map((step) => step.join("+")),
    formula: merged.map((step) => step.join("+")).join(" "),
  };
}

export function tokenizeFormula(formula) {
  return String(formula || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
}
