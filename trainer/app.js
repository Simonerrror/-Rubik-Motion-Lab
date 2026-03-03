(() => {
  const GROUPS = ["F2L", "OLL", "PLL"];
  const PROFILE_STORAGE_KEY = "cards_trainer_profile_v1";
  const PROFILE_SCHEMA_VERSION = 1;
  const CATALOG_SCHEMA_VERSION = "trainer-catalog-v1";
  const CATALOG_URL = "./data/catalog-v1.json";
  const PROGRESS_SORT_STORAGE_KEY = "cards_progress_sort_by_group_v1";
  const STATUS_SORT_RANK = {
    IN_PROGRESS: 0,
    NEW: 1,
    LEARNED: 2,
  };
  const STATUS_CYCLE = ["NEW", "IN_PROGRESS", "LEARNED"];
  const RECOGNIZER_CACHE_BUSTER = `r${Date.now()}`;
  const SANDBOX_PLAYBACK_SPEEDS = [1, 1.5, 2];
  const DEFAULT_SANDBOX_PLAYBACK_CONFIG = {
    run_time_sec: 0.65,
    double_turn_multiplier: 1.7,
    inter_move_pause_ratio: 0.05,
    rate_func: "ease_in_out_sine",
  };
  const AUTO_MERGE_UD_PAIRS = new Set([
    "U|D'",
    "D'|U",
    "U'|D",
    "D|U'",
  ]);
  const POSITIVE_BASES = new Set(["R", "F", "D", "E", "S", "r", "f", "d", "x", "z"]);
  const FACE_TO_NORMAL = {
    U: [0, 0, 1],
    D: [0, 0, -1],
    R: [0, -1, 0],
    L: [0, 1, 0],
    F: [-1, 0, 0],
    B: [1, 0, 0],
  };
  const NORMAL_TO_FACE = {
    "0,0,1": "U",
    "0,0,-1": "D",
    "0,-1,0": "R",
    "0,1,0": "L",
    "-1,0,0": "F",
    "1,0,0": "B",
  };

  const state = {
    category: "PLL",
    cases: [],
    activeCaseKey: null,
    activeCase: null,
    catalog: null,
    provider: null,
    profile: null,
    progressSortByGroup: loadProgressSortMap(),

    sandboxData: null,
    sandboxPlayer: null,
    sandboxStepIndex: 0,
    sandboxTimelineProgress: 0,
    sandboxCursorStepIndex: 0,
    sandboxCursorStepProgress: 0,
    sandboxBusy: false,
    sandboxPlaybackActive: false,
    sandboxPlaybackToken: 0,
    sandboxPlaybackConfig: { ...DEFAULT_SANDBOX_PLAYBACK_CONFIG },
    sandboxPlaybackSpeed: 1,
    sandboxTimelineRafPending: false,
    sandboxPendingTimelineProgress: null,
    sandboxScrubbing: false,
    sandboxWasPlayingBeforeScrub: false,

    activeDisplayMode: "algorithm",
    activeDisplayFormula: "",

    customTimelineCache: new Map(),
  };

  const DOM = {
    catalog: document.getElementById("catalog-container"),
    sortProgressToggle: document.getElementById("sort-progress-toggle"),
    mName: document.getElementById("m-name"),
    mProb: document.getElementById("m-prob"),
    mCaseCode: document.getElementById("m-case-code"),
    sandboxCanvas: document.getElementById("sandbox-canvas"),
    sandboxToStartBtn: document.getElementById("sandbox-to-start-btn"),
    sandboxPrevBtn: document.getElementById("sandbox-prev-btn"),
    sandboxPlayPauseBtn: document.getElementById("sandbox-play-pause-btn"),
    sandboxNextBtn: document.getElementById("sandbox-next-btn"),
    sandboxSpeedButtons: Array.from(document.querySelectorAll(".sandbox-speed-btn")),
    sandboxTimelineSlider: document.getElementById("sandbox-timeline-slider"),
    sandboxTimelineLabel: document.getElementById("sandbox-timeline-label"),
    sandboxStepLabel: document.getElementById("sandbox-step-label"),
    sandboxOverlayTitle: document.getElementById("sandbox-overlay-title"),
    sandboxOverlaySubtitle: document.getElementById("sandbox-overlay-subtitle"),
    sandboxOverlayTopImage: document.getElementById("sandbox-overlay-top-image"),
    sandboxOverlayFormula: document.getElementById("sandbox-overlay-formula"),
    mStatusGroup: document.getElementById("m-status-group"),
    mAlgoList: document.getElementById("m-algo-list"),
    activeAlgoDisplay: document.getElementById("active-algo-display"),
    toast: document.getElementById("toast"),

    exportProfileBtn: document.getElementById("export-profile-btn"),
    importProfileBtn: document.getElementById("import-profile-btn"),
    profileModal: document.getElementById("profile-modal"),
    profileData: document.getElementById("profile-data"),
    profileMsg: document.getElementById("profile-msg"),
    profileApplyBtn: document.getElementById("profile-apply-btn"),
    profileCopyBtn: document.getElementById("profile-copy-btn"),
    profileCloseBtn: document.getElementById("profile-close-btn"),
  };

  let profileModalMode = "export";

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function sanitizeForTestId(raw) {
    return String(raw || "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "item";
  }

  function normalizeStatus(raw) {
    const value = String(raw || "").toUpperCase();
    return STATUS_CYCLE.includes(value) ? value : "NEW";
  }

  function normalizeFormula(raw) {
    return String(raw || "")
      .replace(/\s*\+\s*/g, "+")
      .trim()
      .replace(/\s+/g, " ");
  }

  function cloneObject(value) {
    if (Array.isArray(value)) return value.map(cloneObject);
    if (!value || typeof value !== "object") return value;
    const out = {};
    Object.entries(value).forEach(([key, val]) => {
      out[key] = cloneObject(val);
    });
    return out;
  }

  function loadProgressSortMap() {
    const defaults = { F2L: false, OLL: false, PLL: false };
    try {
      const raw = localStorage.getItem(PROGRESS_SORT_STORAGE_KEY);
      if (!raw) return defaults;
      const parsed = JSON.parse(raw);
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

  function saveProgressSortMap(map) {
    try {
      localStorage.setItem(PROGRESS_SORT_STORAGE_KEY, JSON.stringify(map));
    } catch {
      // no-op
    }
  }

  function showToast(message) {
    DOM.toast.textContent = String(message || "");
    DOM.toast.classList.add("show");
    window.clearTimeout(state._toastTimer);
    state._toastTimer = window.setTimeout(() => {
      DOM.toast.classList.remove("show");
    }, 1800);
  }

  function baseProfile() {
    return {
      schema_version: PROFILE_SCHEMA_VERSION,
      case_progress: {},
      active_algorithm_by_case: {},
      custom_algorithms_by_case: {},
    };
  }

  function normalizeProfile(raw) {
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

  function loadProfileFromStorage() {
    try {
      const raw = localStorage.getItem(PROFILE_STORAGE_KEY);
      if (!raw) return baseProfile();
      return normalizeProfile(JSON.parse(raw));
    } catch {
      return baseProfile();
    }
  }

  function saveProfile(profile) {
    try {
      localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(normalizeProfile(profile)));
    } catch {
      // no-op
    }
  }

  function mergeProfile(base, incoming) {
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

  function bytesToBase64Url(bytes) {
    const chunk = 0x8000;
    let binary = "";
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
    }
    return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  }

  function base64UrlToBytes(raw) {
    const normalized = String(raw || "")
      .trim()
      .replace(/-/g, "+")
      .replace(/_/g, "/");
    const pad = normalized.length % 4;
    const padded = normalized + (pad ? "=".repeat(4 - pad) : "");
    const binary = atob(padded);
    const out = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      out[i] = binary.charCodeAt(i);
    }
    return out;
  }

  async function exportTrainerProfile(payload) {
    const json = JSON.stringify(normalizeProfile(payload));
    const bytes = new TextEncoder().encode(json);
    if (typeof CompressionStream === "undefined") {
      throw new Error("CompressionStream is unavailable in this browser");
    }
    const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream("gzip"));
    const buffer = await new Response(stream).arrayBuffer();
    return bytesToBase64Url(new Uint8Array(buffer));
  }

  async function importTrainerProfile(raw) {
    const value = String(raw || "").trim();
    if (!value) {
      throw new Error("Profile payload is empty");
    }

    if (typeof DecompressionStream === "undefined") {
      throw new Error("DecompressionStream is unavailable in this browser");
    }

    let bytes;
    try {
      bytes = base64UrlToBytes(value);
    } catch (error) {
      throw new Error(`Invalid profile encoding: ${String(error.message || error)}`);
    }

    try {
      const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
      const text = await new Response(stream).text();
      const parsed = JSON.parse(text);
      if (!parsed || typeof parsed !== "object") {
        throw new Error("Profile JSON must be an object");
      }
      if (Number(parsed.schema_version) !== PROFILE_SCHEMA_VERSION) {
        throw new Error(`Unsupported schema_version: ${String(parsed.schema_version)}`);
      }
      return normalizeProfile(parsed);
    } catch (error) {
      throw new Error(`Invalid profile payload: ${String(error.message || error)}`);
    }
  }

  function parseMove(rawMove) {
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

  function splitMove(move) {
    const token = String(move || "").trim();
    if (!token) throw new Error("Empty move token");

    if (token.endsWith("'") || token.endsWith("2")) {
      return [token.slice(0, -1), token.slice(-1)];
    }
    return [token, ""];
  }

  function moveAxis(base) {
    if (["F", "B", "S", "f", "b", "z"].includes(base)) return "x";
    if (["U", "D", "E", "u", "d", "y"].includes(base)) return "z";
    if (["L", "R", "M", "l", "r", "x"].includes(base)) return "y";
    return "";
  }

  function moveSelector(base) {
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

  function moveTurns(base, modifier) {
    let turns = POSITIVE_BASES.has(base) ? 1 : -1;
    if (modifier === "'") turns *= -1;
    if (modifier === "2") turns *= 2;
    return turns;
  }

  function rotateVec(vec, axis, direction) {
    const [x, y, z] = vec;
    if (axis === "x") {
      return direction > 0 ? [x, -z, y] : [x, z, -y];
    }
    if (axis === "y") {
      return direction > 0 ? [z, y, -x] : [-z, y, x];
    }
    if (axis === "z") {
      return direction > 0 ? [-y, x, z] : [y, -x, z];
    }
    return [x, y, z];
  }

  function parseFormulaSteps(formula) {
    const normalized = normalizeFormula(formula);
    if (!normalized) throw new Error("Formula is empty");

    const tokens = normalized.split(/\s+/).filter(Boolean);
    const steps = [];

    tokens.forEach((token) => {
      const parts = token.split("+").map((part) => part.trim()).filter(Boolean);
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

  function mergeParallelUdPairs(steps) {
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

  function invertMove(move) {
    if (move.endsWith("'")) return move.slice(0, -1);
    if (move.endsWith("2")) return move;
    return `${move}'`;
  }

  function normalizeMoveSteps(formula) {
    const parsed = parseFormulaSteps(formula);
    const merged = mergeParallelUdPairs(parsed);
    return {
      steps: merged,
      movesFlat: merged.flat(),
      highlights: merged.map((step) => step.join("+")),
      formula: merged.map((step) => step.join("+")).join(" "),
    };
  }

  function buildCubiesFromState(stateString, stateSlots) {
    const cubies = new Map();
    const source = String(stateString || "");

    (stateSlots || []).forEach((slot, idx) => {
      const position = slot?.position;
      const face = String(slot?.face || "");
      if (!Array.isArray(position) || position.length < 3 || !face) return;
      const key = `${position[0]},${position[1]},${position[2]}`;
      const color = source[idx] || face;
      if (!cubies.has(key)) {
        cubies.set(key, {
          pos: [position[0], position[1], position[2]],
          faces: {},
        });
      }
      cubies.get(key).faces[face] = color;
    });

    return cubies;
  }

  function cubiesToStateString(cubies, stateSlots) {
    return (stateSlots || [])
      .map((slot) => {
        const position = slot?.position;
        const face = String(slot?.face || "");
        if (!Array.isArray(position) || position.length < 3 || !face) return face;
        const key = `${position[0]},${position[1]},${position[2]}`;
        const cubie = cubies.get(key);
        if (!cubie) return face;
        return String(cubie.faces[face] || face);
      })
      .join("");
  }

  function applyMoveToCubies(cubies, token) {
    const [base, modifier] = splitMove(token);
    const axis = moveAxis(base);
    const selector = moveSelector(base);
    const turns = moveTurns(base, modifier);
    if (!axis || !selector || !Number.isFinite(turns) || turns === 0) {
      return cubies;
    }

    let current = cubies;
    let remaining = Math.abs(turns);
    const direction = turns > 0 ? 1 : -1;

    while (remaining > 0) {
      const next = new Map();
      current.forEach((cubie) => {
        let nextPos = [...cubie.pos];
        let nextFaces = { ...cubie.faces };

        if (selector(cubie.pos)) {
          nextPos = rotateVec(cubie.pos, axis, direction);
          const rotatedFaces = {};
          Object.entries(cubie.faces).forEach(([face, color]) => {
            const normal = FACE_TO_NORMAL[face];
            if (!normal) {
              rotatedFaces[face] = color;
              return;
            }
            const rotated = rotateVec(normal, axis, direction);
            const mappedFace = NORMAL_TO_FACE[rotated.join(",")] || face;
            rotatedFaces[mappedFace] = color;
          });
          nextFaces = rotatedFaces;
        }

        const key = `${nextPos[0]},${nextPos[1]},${nextPos[2]}`;
        next.set(key, {
          pos: nextPos,
          faces: nextFaces,
        });
      });
      current = next;
      remaining -= 1;
    }

    return current;
  }

  function buildLocalSandboxTimeline(baseSandbox, formula, group) {
    const normalizedFormula = normalizeMoveSteps(formula || "");
    const moveSteps = normalizedFormula.steps.map((step) => step.map((move) => String(move)));
    const stateSlots = Array.isArray(baseSandbox?.state_slots) ? cloneObject(baseSandbox.state_slots) : [];
    const initialState = String(baseSandbox?.initial_state || "");
    const playbackConfig = normalizeSandboxPlaybackConfig(baseSandbox?.playback_config);

    let cubies = buildCubiesFromState(initialState, stateSlots);
    const states = [initialState || cubiesToStateString(cubies, stateSlots)];

    moveSteps.forEach((step) => {
      step.forEach((move) => {
        cubies = applyMoveToCubies(cubies, move);
      });
      states.push(cubiesToStateString(cubies, stateSlots));
    });

    return {
      formula: normalizedFormula.formula,
      group: String(group || baseSandbox?.group || ""),
      move_steps: moveSteps,
      moves_flat: normalizedFormula.movesFlat,
      initial_state: states[0] || "",
      states_by_step: states,
      highlight_by_step: normalizedFormula.highlights,
      state_slots: stateSlots,
      playback_config: playbackConfig,
    };
  }

  function normalizeSandboxPlaybackConfig(raw) {
    const config = { ...DEFAULT_SANDBOX_PLAYBACK_CONFIG };
    if (!raw || typeof raw !== "object") return config;
    const runTime = Number(raw.run_time_sec);
    const doubleMultiplier = Number(raw.double_turn_multiplier);
    const pauseRatio = Number(raw.inter_move_pause_ratio);
    const rateFunc = String(raw.rate_func || "").trim();
    if (Number.isFinite(runTime) && runTime > 0) config.run_time_sec = runTime;
    if (Number.isFinite(doubleMultiplier) && doubleMultiplier > 0) config.double_turn_multiplier = doubleMultiplier;
    if (Number.isFinite(pauseRatio) && pauseRatio >= 0) config.inter_move_pause_ratio = pauseRatio;
    if (rateFunc) config.rate_func = rateFunc;
    return config;
  }

  function tokenizeFormula(formula) {
    return String(formula || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
  }

  function nextProgressStatus(status) {
    const normalized = String(status || "NEW").toUpperCase();
    const idx = STATUS_CYCLE.indexOf(normalized);
    if (idx < 0) return STATUS_CYCLE[0];
    return STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length];
  }

  function createTrainerCatalogProvider(catalog, profile, onProfileCommit) {
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
      const customList = Array.isArray(next.custom_algorithms_by_case[key])
        ? next.custom_algorithms_by_case[key]
        : [];

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
        cloneObject(caseData.sandbox) ||
        cloneObject(caseData.algorithms.find((item) => item.sandbox)?.sandbox) ||
        null;
      if (!baseSandbox) {
        throw new Error("Sandbox source is unavailable");
      }

      const formula = overrideFormula || algorithm?.formula || "";
      if (!formula) {
        throw new Error("Formula is empty");
      }

      const cacheKey = `${key}|${requestedAlgorithmId || "raw"}|${normalizeFormula(formula)}`;
      if (state.customTimelineCache.has(cacheKey)) {
        return cloneObject(state.customTimelineCache.get(cacheKey));
      }

      const timeline = buildLocalSandboxTimeline(baseSandbox, formula, caseData.group);
      state.customTimelineCache.set(cacheKey, cloneObject(timeline));
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

  function tileTitle(item) {
    return String(
      item.tile_title ||
        item.display_name ||
        item.title ||
        item.case_code ||
        (item.case_number != null ? `${item.group} #${item.case_number}` : "Case")
    );
  }

  function detailTitle(item) {
    return String(
      item.detail_title ||
        item.title ||
        item.display_name ||
        (item.case_number != null ? `${item.group} #${item.case_number}` : item.case_code || "Case")
    );
  }

  function caseShortLabel(item) {
    if (item.case_number != null) return `${item.group} #${item.case_number}`;
    return item.case_code || "-";
  }

  function groupBySubgroup(items) {
    return items.reduce((acc, item) => {
      const key = item.subgroup_title || `${item.group} Cases`;
      if (!acc[key]) acc[key] = [];
      acc[key].push(item);
      return acc;
    }, {});
  }

  function setActiveTab(category) {
    document.querySelectorAll(".nav-tab").forEach((tab) => {
      tab.classList.toggle("active", String(tab.dataset.category || "").toUpperCase() === category);
    });
    syncProgressSortToggle();
  }

  function syncProgressSortToggle() {
    if (!DOM.sortProgressToggle) return;
    DOM.sortProgressToggle.checked = Boolean(state.progressSortByGroup[state.category]);
  }

  function caseSortRank(item) {
    const status = String(item?.status || "NEW");
    return STATUS_SORT_RANK[status] ?? 1;
  }

  function sortCasesForCatalog(cases) {
    const sorted = [...cases];
    if (!state.progressSortByGroup[state.category]) return sorted;
    sorted.sort((a, b) => {
      const rankDiff = caseSortRank(a) - caseSortRank(b);
      if (rankDiff !== 0) return rankDiff;

      const aNum = Number.isFinite(Number(a.case_number)) ? Number(a.case_number) : Number.MAX_SAFE_INTEGER;
      const bNum = Number.isFinite(Number(b.case_number)) ? Number(b.case_number) : Number.MAX_SAFE_INTEGER;
      if (aNum !== bNum) return aNum - bNum;

      const codeA = String(a.case_code || "");
      const codeB = String(b.case_code || "");
      return codeA.localeCompare(codeB);
    });
    return sorted;
  }

  function appendRecognizerPreview(container, item) {
    if (item.recognizer_url) {
      const img = document.createElement("img");
      const sep = item.recognizer_url.includes("?") ? "&" : "?";
      img.src = `${item.recognizer_url}${sep}v=${RECOGNIZER_CACHE_BUSTER}`;
      img.alt = `${item.case_code} recognizer`;
      container.appendChild(img);
      return;
    }
    container.textContent = "No image";
    container.classList.add("catalog-preview-empty");
  }

  function sandboxOverlayFormula(caseItem) {
    const active = String(state.activeDisplayFormula || "").trim();
    if (state.activeDisplayMode === "custom" && active) return active;
    return active || String(caseItem?.active_formula || "").trim();
  }

  function formatSandboxFormulaOverlay(formula) {
    const allMoves = tokenizeFormula(formula);
    if (!allMoves.length) return "";
    const maxMoves = 24;
    const rowSize = 8;
    const truncated = allMoves.length > maxMoves;
    const moves = allMoves.slice(0, maxMoves);
    const rows = [];
    for (let index = 0; index < moves.length; index += rowSize) {
      rows.push(moves.slice(index, index + rowSize).join(" "));
    }
    if (truncated && rows.length) {
      rows[rows.length - 1] = `${rows[rows.length - 1]} ...`;
    }
    return rows.join("\n");
  }

  function updateSandboxOverlay(caseItem = currentCase()) {
    if (DOM.sandboxOverlayTitle) {
      DOM.sandboxOverlayTitle.textContent = caseItem ? detailTitle(caseItem) : "Select Case";
    }
    if (DOM.sandboxOverlaySubtitle) {
      DOM.sandboxOverlaySubtitle.textContent = caseItem
        ? [caseShortLabel(caseItem), caseItem.subgroup_title].filter(Boolean).join(" · ")
        : "-";
    }
    if (DOM.sandboxOverlayFormula) {
      const formula = caseItem ? sandboxOverlayFormula(caseItem) : "";
      const formatted = formatSandboxFormulaOverlay(formula);
      DOM.sandboxOverlayFormula.textContent = formatted || "-";
      DOM.sandboxOverlayFormula.title = formula || "";
    }
    if (DOM.sandboxOverlayTopImage) {
      const recognizerUrl = caseItem ? String(caseItem.recognizer_url || "").trim() : "";
      if (recognizerUrl) {
        const sep = recognizerUrl.includes("?") ? "&" : "?";
        DOM.sandboxOverlayTopImage.src = `${recognizerUrl}${sep}v=${RECOGNIZER_CACHE_BUSTER}`;
        DOM.sandboxOverlayTopImage.style.visibility = "visible";
      } else {
        DOM.sandboxOverlayTopImage.removeAttribute("src");
        DOM.sandboxOverlayTopImage.style.visibility = "hidden";
      }
    }
  }

  function currentCase() {
    return state.activeCase;
  }

  function refreshCaseCache() {
    if (!state.provider) {
      state.cases = [];
      state.activeCase = null;
      state.activeCaseKey = null;
      return;
    }

    state.cases = state.provider.listCases(state.category);
    if (!state.cases.length) {
      state.activeCaseKey = null;
      state.activeCase = null;
      return;
    }

    if (!state.activeCaseKey || !state.cases.some((item) => item.case_key === state.activeCaseKey)) {
      state.activeCaseKey = state.cases[0].case_key;
    }

    state.activeCase = state.provider.getCase(state.activeCaseKey);
  }

  function appendCatalogCard(grid, item) {
    const card = document.createElement("article");
    card.className = "catalog-card";
    card.setAttribute("data-testid", `case-card-${sanitizeForTestId(item.case_key)}`);
    if (item.case_key === state.activeCaseKey) card.classList.add("active");

    const status = String(item.status || "NEW");
    card.innerHTML = `
      <button class="status-dot ${status}" type="button" title="Cycle status" aria-label="Cycle status"></button>
      <div class="catalog-preview"></div>
      <div class="tile-title">${tileTitle(item)}</div>
    `;

    const preview = card.querySelector(".catalog-preview");
    appendRecognizerPreview(preview, item);

    const statusDot = card.querySelector(".status-dot");
    if (statusDot) {
      statusDot.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        void updateCatalogCaseProgress(item.case_key, item.status);
      });
    }

    card.addEventListener("click", () => {
      void selectCase(item.case_key);
    });

    grid.appendChild(card);
  }

  function renderCatalog() {
    DOM.catalog.innerHTML = "";
    if (!state.cases.length) {
      const empty = document.createElement("div");
      empty.className = "catalog-empty";
      empty.textContent = "No cases in this group.";
      DOM.catalog.appendChild(empty);
      return;
    }

    if (state.progressSortByGroup[state.category]) {
      const grid = document.createElement("div");
      grid.className = "catalog-grid";
      sortCasesForCatalog(state.cases).forEach((item) => {
        appendCatalogCard(grid, item);
      });
      DOM.catalog.appendChild(grid);
      return;
    }

    const grouped = groupBySubgroup(state.cases);
    Object.entries(grouped).forEach(([subgroup, cases]) => {
      const section = document.createElement("section");
      section.className = "subgroup-section";

      const title = document.createElement("div");
      title.className = "subgroup-title";
      title.textContent = subgroup;
      section.appendChild(title);

      const grid = document.createElement("div");
      grid.className = "catalog-grid";

      sortCasesForCatalog(cases).forEach((item) => {
        appendCatalogCard(grid, item);
      });

      section.appendChild(grid);
      DOM.catalog.appendChild(section);
    });
  }

  function renderActiveAlgorithmDisplay(formula) {
    DOM.activeAlgoDisplay.innerHTML = "";
    const timelineSteps = Array.isArray(state.sandboxData?.highlight_by_step)
      ? state.sandboxData.highlight_by_step.filter((step) => String(step || "").trim())
      : [];

    if (timelineSteps.length) {
      const chunk = 8;
      for (let offset = 0; offset < timelineSteps.length; offset += chunk) {
        const row = document.createElement("div");
        row.className = "algo-line";
        timelineSteps.slice(offset, offset + chunk).forEach((stepLabel, localIndex) => {
          const stepIndex = offset + localIndex;
          const tile = document.createElement("button");
          const inverse = String(stepLabel).includes("'");
          tile.className = `move-tile ${inverse ? "inverse" : "base"}`;
          tile.type = "button";
          tile.textContent = stepLabel;
          tile.setAttribute("data-step-index", String(stepIndex));
          tile.title = `Go to step ${stepIndex + 1}`;
          tile.setAttribute("aria-label", `Go to step ${stepIndex + 1}`);
          tile.addEventListener("click", () => {
            stopSandboxPlayback({ silent: true, forceUpdate: true });
            sandboxSetStep(stepIndex);
          });
          row.appendChild(tile);
        });
        DOM.activeAlgoDisplay.appendChild(row);
      }
      updateActiveAlgorithmStepHighlight();
      return;
    }

    const moves = tokenizeFormula(formula);
    if (!moves.length) {
      DOM.activeAlgoDisplay.innerHTML = '<div class="algo-placeholder">No algorithm selected</div>';
      return;
    }

    const first = moves.slice(0, 8);
    const second = moves.slice(8);
    const lines = [first];
    if (second.length) lines.push(second);

    lines.forEach((lineMoves) => {
      const row = document.createElement("div");
      row.className = "algo-line";
      lineMoves.forEach((move) => {
        const tile = document.createElement("span");
        const inverse = move.includes("'");
        tile.className = `move-tile ${inverse ? "inverse" : "base"}`;
        tile.textContent = move;
        row.appendChild(tile);
      });
      DOM.activeAlgoDisplay.appendChild(row);
    });

    updateActiveAlgorithmStepHighlight();
  }

  function setActiveDisplayFormula(formula, mode = "algorithm") {
    state.activeDisplayMode = mode;
    state.activeDisplayFormula = String(formula || "").trim();
    renderActiveAlgorithmDisplay(state.activeDisplayFormula);
    updateSandboxOverlay(currentCase());
  }

  function setDetailsDisabled() {
    DOM.mName.textContent = "Select Case";
    DOM.mCaseCode.textContent = "-";
    DOM.mProb.textContent = "Probability: n/a";
    DOM.mStatusGroup.querySelectorAll(".status-btn[data-status]").forEach((btn) => {
      btn.classList.remove("active");
      btn.disabled = true;
    });
    DOM.mAlgoList.innerHTML = '<div class="algo-empty">Select case to manage algorithms.</div>';
    setActiveDisplayFormula("", "algorithm");
    resetSandboxData();
    updateSandboxOverlay(null);
  }

  function updateDetailsPaneState() {
    const c = currentCase();
    if (!c) {
      setDetailsDisabled();
      return;
    }

    DOM.mName.textContent = detailTitle(c);
    DOM.mProb.textContent = `Probability: ${c.probability_text || "n/a"}`;
    DOM.mCaseCode.textContent = [caseShortLabel(c), c.subgroup_title].filter(Boolean).join(" · ");

    DOM.mStatusGroup.querySelectorAll(".status-btn[data-status]").forEach((btn) => {
      btn.disabled = false;
      btn.classList.toggle("active", btn.dataset.status === c.status);
    });

    const lockCustomPreview = state.activeDisplayMode === "custom" && isCustomFormulaInputFocused();
    if (!lockCustomPreview) {
      setActiveDisplayFormula(c.active_formula || "", "algorithm");
    }

    renderAlgorithmsList(c);
    updateSandboxOverlay(c);
  }

  function renderAlgorithmsList(c) {
    const prevInput = DOM.mAlgoList.querySelector("#custom-formula-input");
    const prevValue = prevInput ? String(prevInput.value || "") : "";
    const prevFocused = prevInput ? document.activeElement === prevInput : false;
    const prevSelectionStart = prevInput && prevInput.selectionStart != null ? prevInput.selectionStart : null;
    const prevSelectionEnd = prevInput && prevInput.selectionEnd != null ? prevInput.selectionEnd : null;

    DOM.mAlgoList.innerHTML = "";

    (c.algorithms || []).forEach((algo) => {
      const activeClass = algo.id === c.active_algorithm_id ? "algo-option-active" : "algo-option-inactive";
      const option = document.createElement("label");
      option.className = `algo-option ${activeClass}`;
      const checked = algo.id === c.active_algorithm_id ? "checked" : "";
      const escapedFormula = (algo.formula || "(empty)").replace(/"/g, "&quot;");
      const algoTestId = sanitizeForTestId(algo.id);
      option.innerHTML = `
        <div class="algo-main">
          <input type="radio" name="algo_sel" value="${algo.id}" ${checked} class="algo-radio" data-testid="algo-radio-${algoTestId}">
          <code>${escapedFormula}</code>
        </div>
        ${algo.is_custom ? `<button class="algo-delete-btn" data-action="delete" data-testid="delete-algo-${algoTestId}" type="button">Delete</button>` : ""}
      `;

      option.querySelector("input")?.addEventListener("change", async () => {
        try {
          hardResetSandboxOnSwitch({ clearData: true });
          state.provider.setActiveAlgorithm(c.case_key, algo.id);
          refreshCaseCache();
          state.activeCase = state.provider.getCase(c.case_key);
          setActiveDisplayFormula(algo.formula || "", "algorithm");
          await loadSandboxForCurrentCase();
          renderCatalog();
          updateDetailsPaneState();
          showToast("Active algorithm updated");
        } catch (error) {
          showToast(String(error.message || error));
        }
      });

      const deleteBtn = option.querySelector("[data-action='delete']");
      if (deleteBtn) {
        deleteBtn.addEventListener("click", async (event) => {
          event.preventDefault();
          event.stopPropagation();
          try {
            hardResetSandboxOnSwitch({ clearData: true });
            const payload = state.provider.deleteAlgorithm(c.case_key, algo.id);
            if (!payload.deleted) {
              showToast("Only custom algorithms can be deleted");
              return;
            }
            refreshCaseCache();
            state.activeCase = state.provider.getCase(c.case_key);
            await loadSandboxForCurrentCase();
            renderCatalog();
            updateDetailsPaneState();
            showToast("Algorithm deleted");
          } catch (error) {
            showToast(String(error.message || error));
          }
        });
      }

      DOM.mAlgoList.appendChild(option);
    });

    const customWrap = document.createElement("div");
    customWrap.className = "custom-algo-form";
    customWrap.innerHTML = `
      <input id="custom-formula-input" data-testid="custom-formula-input" type="text" placeholder="Enter custom algorithm..." class="custom-formula-input" />
      <button id="custom-formula-apply" data-testid="custom-formula-apply" type="button" class="custom-formula-apply">Use</button>
    `;

    const input = customWrap.querySelector("#custom-formula-input");
    const applyBtn = customWrap.querySelector("#custom-formula-apply");

    input.value = prevValue;
    if (prevFocused) {
      input.focus();
      if (prevSelectionStart != null && prevSelectionEnd != null) {
        input.setSelectionRange(prevSelectionStart, prevSelectionEnd);
      }
    }

    const submitCustom = async () => {
      const formula = String(input.value || "").trim();
      if (!formula) {
        showToast("Formula is empty");
        return;
      }
      try {
        hardResetSandboxOnSwitch({ clearData: true });
        const result = state.provider.createCustomAlgorithm(c.case_key, formula, "", true);
        refreshCaseCache();
        state.activeCase = state.provider.getCase(c.case_key);
        setActiveDisplayFormula(result.algorithm?.formula || formula, "algorithm");
        await loadSandboxForCurrentCase();
        renderCatalog();
        updateDetailsPaneState();
      } catch (error) {
        showToast(String(error.message || error));
      }
    };

    applyBtn.addEventListener("click", () => {
      void submitCustom();
    });

    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        void submitCustom();
      }
    });

    input.addEventListener("input", () => {
      const liveFormula = String(input.value || "");
      setActiveDisplayFormula(liveFormula, "custom");
    });

    input.addEventListener("blur", () => {
      const activeCase = currentCase();
      if (!activeCase) return;
      if (!String(input.value || "").trim()) {
        setActiveDisplayFormula(activeCase.active_formula || "", "algorithm");
      }
    });

    DOM.mAlgoList.appendChild(customWrap);
  }

  function isCustomFormulaInputFocused() {
    const input = DOM.mAlgoList.querySelector("#custom-formula-input");
    return Boolean(input) && document.activeElement === input;
  }

  async function updateCatalogCaseProgress(caseKey, currentStatus) {
    if (!state.provider) return;
    const nextStatus = nextProgressStatus(currentStatus);
    state.provider.setCaseProgress(caseKey, nextStatus);
    refreshCaseCache();
    renderCatalog();
    updateDetailsPaneState();
  }

  async function selectCase(caseKey) {
    if (!state.provider) return;
    hardResetSandboxOnSwitch({ clearData: true });
    state.activeCaseKey = caseKey;
    state.activeCase = state.provider.getCase(caseKey);
    state.activeDisplayMode = "algorithm";
    state.activeDisplayFormula = state.activeCase?.active_formula || "";
    await loadSandboxForCurrentCase();
    refreshCaseCache();
    renderCatalog();
    updateDetailsPaneState();
  }

  async function loadCatalog() {
    refreshCaseCache();
    if (!state.cases.length) {
      setDetailsDisabled();
      renderCatalog();
      return;
    }

    if (!state.activeCaseKey || !state.cases.some((item) => item.case_key === state.activeCaseKey)) {
      state.activeCaseKey = state.cases[0].case_key;
    }

    state.activeCase = state.provider.getCase(state.activeCaseKey);
    await loadSandboxForCurrentCase();
    refreshCaseCache();
    renderCatalog();
    updateDetailsPaneState();
  }

  function stopSandboxPlayback(options = {}) {
    const hadPlayback = state.sandboxPlaybackActive;
    state.sandboxPlaybackActive = false;
    state.sandboxPlaybackToken += 1;
    if (!options.silent && (hadPlayback || options.forceUpdate)) {
      updateSandboxControls();
    }
  }

  function hardResetSandboxOnSwitch(options = {}) {
    const clearData = options.clearData !== false;
    stopSandboxPlayback({ silent: true, forceUpdate: true });
    if (clearData) {
      state.sandboxData = null;
    }
    state.sandboxStepIndex = 0;
    state.sandboxTimelineProgress = 0;
    state.sandboxCursorStepIndex = 0;
    state.sandboxCursorStepProgress = 0;
    state.sandboxScrubbing = false;
    state.sandboxWasPlayingBeforeScrub = false;
    state.sandboxTimelineRafPending = false;
    state.sandboxPendingTimelineProgress = null;
    state.sandboxBusy = false;
    state.sandboxPlaybackConfig = { ...DEFAULT_SANDBOX_PLAYBACK_CONFIG };
    if (state.sandboxPlayer) {
      state.sandboxPlayer.setSlots([]);
      if (state.sandboxPlayer.setStickerlessTopMask) {
        state.sandboxPlayer.setStickerlessTopMask(false);
      }
      state.sandboxPlayer.setState("");
    }
    updateSandboxControls();
  }

  function setSandboxPlaybackSpeed(rawSpeed) {
    const parsed = Number(rawSpeed);
    const next = SANDBOX_PLAYBACK_SPEEDS.includes(parsed) ? parsed : 1;
    state.sandboxPlaybackSpeed = next;
    updateSandboxControls();
  }

  function sleepWithToken(delayMs, token) {
    const ms = Math.max(0, Math.round(delayMs));
    if (!ms) {
      return Promise.resolve(state.sandboxPlaybackToken === token);
    }
    return new Promise((resolve) => {
      window.setTimeout(() => {
        resolve(state.sandboxPlaybackToken === token);
      }, ms);
    });
  }

  function isDoubleTurnMove(move) {
    return /2'?$/.test(String(move || "").trim());
  }

  function sandboxStepDurationMs(stepMoves) {
    const cfg = state.sandboxPlaybackConfig || DEFAULT_SANDBOX_PLAYBACK_CONFIG;
    const speed = state.sandboxPlaybackSpeed || 1;
    const step = Array.isArray(stepMoves) ? stepMoves : [];
    const allDoubleTurns = step.length > 0 && step.every(isDoubleTurnMove);
    const runTimeSec = allDoubleTurns
      ? cfg.run_time_sec * cfg.double_turn_multiplier
      : cfg.run_time_sec;
    return Math.max(80, Math.round((runTimeSec * 1000) / speed));
  }

  function sandboxInterMovePauseMs() {
    const cfg = state.sandboxPlaybackConfig || DEFAULT_SANDBOX_PLAYBACK_CONFIG;
    const speed = state.sandboxPlaybackSpeed || 1;
    const pauseSec = (cfg.run_time_sec * cfg.inter_move_pause_ratio) / speed;
    return Math.max(0, Math.round(pauseSec * 1000));
  }

  function currentSandboxStepCount() {
    const steps = state.sandboxData?.move_steps;
    return Array.isArray(steps) ? steps.length : 0;
  }

  function normalizeTimelineProgress(rawProgress) {
    const total = currentSandboxStepCount();
    const numeric = Number(rawProgress);
    if (!Number.isFinite(numeric)) return 0;
    return clamp(numeric, 0, total);
  }

  function setCursorFromTimelineProgress(rawProgress) {
    const total = currentSandboxStepCount();
    const clamped = normalizeTimelineProgress(rawProgress);
    let stepIndex = Math.floor(clamped);
    let stepProgress = 0;
    if (stepIndex >= total) {
      stepIndex = total;
      stepProgress = 0;
    } else {
      stepProgress = clamp(clamped - stepIndex, 0, 0.999999);
      if (stepProgress >= 0.999999) {
        stepIndex = Math.min(stepIndex + 1, total);
        stepProgress = 0;
      }
    }
    state.sandboxTimelineProgress = clamped;
    state.sandboxCursorStepIndex = stepIndex;
    state.sandboxCursorStepProgress = stepProgress;
    state.sandboxStepIndex = stepIndex;
  }

  function timelineCurrentStepForHighlight() {
    const total = currentSandboxStepCount();
    const stepIndex = state.sandboxCursorStepIndex;
    if (stepIndex < total && state.sandboxCursorStepProgress > 0) {
      return stepIndex;
    }
    return -1;
  }

  function timelineLabelText() {
    const total = currentSandboxStepCount();
    const progress = normalizeTimelineProgress(state.sandboxTimelineProgress);
    return `${progress.toFixed(2)} / ${total}`;
  }

  function stepLabelText() {
    const total = currentSandboxStepCount();
    const stepIndex = state.sandboxCursorStepIndex;
    const stepProgress = state.sandboxCursorStepProgress;
    if (!total) return "Step 0/0";
    if (stepIndex >= total && stepProgress <= 0) return `Step ${total}/${total} · Done`;
    if (stepProgress > 0 && stepIndex < total) {
      const label = state.sandboxData?.highlight_by_step?.[stepIndex] || "";
      const percent = Math.round(stepProgress * 100);
      return label
        ? `Step ${stepIndex + 1}/${total} · ${label} (${percent}%)`
        : `Step ${stepIndex + 1}/${total} (${percent}%)`;
    }
    if (stepIndex === 0) return `Step 0/${total} · Start`;
    const label = state.sandboxData?.highlight_by_step?.[stepIndex - 1] || "";
    return label ? `Step ${stepIndex}/${total} · ${label}` : `Step ${stepIndex}/${total}`;
  }

  function updateTimelineDisplay() {
    const total = currentSandboxStepCount();
    if (DOM.sandboxTimelineSlider) {
      DOM.sandboxTimelineSlider.max = String(total);
      DOM.sandboxTimelineSlider.value = String(normalizeTimelineProgress(state.sandboxTimelineProgress));
    }
    if (DOM.sandboxTimelineLabel) {
      DOM.sandboxTimelineLabel.textContent = timelineLabelText();
    }
  }

  function updateActiveAlgorithmStepHighlight() {
    const activeStep = timelineCurrentStepForHighlight();
    DOM.activeAlgoDisplay.querySelectorAll(".move-tile[data-step-index]").forEach((tile) => {
      const index = Number(tile.getAttribute("data-step-index"));
      tile.classList.toggle("current", index === activeStep);
    });
  }

  function renderSandboxProgress(options = {}) {
    if (!state.sandboxData) {
      DOM.sandboxStepLabel.textContent = "Step 0/0";
      state.sandboxTimelineProgress = 0;
      updateTimelineDisplay();
      updateActiveAlgorithmStepHighlight();
      return false;
    }

    const progress = options.progress != null ? options.progress : state.sandboxTimelineProgress;
    const syncState = options.syncState !== false;
    setCursorFromTimelineProgress(progress);

    const total = currentSandboxStepCount();
    const stepIndex = state.sandboxCursorStepIndex;
    const stepProgress = state.sandboxCursorStepProgress;

    if (syncState && state.sandboxPlayer) {
      const baseState = state.sandboxData.states_by_step?.[stepIndex] || "";
      if (baseState) {
        state.sandboxPlayer.setState(baseState);
        if (stepProgress > 0 && stepIndex < total && state.sandboxPlayer.previewStepFromState) {
          const stepMoves = Array.isArray(state.sandboxData.move_steps?.[stepIndex]) ? state.sandboxData.move_steps[stepIndex] : [];
          state.sandboxPlayer.previewStepFromState(baseState, stepMoves, {
            progress: stepProgress,
            easing: state.sandboxPlaybackConfig.rate_func,
          });
        }
      }
    }

    DOM.sandboxStepLabel.textContent = stepLabelText();
    updateTimelineDisplay();
    updateActiveAlgorithmStepHighlight();
    updateSandboxControls();
    return true;
  }

  function renderSandboxStep(options = {}) {
    const progress = options.progress != null ? options.progress : state.sandboxTimelineProgress;
    return renderSandboxProgress({
      progress,
      syncState: options.syncState,
    });
  }

  function updateSandboxControls() {
    const hasTimeline = Boolean(state.sandboxData);
    const total = currentSandboxStepCount();
    const progress = normalizeTimelineProgress(state.sandboxTimelineProgress);
    const atStart = progress <= 0.000001;
    const atEnd = progress >= total - 0.000001;
    const locked = state.sandboxBusy || state.sandboxPlaybackActive || state.sandboxScrubbing;

    if (DOM.sandboxToStartBtn) {
      DOM.sandboxToStartBtn.disabled = !hasTimeline || atStart || locked;
      DOM.sandboxToStartBtn.title = "Back to start";
      DOM.sandboxToStartBtn.setAttribute("aria-label", "Back to start");
    }
    if (DOM.sandboxPrevBtn) {
      DOM.sandboxPrevBtn.disabled = !hasTimeline || atStart || locked;
      DOM.sandboxPrevBtn.title = "Previous step";
      DOM.sandboxPrevBtn.setAttribute("aria-label", "Previous step");
    }
    if (DOM.sandboxPlayPauseBtn) {
      DOM.sandboxPlayPauseBtn.disabled = !hasTimeline || total === 0;
      const isPlaying = state.sandboxPlaybackActive;
      DOM.sandboxPlayPauseBtn.textContent = isPlaying ? "⏸" : "▶";
      DOM.sandboxPlayPauseBtn.title = isPlaying ? "Pause" : "Play";
      DOM.sandboxPlayPauseBtn.setAttribute("aria-label", isPlaying ? "Pause" : "Play");
    }
    if (DOM.sandboxNextBtn) {
      DOM.sandboxNextBtn.disabled = !hasTimeline || atEnd || locked;
      DOM.sandboxNextBtn.title = "Next step";
      DOM.sandboxNextBtn.setAttribute("aria-label", "Next step");
    }
    if (DOM.sandboxTimelineSlider) {
      DOM.sandboxTimelineSlider.disabled = !hasTimeline || total === 0;
    }

    const speedButtons = Array.from(document.querySelectorAll(".sandbox-speed-btn"));
    if (speedButtons.length) {
      speedButtons.forEach((btn) => {
        const speedValue = Number(btn.dataset.speed || "1");
        btn.classList.toggle("active", speedValue === state.sandboxPlaybackSpeed);
        btn.disabled = !hasTimeline || total === 0;
      });
    }

    if (!hasTimeline) {
      DOM.sandboxStepLabel.textContent = "Step 0/0";
    }

    updateTimelineDisplay();
    updateActiveAlgorithmStepHighlight();
  }

  function resetSandboxData() {
    hardResetSandboxOnSwitch({ clearData: true });
  }

  async function loadSandboxForCurrentCase() {
    hardResetSandboxOnSwitch({ clearData: true });
    const c = currentCase();
    if (!c?.case_key || !state.provider) {
      return;
    }

    try {
      const sandbox = state.provider.getSandboxTimeline(c.case_key, c.active_algorithm_id);
      const isF2L = String(sandbox.group || "").toUpperCase() === "F2L";
      state.sandboxData = sandbox;
      state.sandboxStepIndex = 0;
      state.sandboxTimelineProgress = 0;
      state.sandboxCursorStepIndex = 0;
      state.sandboxCursorStepProgress = 0;
      state.sandboxBusy = false;
      state.sandboxPlaybackConfig = normalizeSandboxPlaybackConfig(sandbox.playback_config);
      renderActiveAlgorithmDisplay(c.active_formula || "");

      if (state.sandboxPlayer) {
        state.sandboxPlayer.setSlots(Array.isArray(sandbox.state_slots) ? sandbox.state_slots : []);
        if (state.sandboxPlayer.setFaceColors) {
          state.sandboxPlayer.setFaceColors(null);
          if (sandbox.face_colors) {
            state.sandboxPlayer.setFaceColors(sandbox.face_colors);
          }
          if (isF2L && !state.sandboxPlayer.setStickerlessTopMask) {
            state.sandboxPlayer.setFaceColors({ U: 0x0b1220 });
          }
        }
        if (state.sandboxPlayer.setStickerlessTopMask) {
          state.sandboxPlayer.setStickerlessTopMask(isF2L, 0x0b1220);
        }
        window.requestAnimationFrame(() => {
          state.sandboxPlayer?.resize();
          renderSandboxProgress({ progress: 0, syncState: true });
        });
      }

      renderSandboxProgress({ progress: 0, syncState: true });
    } catch (error) {
      resetSandboxData();
      showToast(`Sandbox unavailable: ${String(error.message || error)}`);
    }
  }

  async function moveSandboxBy(delta, options = {}) {
    if (!state.sandboxData || state.sandboxBusy || state.sandboxScrubbing) return false;
    const total = currentSandboxStepCount();
    if (total <= 0) return false;
    const animate = options.animate !== false;

    if (delta < 0) {
      const currentProgress = normalizeTimelineProgress(state.sandboxTimelineProgress);
      if (currentProgress <= 0.000001) return false;
      if (state.sandboxCursorStepProgress > 0) {
        return renderSandboxProgress({ progress: state.sandboxCursorStepIndex, syncState: true });
      }

      const targetStep = Math.max(0, state.sandboxCursorStepIndex - 1);
      const moveStep = Array.isArray(state.sandboxData.move_steps?.[targetStep]) ? state.sandboxData.move_steps[targetStep] : [];
      const durationMs = Number(options.durationMs) || sandboxStepDurationMs(moveStep);

      if (animate && state.sandboxPlayer?.playStep && moveStep.length) {
        state.sandboxBusy = true;
        updateSandboxControls();
        let animated = false;
        try {
          animated = await state.sandboxPlayer.playStep(moveStep, {
            reverse: true,
            durationMs,
            easing: state.sandboxPlaybackConfig.rate_func,
          });
        } catch {
          animated = false;
        }
        state.sandboxBusy = false;
        if (animated) {
          return renderSandboxProgress({ progress: targetStep, syncState: false });
        }
      }

      return renderSandboxProgress({ progress: targetStep, syncState: true });
    }

    if (delta > 0) {
      const stepIndex = state.sandboxCursorStepIndex;
      if (stepIndex >= total) return false;
      const stepProgress = state.sandboxCursorStepProgress;
      const moveStep = Array.isArray(state.sandboxData.move_steps?.[stepIndex]) ? state.sandboxData.move_steps[stepIndex] : [];
      const durationMs = Number(options.durationMs) || sandboxStepDurationMs(moveStep);
      const baseState = state.sandboxData.states_by_step?.[stepIndex] || "";

      if (animate && state.sandboxPlayer?.playStep && moveStep.length) {
        state.sandboxBusy = true;
        updateSandboxControls();
        let animated = false;
        try {
          animated = await state.sandboxPlayer.playStep(moveStep, {
            durationMs,
            easing: state.sandboxPlaybackConfig.rate_func,
            baseState,
            startProgress: stepProgress,
            onProgress: (progress01) => {
              setCursorFromTimelineProgress(stepIndex + progress01);
              DOM.sandboxStepLabel.textContent = stepLabelText();
              updateTimelineDisplay();
              updateActiveAlgorithmStepHighlight();
            },
          });
        } catch {
          animated = false;
        }
        state.sandboxBusy = false;
        if (animated) {
          return renderSandboxProgress({ progress: Math.min(stepIndex + 1, total), syncState: false });
        }
      }

      return renderSandboxProgress({ progress: Math.min(stepIndex + 1, total), syncState: true });
    }

    return false;
  }

  function sandboxSetStep(index) {
    if (!state.sandboxData || state.sandboxBusy) return false;
    return renderSandboxProgress({ progress: index, syncState: true });
  }

  function sandboxSetProgress(progress) {
    if (!state.sandboxData || state.sandboxBusy) return false;
    return renderSandboxProgress({ progress, syncState: true });
  }

  function sandboxToStart() {
    if (!state.sandboxData || state.sandboxBusy) return;
    sandboxSetProgress(0);
  }

  async function sandboxStepBackward() {
    if (!state.sandboxData || state.sandboxBusy || state.sandboxPlaybackActive) return;
    await moveSandboxBy(-1, { animate: true });
  }

  async function sandboxStepForward() {
    if (!state.sandboxData || state.sandboxBusy || state.sandboxPlaybackActive) return;
    await moveSandboxBy(1, { animate: true });
  }

  function queueTimelinePreview(progress) {
    state.sandboxPendingTimelineProgress = normalizeTimelineProgress(progress);
    if (state.sandboxTimelineRafPending) return;
    state.sandboxTimelineRafPending = true;
    window.requestAnimationFrame(() => {
      state.sandboxTimelineRafPending = false;
      const pending = state.sandboxPendingTimelineProgress;
      if (pending == null) return;
      if (state.sandboxBusy) return;
      state.sandboxPendingTimelineProgress = null;
      renderSandboxProgress({ progress: pending, syncState: true });
    });
  }

  function beginSandboxScrubbing() {
    if (!state.sandboxData) return;
    state.sandboxWasPlayingBeforeScrub = state.sandboxPlaybackActive;
    if (state.sandboxPlaybackActive) {
      stopSandboxPlayback({ silent: true, forceUpdate: true });
    }
    state.sandboxScrubbing = true;
    updateSandboxControls();
  }

  async function finishSandboxScrubbing(progress) {
    if (!state.sandboxData) return;
    if (state.sandboxBusy) {
      window.setTimeout(() => {
        void finishSandboxScrubbing(progress);
      }, 20);
      return;
    }

    state.sandboxScrubbing = false;
    state.sandboxPendingTimelineProgress = null;
    renderSandboxProgress({ progress, syncState: true });

    const shouldResume = state.sandboxWasPlayingBeforeScrub;
    state.sandboxWasPlayingBeforeScrub = false;
    if (shouldResume) {
      await startSandboxPlayback();
    } else {
      updateSandboxControls();
    }
  }

  async function startSandboxPlayback() {
    if (!state.sandboxData || state.sandboxPlaybackActive || state.sandboxScrubbing) return;
    const total = currentSandboxStepCount();
    if (total <= 0) return;

    if (state.sandboxTimelineProgress >= total) {
      renderSandboxProgress({ progress: 0, syncState: true });
    }

    const token = state.sandboxPlaybackToken + 1;
    state.sandboxPlaybackToken = token;
    state.sandboxPlaybackActive = true;
    updateSandboxControls();

    while (state.sandboxPlaybackActive && token === state.sandboxPlaybackToken) {
      const nowTotal = currentSandboxStepCount();
      if (state.sandboxTimelineProgress >= nowTotal - 0.000001) break;
      if (state.sandboxBusy || state.sandboxScrubbing) {
        const ok = await sleepWithToken(12, token);
        if (!ok) return;
        continue;
      }

      const stepIndex = state.sandboxCursorStepIndex;
      if (stepIndex >= nowTotal) break;
      const step = state.sandboxData.move_steps?.[stepIndex] || [];
      const durationMs = sandboxStepDurationMs(step);
      const moved = await moveSandboxBy(1, { animate: true, durationMs });
      if (!moved || token !== state.sandboxPlaybackToken || !state.sandboxPlaybackActive) {
        break;
      }
      if (state.sandboxTimelineProgress >= nowTotal - 0.000001) {
        break;
      }
      const pauseOk = await sleepWithToken(sandboxInterMovePauseMs(), token);
      if (!pauseOk) return;
    }

    if (token !== state.sandboxPlaybackToken) return;
    state.sandboxPlaybackActive = false;
    if (state.sandboxTimelineProgress >= currentSandboxStepCount() - 0.000001) {
      renderSandboxProgress({ progress: 0, syncState: true });
    }
    updateSandboxControls();
  }

  function toggleSandboxPlayback() {
    if (state.sandboxPlaybackActive) {
      stopSandboxPlayback();
      return;
    }
    void startSandboxPlayback();
  }

  function setProfileModalMessage(message, isError = false) {
    if (!DOM.profileMsg) return;
    DOM.profileMsg.textContent = String(message || "");
    DOM.profileMsg.classList.toggle("profile-msg-error", Boolean(isError));
  }

  function closeProfileModal() {
    DOM.profileModal?.classList.add("hidden");
  }

  async function openProfileModal(mode) {
    profileModalMode = mode;
    DOM.profileModal?.classList.remove("hidden");

    if (mode === "export") {
      DOM.profileApplyBtn.disabled = true;
      setProfileModalMessage("Preparing export...");
      DOM.profileData.value = "";
      try {
        const payload = state.provider?.getProfile() || state.profile || baseProfile();
        const encoded = await exportTrainerProfile(payload);
        DOM.profileData.value = encoded;
        setProfileModalMessage("Export payload ready");
      } catch (error) {
        setProfileModalMessage(String(error.message || error), true);
      }
    } else {
      DOM.profileApplyBtn.disabled = false;
      DOM.profileData.value = "";
      setProfileModalMessage("Paste payload and click Apply");
    }

    window.setTimeout(() => {
      DOM.profileData?.focus();
      if (mode === "export") {
        DOM.profileData?.select();
      }
    }, 0);
  }

  async function applyImportedProfile() {
    try {
      const raw = String(DOM.profileData.value || "").trim();
      const imported = await importTrainerProfile(raw);
      const current = state.provider?.getProfile() || state.profile || baseProfile();
      const merged = mergeProfile(current, imported);
      state.provider.replaceProfile(merged);
      state.profile = state.provider.getProfile();
      state.customTimelineCache.clear();

      refreshCaseCache();
      await loadCatalog();
      setProfileModalMessage("Profile imported");
      showToast("Profile imported");
    } catch (error) {
      setProfileModalMessage(String(error.message || error), true);
    }
  }

  async function copyProfilePayload() {
    const text = String(DOM.profileData.value || "");
    if (!text.trim()) {
      setProfileModalMessage("Nothing to copy", true);
      return;
    }

    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        DOM.profileData.focus();
        DOM.profileData.select();
        document.execCommand("copy");
      }
      setProfileModalMessage("Copied to clipboard");
    } catch (error) {
      setProfileModalMessage(String(error.message || error), true);
    }
  }

  function setupEventListeners() {
    DOM.sandboxToStartBtn?.addEventListener("click", () => {
      stopSandboxPlayback({ silent: true });
      sandboxToStart();
    });

    DOM.sandboxPrevBtn?.addEventListener("click", () => {
      void sandboxStepBackward();
    });

    DOM.sandboxPlayPauseBtn?.addEventListener("click", () => {
      toggleSandboxPlayback();
    });

    DOM.sandboxNextBtn?.addEventListener("click", () => {
      void sandboxStepForward();
    });

    if (DOM.sandboxTimelineSlider) {
      const finishScrub = () => {
        if (!state.sandboxScrubbing) return;
        void finishSandboxScrubbing(DOM.sandboxTimelineSlider.value);
      };

      DOM.sandboxTimelineSlider.addEventListener("pointerdown", () => {
        beginSandboxScrubbing();
      });

      DOM.sandboxTimelineSlider.addEventListener("input", (event) => {
        const target = event.currentTarget;
        if (!(target instanceof HTMLInputElement)) return;
        if (!state.sandboxScrubbing) {
          beginSandboxScrubbing();
        }
        queueTimelinePreview(target.value);
      });

      DOM.sandboxTimelineSlider.addEventListener("change", finishScrub);
      window.addEventListener("pointerup", finishScrub);
    }

    const onSpeedClick = (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const speedBtn = target.closest(".sandbox-speed-btn");
      if (!speedBtn) return;
      setSandboxPlaybackSpeed(speedBtn.dataset.speed || "1");
    };

    document.querySelectorAll(".sandbox-speed-btn").forEach((btn) => {
      btn.addEventListener("click", onSpeedClick);
    });

    if (DOM.sortProgressToggle) {
      DOM.sortProgressToggle.addEventListener("change", (event) => {
        const target = event.currentTarget;
        if (!(target instanceof HTMLInputElement)) return;
        const enabled = Boolean(target.checked);
        state.progressSortByGroup[state.category] = enabled;
        saveProgressSortMap(state.progressSortByGroup);
        renderCatalog();
      });
    }

    document.querySelectorAll(".nav-tab").forEach((tab) => {
      tab.addEventListener("click", async (event) => {
        const target = event.currentTarget;
        if (!(target instanceof HTMLElement)) return;
        const category = String(target.dataset.category || "").toUpperCase();
        if (!GROUPS.includes(category) || category === state.category) return;
        state.category = category;
        state.activeCaseKey = null;
        state.activeCase = null;
        setActiveTab(category);
        await loadCatalog();
      });
    });

    DOM.mStatusGroup.querySelectorAll(".status-btn[data-status]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const c = currentCase();
        if (!c || !state.provider) return;
        const status = String(btn.dataset.status || "");
        if (!status) return;
        state.provider.setCaseProgress(c.case_key, status);
        refreshCaseCache();
        renderCatalog();
        updateDetailsPaneState();
      });
    });

    DOM.exportProfileBtn?.addEventListener("click", () => {
      void openProfileModal("export");
    });

    DOM.importProfileBtn?.addEventListener("click", () => {
      void openProfileModal("import");
    });

    DOM.profileApplyBtn?.addEventListener("click", () => {
      if (profileModalMode !== "import") return;
      void applyImportedProfile();
    });

    DOM.profileCopyBtn?.addEventListener("click", () => {
      void copyProfilePayload();
    });

    DOM.profileCloseBtn?.addEventListener("click", () => {
      closeProfileModal();
    });

    DOM.profileModal?.addEventListener("click", (event) => {
      if (event.target === DOM.profileModal) {
        closeProfileModal();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && DOM.profileModal && !DOM.profileModal.classList.contains("hidden")) {
        closeProfileModal();
        return;
      }

      const target = event.target;
      if (
        target instanceof HTMLElement &&
        (target.closest("input[type='text']") || target.closest("textarea") || target.isContentEditable)
      ) {
        return;
      }

      if (!state.sandboxData) return;
      if (event.repeat && event.code === "Space") return;

      if (event.code === "Space") {
        event.preventDefault();
        toggleSandboxPlayback();
        return;
      }
      if (event.code === "ArrowLeft") {
        event.preventDefault();
        stopSandboxPlayback({ silent: true, forceUpdate: true });
        void sandboxStepBackward();
        return;
      }
      if (event.code === "ArrowRight") {
        event.preventDefault();
        stopSandboxPlayback({ silent: true, forceUpdate: true });
        void sandboxStepForward();
        return;
      }
      if (event.code === "KeyR") {
        event.preventDefault();
        stopSandboxPlayback({ silent: true, forceUpdate: true });
        sandboxToStart();
      }
    });
  }

  async function loadCatalogPayload() {
    const response = await fetch(CATALOG_URL, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Catalog load failed (${response.status})`);
    }
    const payload = await response.json();
    if (!payload || payload.schema_version !== CATALOG_SCHEMA_VERSION) {
      throw new Error("Invalid trainer catalog schema");
    }
    if (!Array.isArray(payload.cases)) {
      throw new Error("Catalog cases must be an array");
    }
    if (!Array.isArray(payload.categories)) {
      throw new Error("Catalog categories must be an array");
    }
    return payload;
  }

  async function init() {
    try {
      if (window.CubeSandbox3D?.createSandbox3D && DOM.sandboxCanvas) {
        state.sandboxPlayer = window.CubeSandbox3D.createSandbox3D(DOM.sandboxCanvas);
        window.addEventListener("resize", () => {
          state.sandboxPlayer?.resize();
        });
      }

      state.catalog = await loadCatalogPayload();
      if (state.catalog.categories.includes(state.category)) {
        state.category = String(state.category);
      } else {
        state.category = state.catalog.categories[0] || "PLL";
      }

      const initialProfile = loadProfileFromStorage();
      state.provider = createTrainerCatalogProvider(state.catalog, initialProfile, (nextProfile) => {
        state.profile = normalizeProfile(nextProfile);
        saveProfile(state.profile);
      });
      state.profile = state.provider.getProfile();

      setActiveTab(state.category);
      setupEventListeners();
      updateSandboxControls();
      syncProgressSortToggle();
      await loadCatalog();
    } catch (error) {
      showToast(String(error.message || error));
      console.error(error);
      setDetailsDisabled();
      DOM.catalog.innerHTML = '<div class="catalog-empty">Catalog unavailable. Run trainer build first.</div>';
    }
  }

  void init();
})();
