const THREE_VENDOR_URL = "./vendor/three.min.js";
const SANDBOX_MODULE_URL = "../../sandbox3d.js";
const THREE_SCRIPT_ID = "trainer-three-runtime";

let sandboxRuntimePromise = null;

function loadScript(src, id) {
  return new Promise((resolve, reject) => {
    const existing = id ? document.getElementById(id) : null;
    if (existing) {
      if (existing.dataset.loaded === "true") {
        resolve();
        return;
      }
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error(`Script load failed: ${src}`)), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    if (id) {
      script.id = id;
    }
    script.addEventListener("load", () => {
      script.dataset.loaded = "true";
      resolve();
    }, { once: true });
    script.addEventListener("error", () => {
      reject(new Error(`Script load failed: ${src}`));
    }, { once: true });
    document.head.appendChild(script);
  });
}

async function ensureThreeVendor() {
  if (globalThis.THREE) {
    return;
  }
  await loadScript(THREE_VENDOR_URL, THREE_SCRIPT_ID);
  if (!globalThis.THREE) {
    throw new Error("THREE runtime is unavailable after vendor load");
  }
}

export function isSandboxRuntimeReady() {
  return Boolean(globalThis.THREE && globalThis.CubeSandbox3D?.createSandbox3D);
}

export async function ensureSandboxRuntime() {
  if (isSandboxRuntimeReady()) {
    return globalThis.CubeSandbox3D;
  }
  if (!sandboxRuntimePromise) {
    sandboxRuntimePromise = (async () => {
      await ensureThreeVendor();
      const mod = await import(SANDBOX_MODULE_URL);
      const runtime = mod?.createSandbox3D ? { createSandbox3D: mod.createSandbox3D } : globalThis.CubeSandbox3D;
      if (!runtime?.createSandbox3D) {
        throw new Error("CubeSandbox3D runtime failed to initialize");
      }
      return runtime;
    })().catch((error) => {
      sandboxRuntimePromise = null;
      throw error;
    });
  }
  return sandboxRuntimePromise;
}

export async function preloadSandboxRuntime() {
  await ensureSandboxRuntime();
}

export async function ensureSandboxPlayerReady(canvasEl) {
  const runtime = await ensureSandboxRuntime();
  return runtime.createSandbox3D(canvasEl);
}
