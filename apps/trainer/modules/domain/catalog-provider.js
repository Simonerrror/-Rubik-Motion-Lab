import { cloneObject } from "../utils/common.js";
import { normalizeFormula, normalizeMoveSteps } from "./formula.js";
import { buildLocalSandboxTimeline } from "./timeline-builder.js";
import { normalizeProfile, normalizeStatus } from "./profile-storage.js";

/**
 * @typedef {Object} CatalogProvider
 * @property {(group: string) => Array<Object>} listCases
 * @property {(caseKey: string) => Object|null} getCase
 * @property {(caseKey: string, status: string) => Object|null} setCaseProgress
 * @property {(caseKey: string, algorithmId: string) => Object|null} setActiveAlgorithm
 * @property {(caseKey: string, algorithmId: string) => {deleted: boolean, case: Object|null}} deleteAlgorithm
 * @property {(caseKey: string, formula: string, name: string, isActive: boolean) => {case: Object|null, algorithm: Object}} createCustomAlgorithm
 * @property {(caseKey: string, algorithmId?: string, formulaOverride?: string) => Object} getSandboxTimeline
 * @property {(profile: Object) => void} replaceProfile
 * @property {() => Object} getProfile
 */

/**
 * @param {Object} catalog
 * @param {Object} profile
 * @param {(nextProfile: Object) => void} onProfileCommit
 * @param {Map<string, Object>} timelineCache
 * @returns {CatalogProvider}
 */
export function createTrainerCatalogProvider(catalog, profile, onProfileCommit, timelineCache) {
  const cases = Array.isArray(catalog?.cases) ? cloneObject(catalog.cases) : [];
  const caseByKey = new Map(cases.map((item) => [String(item.case_key), item]));
  let profileState = normalizeProfile(profile);

  function commit(next) {
    profileState = normalizeProfile(next);
    if (typeof onProfileCommit === "function") {
      onProfileCommit(profileState);
    }
  }

  function customAlgorithms(caseKey) {
    const list = profileState.custom_algorithms_by_case[caseKey];
    return Array.isArray(list) ? list : [];
  }

  function canonicalAlgorithms(baseCase) {
    const algorithms = Array.isArray(baseCase?.algorithms) ? baseCase.algorithms : [];
    return algorithms.map((item) => ({
      ...cloneObject(item),
      formula: normalizeFormula(item.formula || ""),
      status: normalizeStatus(item.status || "NEW"),
      is_custom: Boolean(item.is_custom),
    }));
  }

  function resolveCase(caseKey) {
    const key = String(caseKey || "");
    const baseCase = caseByKey.get(key);
    if (!baseCase) return null;

    const canonical = canonicalAlgorithms(baseCase);
    const canonicalFormulaSet = new Set(canonical.map((item) => normalizeFormula(item.formula)));

    const mergedAlgorithms = [...canonical];
    const seenCustomFormula = new Set();

    customAlgorithms(key).forEach((item) => {
      const formula = normalizeFormula(item.formula || "");
      if (!formula) return;
      if (canonicalFormulaSet.has(formula)) return;
      if (seenCustomFormula.has(formula)) return;
      seenCustomFormula.add(formula);
      mergedAlgorithms.push({
        ...cloneObject(item),
        formula,
        status: normalizeStatus(item.status || "NEW"),
        is_custom: true,
      });
    });

    let activeAlgorithmId = String(profileState.active_algorithm_by_case[key] || "").trim();
    if (!activeAlgorithmId) {
      activeAlgorithmId = String(baseCase.active_algorithm_id || "").trim();
    }

    if (!mergedAlgorithms.some((item) => item.id === activeAlgorithmId)) {
      activeAlgorithmId = mergedAlgorithms[0]?.id || "";
    }

    const activeAlgorithm = mergedAlgorithms.find((item) => item.id === activeAlgorithmId) || null;

    return {
      ...cloneObject(baseCase),
      case_key: key,
      status: normalizeStatus(profileState.case_progress[key] || baseCase.status || "NEW"),
      algorithms: mergedAlgorithms,
      active_algorithm_id: activeAlgorithmId,
      active_formula: activeAlgorithm?.formula || "",
    };
  }

  function listCases(group) {
    return cases
      .filter((item) => String(item.group || "") === String(group || ""))
      .map((item) => resolveCase(item.case_key))
      .filter(Boolean);
  }

  function getCase(caseKey) {
    return resolveCase(caseKey);
  }

  function setCaseProgress(caseKey, status) {
    const key = String(caseKey || "").trim();
    if (!caseByKey.has(key)) return null;
    const next = normalizeProfile(profileState);
    next.case_progress[key] = normalizeStatus(status);
    commit(next);
    return resolveCase(key);
  }

  function setActiveAlgorithm(caseKey, algorithmId) {
    const key = String(caseKey || "").trim();
    const algorithm = String(algorithmId || "").trim();
    const caseData = resolveCase(key);
    if (!caseData) return null;
    if (!caseData.algorithms.some((item) => item.id === algorithm)) return caseData;

    const next = normalizeProfile(profileState);
    next.active_algorithm_by_case[key] = algorithm;
    commit(next);
    return resolveCase(key);
  }

  function deleteAlgorithm(caseKey, algorithmId) {
    const key = String(caseKey || "").trim();
    const target = String(algorithmId || "").trim();
    if (!key || !target) return { deleted: false, case: resolveCase(key) };

    const base = normalizeProfile(profileState);
    const current = Array.isArray(base.custom_algorithms_by_case[key])
      ? base.custom_algorithms_by_case[key]
      : [];
    const nextCustom = current.filter((item) => String(item.id || "") !== target);
    const deleted = nextCustom.length !== current.length;
    if (!deleted) {
      return { deleted: false, case: resolveCase(key) };
    }

    if (nextCustom.length) {
      base.custom_algorithms_by_case[key] = nextCustom;
    } else {
      delete base.custom_algorithms_by_case[key];
    }

    if (String(base.active_algorithm_by_case[key] || "") === target) {
      delete base.active_algorithm_by_case[key];
    }

    commit(base);
    const resolved = resolveCase(key);
    if (resolved?.active_algorithm_id === target) {
      setActiveAlgorithm(key, resolved.algorithms[0]?.id || "");
    }
    return { deleted: true, case: resolveCase(key) };
  }

  function createCustomAlgorithm(caseKey, formula, name, isActive) {
    const key = String(caseKey || "").trim();
    const caseData = resolveCase(key);
    if (!caseData) throw new Error("Case not found");

    const normalized = normalizeMoveSteps(formula || "");
    const normalizedFormulaText = normalized.formula;
    if (!normalizedFormulaText) {
      throw new Error("Formula is empty");
    }

    const canonicalMatch = caseData.algorithms.find((item) => normalizeFormula(item.formula) === normalizedFormulaText);
    if (canonicalMatch) {
      if (isActive) {
        setActiveAlgorithm(key, canonicalMatch.id);
      }
      return { case: resolveCase(key), algorithm: canonicalMatch };
    }

    const currentCustom = customAlgorithms(key);
    const existingCustom = currentCustom.find((item) => normalizeFormula(item.formula) === normalizedFormulaText);
    if (existingCustom) {
      if (isActive) {
        setActiveAlgorithm(key, existingCustom.id);
      }
      return { case: resolveCase(key), algorithm: existingCustom };
    }

    const next = normalizeProfile(profileState);
    const customList = Array.isArray(next.custom_algorithms_by_case[key]) ? next.custom_algorithms_by_case[key] : [];

    const customId = `${key}:custom:${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
    const customAlgorithm = {
      id: customId,
      name: String(name || normalizedFormulaText).trim() || normalizedFormulaText,
      formula: normalizedFormulaText,
      status: "NEW",
      is_custom: true,
    };

    customList.push(customAlgorithm);
    next.custom_algorithms_by_case[key] = customList;
    if (isActive) {
      next.active_algorithm_by_case[key] = customId;
    }
    commit(next);
    return { case: resolveCase(key), algorithm: customAlgorithm };
  }

  function getSandboxTimeline(caseKey, algorithmId, formulaOverride) {
    const key = String(caseKey || "").trim();
    const caseData = resolveCase(key);
    if (!caseData) throw new Error("Case not found");

    const requestedAlgorithmId = String(algorithmId || caseData.active_algorithm_id || "").trim();
    const algorithm = caseData.algorithms.find((item) => item.id === requestedAlgorithmId) || null;
    const overrideFormula = String(formulaOverride || "").trim();

    if (algorithm?.sandbox && !overrideFormula) {
      return cloneObject(algorithm.sandbox);
    }

    const baseSandbox =
      cloneObject(caseData.sandbox) || cloneObject(caseData.algorithms.find((item) => item.sandbox)?.sandbox) || null;
    if (!baseSandbox) {
      throw new Error("Sandbox source is unavailable");
    }

    const formula = overrideFormula || algorithm?.formula || "";
    if (!formula) {
      throw new Error("Formula is empty");
    }

    const cacheKey = `${key}|${requestedAlgorithmId || "raw"}|${normalizeFormula(formula)}`;
    if (timelineCache?.has(cacheKey)) {
      return cloneObject(timelineCache.get(cacheKey));
    }

    const timeline = buildLocalSandboxTimeline(baseSandbox, formula, caseData.group);
    timelineCache?.set(cacheKey, cloneObject(timeline));
    return timeline;
  }

  function replaceProfile(nextProfile) {
    commit(normalizeProfile(nextProfile));
  }

  function getProfile() {
    return normalizeProfile(profileState);
  }

  return {
    listCases,
    getCase,
    setCaseProgress,
    setActiveAlgorithm,
    deleteAlgorithm,
    createCustomAlgorithm,
    getSandboxTimeline,
    replaceProfile,
    getProfile,
  };
}
