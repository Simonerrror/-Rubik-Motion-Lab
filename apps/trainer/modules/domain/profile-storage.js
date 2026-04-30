import {
  GROUPS,
  PROFILE_SCHEMA_VERSION,
  PROFILE_STORAGE_KEY,
  PROGRESS_SORT_STORAGE_KEY,
  STATUS_CYCLE,
} from "../core/constants.js";
import { cloneObject } from "../utils/common.js";
import { normalizeFormula } from "./formula.js";

export function normalizeStatus(raw) {
  const value = String(raw || "").toUpperCase();
  return STATUS_CYCLE.includes(value) ? value : "NEW";
}

export function baseProfile() {
  return {
    schema_version: PROFILE_SCHEMA_VERSION,
    case_progress: {},
    active_algorithm_by_case: {},
    custom_algorithms_by_case: {},
  };
}

export function normalizeProfile(raw) {
  const fallback = baseProfile();
  if (!raw || typeof raw !== "object") return fallback;
  if (Number(raw.schema_version) !== PROFILE_SCHEMA_VERSION) return fallback;

  if (raw.case_progress && typeof raw.case_progress === "object") {
    Object.entries(raw.case_progress).forEach(([caseKey, status]) => {
      if (!caseKey || typeof caseKey !== "string") return;
      fallback.case_progress[caseKey] = normalizeStatus(status);
    });
  }

  if (raw.active_algorithm_by_case && typeof raw.active_algorithm_by_case === "object") {
    Object.entries(raw.active_algorithm_by_case).forEach(([caseKey, algorithmId]) => {
      if (!caseKey || typeof caseKey !== "string") return;
      if (!algorithmId || typeof algorithmId !== "string") return;
      fallback.active_algorithm_by_case[caseKey] = String(algorithmId);
    });
  }

  if (raw.custom_algorithms_by_case && typeof raw.custom_algorithms_by_case === "object") {
    Object.entries(raw.custom_algorithms_by_case).forEach(([caseKey, algorithms]) => {
      if (!caseKey || typeof caseKey !== "string") return;
      if (!Array.isArray(algorithms)) return;

      const normalized = [];
      const seenFormula = new Set();
      algorithms.forEach((item) => {
        if (!item || typeof item !== "object") return;
        const id = String(item.id || "").trim();
        const formula = normalizeFormula(item.formula || "");
        if (!id || !formula) return;
        if (seenFormula.has(formula)) return;
        seenFormula.add(formula);
        normalized.push({
          id,
          name: String(item.name || formula).trim() || formula,
          formula,
          status: normalizeStatus(item.status || "NEW"),
          is_custom: true,
        });
      });

      if (normalized.length) {
        fallback.custom_algorithms_by_case[caseKey] = normalized;
      }
    });
  }

  return fallback;
}

export function loadProfileFromStorage() {
  try {
    const raw = localStorage.getItem(PROFILE_STORAGE_KEY);
    if (!raw) return baseProfile();
    return normalizeProfile(JSON.parse(raw));
  } catch {
    return baseProfile();
  }
}

export function saveProfile(profile) {
  try {
    localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(normalizeProfile(profile)));
  } catch {
    // no-op
  }
}

export function mergeProfile(base, incoming) {
  const merged = normalizeProfile(base);
  const source = normalizeProfile(incoming);

  Object.entries(source.case_progress).forEach(([caseKey, status]) => {
    merged.case_progress[caseKey] = status;
  });

  Object.entries(source.active_algorithm_by_case).forEach(([caseKey, algorithmId]) => {
    merged.active_algorithm_by_case[caseKey] = algorithmId;
  });

  Object.entries(source.custom_algorithms_by_case).forEach(([caseKey, incomingAlgorithms]) => {
    const current = Array.isArray(merged.custom_algorithms_by_case[caseKey])
      ? merged.custom_algorithms_by_case[caseKey]
      : [];

    const byFormula = new Map();
    current.forEach((item) => {
      const formula = normalizeFormula(item.formula || "");
      if (!formula) return;
      byFormula.set(formula, cloneObject(item));
    });

    incomingAlgorithms.forEach((item) => {
      const formula = normalizeFormula(item.formula || "");
      if (!formula) return;
      byFormula.set(formula, {
        ...cloneObject(item),
        formula,
        status: normalizeStatus(item.status),
        is_custom: true,
      });
    });

    merged.custom_algorithms_by_case[caseKey] = Array.from(byFormula.values());
  });

  return merged;
}

export function loadProgressSortMap() {
  const defaults = { F2L: false, OLL: false, PLL: false };
  try {
    const raw = localStorage.getItem(PROGRESS_SORT_STORAGE_KEY);
    if (!raw) return defaults;
    const parsed = JSON.parse(raw);
    Object.entries(parsed || {}).forEach(([group, enabled]) => {
      const normalized = String(group || "").trim().toUpperCase();
      if (normalized) {
        defaults[normalized] = Boolean(enabled);
      }
    });
    GROUPS.forEach((group) => {
      if (Object.prototype.hasOwnProperty.call(parsed || {}, group)) {
        defaults[group] = Boolean(parsed[group]);
      }
    });
  } catch {
    // no-op
  }
  return defaults;
}

export function saveProgressSortMap(map) {
  try {
    localStorage.setItem(PROGRESS_SORT_STORAGE_KEY, JSON.stringify(map));
  } catch {
    // no-op
  }
}

export function nextProgressStatus(status) {
  const normalized = String(status || "NEW").toUpperCase();
  const idx = STATUS_CYCLE.indexOf(normalized);
  if (idx < 0) return STATUS_CYCLE[0];
  return STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length];
}
