import { RECOGNIZER_CACHE_BUSTER } from "../core/constants.js";
import { tokenizeFormula } from "../domain/formula.js";

export function caseShortLabel(item) {
  if (item.case_number != null) return `${item.group} #${item.case_number}`;
  return item.case_code || "-";
}

export function detailTitle(item) {
  return String(
    item.detail_title ||
      item.title ||
      item.display_name ||
      (item.case_number != null ? `${item.group} #${item.case_number}` : item.case_code || "Case")
  );
}

export function tileTitle(item) {
  return String(
    item.tile_title ||
      item.display_name ||
      item.title ||
      item.case_code ||
      (item.case_number != null ? `${item.group} #${item.case_number}` : "Case")
  );
}

export function appendRecognizerPreview(container, item) {
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

function sandboxOverlayFormula(state, caseItem) {
  const active = String(state.activeDisplayFormula || "").trim();
  if (state.activeDisplayMode === "custom" && active) return active;
  return active || String(caseItem?.active_formula || "").trim();
}

export function updateSandboxOverlay(dom, state, caseItem) {
  if (dom.sandboxOverlayTitle) {
    dom.sandboxOverlayTitle.textContent = caseItem ? detailTitle(caseItem) : "Select Case";
  }
  if (dom.sandboxOverlaySubtitle) {
    dom.sandboxOverlaySubtitle.textContent = caseItem
      ? [caseShortLabel(caseItem), caseItem.subgroup_title].filter(Boolean).join(" · ")
      : "-";
  }
  if (dom.sandboxOverlayFormula) {
    const formula = caseItem ? sandboxOverlayFormula(state, caseItem) : "";
    const formatted = formatSandboxFormulaOverlay(formula);
    dom.sandboxOverlayFormula.textContent = formatted || "-";
    dom.sandboxOverlayFormula.title = formula || "";
  }
  if (dom.sandboxOverlayTopImage) {
    const recognizerUrl = caseItem ? String(caseItem.recognizer_url || "").trim() : "";
    if (recognizerUrl) {
      const sep = recognizerUrl.includes("?") ? "&" : "?";
      dom.sandboxOverlayTopImage.src = `${recognizerUrl}${sep}v=${RECOGNIZER_CACHE_BUSTER}`;
      dom.sandboxOverlayTopImage.style.visibility = "visible";
    } else {
      dom.sandboxOverlayTopImage.removeAttribute("src");
      dom.sandboxOverlayTopImage.style.visibility = "hidden";
    }
  }
}
