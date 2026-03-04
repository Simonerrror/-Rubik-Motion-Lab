import { DEFAULT_SANDBOX_PLAYBACK_CONFIG } from "./constants.js";

/**
 * @typedef {"algorithm"|"custom"} ActiveDisplayMode
 */

/**
 * @typedef {"IDLE"|"PLAYING"|"STEPPING"|"SCRUBBING"|"ERROR"} SandboxMachineState
 */

/**
 * @typedef {Object} TrainerState
 * @property {string} category
 * @property {Array<Object>} cases
 * @property {string|null} activeCaseKey
 * @property {Object|null} activeCase
 * @property {Object|null} catalog
 * @property {Object|null} provider
 * @property {Object|null} profile
 * @property {Record<string, boolean>} progressSortByGroup
 * @property {Object|null} sandboxData
 * @property {Object|null} sandboxPlayer
 * @property {number} sandboxStepIndex
 * @property {number} sandboxTimelineProgress
 * @property {number} sandboxCursorStepIndex
 * @property {number} sandboxCursorStepProgress
 * @property {boolean} sandboxTimelineRafPending
 * @property {number|null} sandboxPendingTimelineProgress
 * @property {number} sandboxPlaybackToken
 * @property {Object} sandboxPlaybackConfig
 * @property {number} sandboxPlaybackSpeed
 * @property {SandboxMachineState} sandboxMachineState
 * @property {boolean} sandboxWasPlayingBeforeScrub
 * @property {ActiveDisplayMode} activeDisplayMode
 * @property {string} activeDisplayFormula
 * @property {Map<string, Object>} customTimelineCache
 * @property {number|undefined} _toastTimer
 */

/**
 * @param {Record<string, boolean>} progressSortByGroup
 * @returns {TrainerState}
 */
export function createInitialState(progressSortByGroup) {
  return {
    category: "PLL",
    cases: [],
    activeCaseKey: null,
    activeCase: null,
    catalog: null,
    provider: null,
    profile: null,
    progressSortByGroup,

    sandboxData: null,
    sandboxPlayer: null,
    sandboxStepIndex: 0,
    sandboxTimelineProgress: 0,
    sandboxCursorStepIndex: 0,
    sandboxCursorStepProgress: 0,
    sandboxTimelineRafPending: false,
    sandboxPendingTimelineProgress: null,
    sandboxPlaybackToken: 0,
    sandboxPlaybackConfig: { ...DEFAULT_SANDBOX_PLAYBACK_CONFIG },
    sandboxPlaybackSpeed: 1,
    sandboxMachineState: "IDLE",
    sandboxWasPlayingBeforeScrub: false,

    activeDisplayMode: "algorithm",
    activeDisplayFormula: "",

    customTimelineCache: new Map(),
  };
}
