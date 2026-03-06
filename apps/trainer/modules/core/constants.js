export const GROUPS = ["F2L", "OLL", "PLL"];
export const PROFILE_STORAGE_KEY = "cards_trainer_profile_v1";
export const PROFILE_SCHEMA_VERSION = 1;
export const CATALOG_SCHEMA_VERSION = "trainer-catalog-v1";
export const CATALOG_URL = "./data/catalog-v1.json";
export const MANUAL_CONTENT_URL = "./data/manual-content.json";
export const PROGRESS_SORT_STORAGE_KEY = "cards_progress_sort_by_group_v1";
export const STATUS_SORT_RANK = {
  IN_PROGRESS: 0,
  NEW: 1,
  LEARNED: 2,
};
export const STATUS_CYCLE = ["NEW", "IN_PROGRESS", "LEARNED"];
export const RECOGNIZER_CACHE_BUSTER = `r${Date.now()}`;

export const SANDBOX_PLAYBACK_SPEEDS = [1, 1.5, 2];
export const DEFAULT_SANDBOX_PLAYBACK_CONFIG = {
  run_time_sec: 0.65,
  double_turn_multiplier: 1.7,
  inter_move_pause_ratio: 0.05,
  rate_func: "ease_in_out_sine",
};
export const SANDBOX_RESTART_DELAY_MS = 500;
export const MOBILE_LAYOUT_MAX_WIDTH = 860;
export const DESKTOP_LAYOUT_MIN_WIDTH = 1280;

export const AUTO_MERGE_UD_PAIRS = new Set([
  "U|D'",
  "D'|U",
  "U'|D",
  "D|U'",
]);

export const POSITIVE_BASES = new Set(["R", "F", "D", "E", "S", "r", "f", "d", "x", "z"]);
export const FACE_TO_NORMAL = {
  U: [0, 0, 1],
  D: [0, 0, -1],
  R: [0, -1, 0],
  L: [0, 1, 0],
  F: [-1, 0, 0],
  B: [1, 0, 0],
};
export const NORMAL_TO_FACE = {
  "0,0,1": "U",
  "0,0,-1": "D",
  "0,-1,0": "R",
  "0,1,0": "L",
  "-1,0,0": "F",
  "1,0,0": "B",
};
