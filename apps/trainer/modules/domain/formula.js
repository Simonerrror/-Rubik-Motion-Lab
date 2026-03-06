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

function tokenizeFormulaInternal(formula) {
  const text = String(formula || "");
  const tokens = [];
  let i = 0;

  while (i < text.length) {
    const char = text[i];
    if (/\s/.test(char)) {
      i += 1;
      continue;
    }

    if ("()^+".includes(char)) {
      tokens.push({ kind: char, value: char, start: i });
      i += 1;
      continue;
    }

    if (/\d/.test(char)) {
      const start = i;
      while (i < text.length && /\d/.test(text[i])) i += 1;
      tokens.push({ kind: "INT", value: text.slice(start, i), start });
      continue;
    }

    if (/[A-Za-z]/.test(char)) {
      const start = i;
      i += 1;
      if (i < text.length && /[wW]/.test(text[i]) && /[URFDLB]/.test(text[start])) {
        i += 1;
      }
      if (i < text.length && /['2]/.test(text[i])) {
        i += 1;
      }
      tokens.push({ kind: "MOVE", value: text.slice(start, i), start });
      continue;
    }

    throw new Error(`Unsupported character '${char}' at index ${i}`);
  }

  return tokens;
}

function validateSimultaneousAxis(moves, position) {
  if (moves.length < 2) return;
  let axis = null;
  moves.forEach((move) => {
    const [base] = splitMove(move);
    const currentAxis = moveAxis(base);
    if (!currentAxis) {
      throw new Error(`Unsupported move token at index ${position}`);
    }
    if (axis == null) {
      axis = currentAxis;
      return;
    }
    if (axis !== currentAxis) {
      throw new Error("Simultaneous moves must share axis");
    }
  });
}

function parseRepeat(tokens, state, isGroup) {
  if (state.index >= tokens.length) return 1;
  const token = tokens[state.index];

  if (token.kind === "^") {
    state.index += 1;
    const next = tokens[state.index];
    if (!next || next.kind !== "INT") {
      throw new Error(`Expected integer after '^' at index ${token.start}`);
    }
    state.index += 1;
    const repeat = Number.parseInt(next.value, 10);
    if (!Number.isFinite(repeat) || repeat < 1) {
      throw new Error(`Repeat must be >= 1 at index ${next.start}`);
    }
    return repeat;
  }

  if (isGroup && token.kind === "INT") {
    state.index += 1;
    const repeat = Number.parseInt(token.value, 10);
    if (!Number.isFinite(repeat) || repeat < 1) {
      throw new Error(`Repeat must be >= 1 at index ${token.start}`);
    }
    return repeat;
  }

  return 1;
}

function parseAtom(tokens, state) {
  const token = tokens[state.index];
  state.index += 1;

  if (token.kind === "(") {
    const steps = parseSequence(tokens, state, true);
    return [steps, true];
  }

  if (token.kind !== "MOVE") {
    throw new Error(`Expected move or '(' but got '${token.value}' at index ${token.start}`);
  }

  const simultaneous = [parseMove(token.value)];
  let simultaneousPos = token.start;
  while (state.index < tokens.length && tokens[state.index].kind === "+") {
    simultaneousPos = tokens[state.index].start;
    state.index += 1;
    const moveToken = tokens[state.index];
    if (!moveToken || moveToken.kind !== "MOVE") {
      throw new Error(`Expected move after '+' at index ${simultaneousPos}`);
    }
    state.index += 1;
    simultaneous.push(parseMove(moveToken.value));
  }

  validateSimultaneousAxis(simultaneous, simultaneousPos);
  return [[simultaneous], false];
}

function parseSequence(tokens, state, stopAtRParen = false) {
  const steps = [];

  while (state.index < tokens.length) {
    const token = tokens[state.index];
    if (token.kind === ")") {
      if (stopAtRParen) break;
      throw new Error(`Unexpected ')' at index ${token.start}`);
    }

    const [atomSteps, isGroup] = parseAtom(tokens, state);
    const repeat = parseRepeat(tokens, state, isGroup);
    for (let i = 0; i < repeat; i += 1) {
      atomSteps.forEach((step) => {
        steps.push([...step]);
      });
    }
  }

  if (stopAtRParen) {
    const token = tokens[state.index];
    if (!token || token.kind !== ")") {
      throw new Error(`Missing closing ')' at index ${String(tokens.at(-1)?.start ?? 0)}`);
    }
    state.index += 1;
  }

  return steps;
}

export function parseFormulaSteps(formula) {
  const normalized = normalizeFormula(formula);
  if (!normalized) throw new Error("Formula is empty");

  const tokens = tokenizeFormulaInternal(normalized);
  const state = { index: 0 };
  const steps = parseSequence(tokens, state, false);
  if (state.index !== tokens.length) {
    const token = tokens[state.index];
    throw new Error(`Unexpected token '${token.value}' at index ${token.start}`);
  }
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
