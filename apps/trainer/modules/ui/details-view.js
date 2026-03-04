import { tokenizeFormula } from "../domain/formula.js";
import { sanitizeForTestId } from "../utils/common.js";
import { caseShortLabel, detailTitle } from "./sandbox-overlay-view.js";

/**
 * @param {Object} deps
 */
export function createDetailsView(deps) {
  const {
    state,
    dom,
    showToast,
    getCurrentCase,
    updateSandboxOverlay,
    onSelectAlgorithm,
    onDeleteAlgorithm,
    onApplyCustomFormula,
    onGoToStep,
  } = deps;

  function updateActiveAlgorithmStepHighlight(activeStep) {
    dom.activeAlgoDisplay.querySelectorAll(".move-tile[data-step-index]").forEach((tile) => {
      const index = Number(tile.getAttribute("data-step-index"));
      tile.classList.toggle("current", index === activeStep);
    });
  }

  function renderActiveAlgorithmDisplay(formula) {
    dom.activeAlgoDisplay.innerHTML = "";
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
            onGoToStep(stepIndex);
          });
          row.appendChild(tile);
        });
        dom.activeAlgoDisplay.appendChild(row);
      }
      return;
    }

    const moves = tokenizeFormula(formula);
    if (!moves.length) {
      dom.activeAlgoDisplay.innerHTML = '<div class="algo-placeholder">No algorithm selected</div>';
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
      dom.activeAlgoDisplay.appendChild(row);
    });
  }

  function setActiveDisplayFormula(formula, mode = "algorithm") {
    state.activeDisplayMode = mode;
    state.activeDisplayFormula = String(formula || "").trim();
    renderActiveAlgorithmDisplay(state.activeDisplayFormula);
    updateSandboxOverlay(getCurrentCase());
  }

  function isCustomFormulaInputFocused() {
    const input = dom.mAlgoList.querySelector("#custom-formula-input");
    return Boolean(input) && document.activeElement === input;
  }

  function setDetailsDisabled() {
    dom.mName.textContent = "Select Case";
    dom.mCaseCode.textContent = "-";
    dom.mProb.textContent = "Probability: n/a";
    dom.mStatusGroup.querySelectorAll(".status-btn[data-status]").forEach((btn) => {
      btn.classList.remove("active");
      btn.disabled = true;
    });
    dom.mAlgoList.innerHTML = '<div class="algo-empty">Select case to manage algorithms.</div>';
    setActiveDisplayFormula("", "algorithm");
    updateSandboxOverlay(null);
  }

  function renderAlgorithmsList(c) {
    const prevInput = dom.mAlgoList.querySelector("#custom-formula-input");
    const prevValue = prevInput ? String(prevInput.value || "") : "";
    const prevFocused = prevInput ? document.activeElement === prevInput : false;
    const prevSelectionStart = prevInput && prevInput.selectionStart != null ? prevInput.selectionStart : null;
    const prevSelectionEnd = prevInput && prevInput.selectionEnd != null ? prevInput.selectionEnd : null;

    dom.mAlgoList.innerHTML = "";

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
          await onSelectAlgorithm(algo.id);
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
            await onDeleteAlgorithm(algo.id);
          } catch (error) {
            showToast(String(error.message || error));
          }
        });
      }

      dom.mAlgoList.appendChild(option);
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
        await onApplyCustomFormula(formula);
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
      const activeCase = getCurrentCase();
      if (!activeCase) return;
      if (!String(input.value || "").trim()) {
        setActiveDisplayFormula(activeCase.active_formula || "", "algorithm");
      }
    });

    dom.mAlgoList.appendChild(customWrap);
  }

  function updateDetailsPaneState() {
    const c = getCurrentCase();
    if (!c) {
      setDetailsDisabled();
      return;
    }

    dom.mName.textContent = detailTitle(c);
    dom.mProb.textContent = `Probability: ${c.probability_text || "n/a"}`;
    dom.mCaseCode.textContent = [caseShortLabel(c), c.subgroup_title].filter(Boolean).join(" · ");

    dom.mStatusGroup.querySelectorAll(".status-btn[data-status]").forEach((btn) => {
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

  return {
    setDetailsDisabled,
    updateDetailsPaneState,
    setActiveDisplayFormula,
    renderActiveAlgorithmDisplay,
    updateActiveAlgorithmStepHighlight,
    isCustomFormulaInputFocused,
  };
}
