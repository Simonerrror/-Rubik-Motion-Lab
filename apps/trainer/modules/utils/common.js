export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function sanitizeForTestId(raw) {
  return (
    String(raw || "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "item"
  );
}

export function cloneObject(value) {
  if (Array.isArray(value)) return value.map(cloneObject);
  if (!value || typeof value !== "object") return value;
  const out = {};
  Object.entries(value).forEach(([key, val]) => {
    out[key] = cloneObject(val);
  });
  return out;
}
