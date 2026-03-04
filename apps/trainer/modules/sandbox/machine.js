/**
 * @typedef {"IDLE"|"PLAYING"|"STEPPING"|"SCRUBBING"|"ERROR"} SandboxMachineState
 */

/**
 * @typedef {"LOAD_TIMELINE"|"PLAY_TOGGLE"|"STEP_NEXT"|"STEP_PREV"|"TO_START"|"SCRUB_BEGIN"|"SCRUB_UPDATE"|"SCRUB_END"|"ANIM_DONE"|"ANIM_FAIL"|"RESET"} SandboxMachineEvent
 */

const STATES = new Set(["IDLE", "PLAYING", "STEPPING", "SCRUBBING", "ERROR"]);

/**
 * @param {SandboxMachineState} [initialState]
 * @param {(transition: {prev: SandboxMachineState, next: SandboxMachineState, event: SandboxMachineEvent, payload: Object}) => void} [onTransition]
 */
export function createSandboxMachine(initialState = "IDLE", onTransition) {
  let current = STATES.has(initialState) ? initialState : "IDLE";
  const context = {
    wasPlayingBeforeScrub: false,
    lastError: null,
  };

  /**
   * @param {SandboxMachineEvent} event
   * @param {Object} [payload]
   * @returns {SandboxMachineState}
   */
  function send(event, payload = {}) {
    const prev = current;

    switch (event) {
      case "LOAD_TIMELINE":
      case "RESET": {
        context.wasPlayingBeforeScrub = false;
        context.lastError = null;
        current = "IDLE";
        break;
      }
      case "PLAY_TOGGLE": {
        if (current === "PLAYING") {
          current = "IDLE";
        } else if (current === "IDLE" || current === "ERROR") {
          current = "PLAYING";
        }
        break;
      }
      case "STEP_NEXT":
      case "STEP_PREV": {
        if (current === "IDLE" || current === "PLAYING") {
          current = "STEPPING";
        }
        break;
      }
      case "TO_START": {
        if (current !== "ERROR") {
          current = "IDLE";
        }
        break;
      }
      case "SCRUB_BEGIN": {
        context.wasPlayingBeforeScrub = current === "PLAYING";
        current = "SCRUBBING";
        break;
      }
      case "SCRUB_UPDATE": {
        break;
      }
      case "SCRUB_END": {
        if (current === "SCRUBBING") {
          current = context.wasPlayingBeforeScrub ? "PLAYING" : "IDLE";
          context.wasPlayingBeforeScrub = false;
        }
        break;
      }
      case "ANIM_DONE": {
        if (current === "STEPPING") {
          current = payload.resumePlaying ? "PLAYING" : "IDLE";
        }
        break;
      }
      case "ANIM_FAIL": {
        context.lastError = payload.error || null;
        current = "ERROR";
        if (payload.recover !== false) {
          current = "IDLE";
        }
        break;
      }
      default:
        break;
    }

    if (typeof onTransition === "function") {
      onTransition({ prev, next: current, event, payload });
    }
    return current;
  }

  return {
    send,
    getState() {
      return current;
    },
    getContext() {
      return { ...context };
    },
    is(value) {
      return current === value;
    },
  };
}
