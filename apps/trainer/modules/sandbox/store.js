import { DEFAULT_SANDBOX_PLAYBACK_CONFIG, SANDBOX_PLAYBACK_SPEEDS } from "../core/constants.js";
import { clamp } from "../utils/common.js";

function deriveCursor(progress, total) {
  const normalized = clamp(Number(progress) || 0, 0, Math.max(0, total));
  let stepIndex = Math.floor(normalized);
  let stepProgress = 0;
  if (stepIndex >= total) {
    stepIndex = total;
  } else {
    stepProgress = clamp(normalized - stepIndex, 0, 0.999999);
    if (stepProgress >= 0.999999) {
      stepIndex = Math.min(stepIndex + 1, total);
      stepProgress = 0;
    }
  }
  return { progress: normalized, stepIndex, stepProgress };
}

function emptyState() {
  return {
    activeTimeline: null,
    activeFormula: "",
    cubeSize: 3,
    timelineModels: [],
    timelineSnapshots: [],
    timelineProgress: 0,
    cursorStepIndex: 0,
    cursorStepProgress: 0,
    playbackSpeed: 1,
    playbackConfig: { ...DEFAULT_SANDBOX_PLAYBACK_CONFIG },
    playbackMode: "idle",
    playbackToken: 0,
    wasPlayingBeforeScrub: false,
    pendingTimelineProgress: null,
    timelineRafPending: false,
    pendingActionQueue: [],
  };
}

function reduce(state, action) {
  const current = state || emptyState();
  switch (action.type) {
    case "RESET": {
      return emptyState();
    }
    case "LOAD_TIMELINE": {
      const timeline = action.timeline || null;
      const total = Array.isArray(timeline?.move_steps) ? timeline.move_steps.length : 0;
      const cursor = deriveCursor(0, total);
      return {
        ...current,
        activeTimeline: timeline,
        activeFormula: String(action.activeFormula || ""),
        cubeSize: Number(action.cubeSize || timeline?.cube_size || 3) || 3,
        timelineModels: Array.isArray(action.timelineModels) ? action.timelineModels : [],
        timelineSnapshots: Array.isArray(action.timelineSnapshots) ? action.timelineSnapshots : [],
        timelineProgress: cursor.progress,
        cursorStepIndex: cursor.stepIndex,
        cursorStepProgress: cursor.stepProgress,
        playbackConfig: action.playbackConfig || { ...DEFAULT_SANDBOX_PLAYBACK_CONFIG },
        playbackMode: "idle",
        playbackToken: current.playbackToken + 1,
        wasPlayingBeforeScrub: false,
        pendingTimelineProgress: null,
        timelineRafPending: false,
        pendingActionQueue: [],
      };
    }
    case "SET_PROGRESS": {
      const total = Array.isArray(current.activeTimeline?.move_steps) ? current.activeTimeline.move_steps.length : 0;
      const cursor = deriveCursor(action.progress, total);
      return {
        ...current,
        timelineProgress: cursor.progress,
        cursorStepIndex: cursor.stepIndex,
        cursorStepProgress: cursor.stepProgress,
      };
    }
    case "SET_SPEED": {
      const nextSpeed = Number(action.speed);
      return {
        ...current,
        playbackSpeed: SANDBOX_PLAYBACK_SPEEDS.includes(nextSpeed) ? nextSpeed : 1,
      };
    }
    case "SET_PLAYBACK_MODE": {
      return {
        ...current,
        playbackMode: String(action.mode || "idle"),
      };
    }
    case "BUMP_TOKEN": {
      return {
        ...current,
        playbackToken: current.playbackToken + 1,
      };
    }
    case "SET_WAS_PLAYING_BEFORE_SCRUB": {
      return {
        ...current,
        wasPlayingBeforeScrub: Boolean(action.value),
      };
    }
    case "SET_PENDING_TIMELINE_PROGRESS": {
      return {
        ...current,
        pendingTimelineProgress: action.progress == null ? null : Number(action.progress),
      };
    }
    case "SET_TIMELINE_RAF_PENDING": {
      return {
        ...current,
        timelineRafPending: Boolean(action.value),
      };
    }
    case "ENQUEUE_ACTION": {
      return {
        ...current,
        pendingActionQueue: [...current.pendingActionQueue, action.payload],
      };
    }
    case "SHIFT_ACTION": {
      return {
        ...current,
        pendingActionQueue: current.pendingActionQueue.slice(1),
      };
    }
    case "CLEAR_ACTION_QUEUE": {
      return {
        ...current,
        pendingActionQueue: [],
      };
    }
    default:
      return current;
  }
}

export function createSandboxStore(initialState) {
  let current = {
    ...emptyState(),
    ...(initialState || {}),
  };
  const listeners = new Set();

  function notify() {
    listeners.forEach((listener) => {
      listener(current);
    });
  }

  return {
    getState() {
      return current;
    },
    dispatch(action) {
      current = reduce(current, action || { type: "__noop__" });
      notify();
      return current;
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
