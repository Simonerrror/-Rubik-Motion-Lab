import { RECOGNIZER_CACHE_BUSTER } from "../core/constants.js";

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

export function updateSandboxOverlay(dom, state, caseItem) {
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
