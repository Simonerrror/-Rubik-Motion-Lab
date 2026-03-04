/**
 * @param {Object} deps
 */
export function createProfileModalController(deps) {
  const { dom, exportTrainerProfile, importTrainerProfile, mergeProfile, baseProfile, getProfile, applyProfile, showToast } = deps;
  let profileModalMode = "export";

  function setMessage(message, isError = false) {
    if (!dom.profileMsg) return;
    dom.profileMsg.textContent = String(message || "");
    dom.profileMsg.classList.toggle("profile-msg-error", Boolean(isError));
  }

  function close() {
    dom.profileModal?.classList.add("hidden");
  }

  async function open(mode) {
    profileModalMode = mode;
    dom.profileModal?.classList.remove("hidden");

    if (mode === "export") {
      dom.profileApplyBtn.disabled = true;
      setMessage("Preparing export...");
      dom.profileData.value = "";
      try {
        const payload = getProfile() || baseProfile();
        const encoded = await exportTrainerProfile(payload);
        dom.profileData.value = encoded;
        setMessage("Export payload ready");
      } catch (error) {
        setMessage(String(error.message || error), true);
      }
    } else {
      dom.profileApplyBtn.disabled = false;
      dom.profileData.value = "";
      setMessage("Paste payload and click Apply");
    }

    window.setTimeout(() => {
      dom.profileData?.focus();
      if (mode === "export") {
        dom.profileData?.select();
      }
    }, 0);
  }

  async function applyImported() {
    try {
      const raw = String(dom.profileData.value || "").trim();
      const imported = await importTrainerProfile(raw);
      const current = getProfile() || baseProfile();
      const merged = mergeProfile(current, imported);
      await applyProfile(merged);
      setMessage("Profile imported");
      showToast("Profile imported");
    } catch (error) {
      setMessage(String(error.message || error), true);
    }
  }

  async function copyPayload() {
    const text = String(dom.profileData.value || "");
    if (!text.trim()) {
      setMessage("Nothing to copy", true);
      return;
    }

    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        dom.profileData.focus();
        dom.profileData.select();
        document.execCommand("copy");
      }
      setMessage("Copied to clipboard");
    } catch (error) {
      setMessage(String(error.message || error), true);
    }
  }

  function isOpen() {
    return Boolean(dom.profileModal && !dom.profileModal.classList.contains("hidden"));
  }

  return {
    get mode() {
      return profileModalMode;
    },
    open,
    close,
    applyImported,
    copyPayload,
    isOpen,
    setMessage,
  };
}
