import { PROFILE_SCHEMA_VERSION } from "../core/constants.js";
import { normalizeProfile } from "./profile-storage.js";

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

export async function exportTrainerProfile(payload) {
  const json = JSON.stringify(normalizeProfile(payload));
  const bytes = new TextEncoder().encode(json);
  if (typeof CompressionStream === "undefined") {
    throw new Error("CompressionStream is unavailable in this browser");
  }
  const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream("gzip"));
  const buffer = await new Response(stream).arrayBuffer();
  return bytesToBase64Url(new Uint8Array(buffer));
}

export async function importTrainerProfile(raw) {
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
