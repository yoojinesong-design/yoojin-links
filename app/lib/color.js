/**
 * Parse a color string (hex or rgb()) into { r, g, b } components.
 * Returns null if the color can't be parsed.
 */
export function hexToRgb(color) {
  if (!color) return null;
  // Handle rgb() format returned by getComputedStyle
  const rgbMatch = color.match(/^rgb\((\d+),\s*(\d+),\s*(\d+)\)$/);
  if (rgbMatch) return { r: +rgbMatch[1], g: +rgbMatch[2], b: +rgbMatch[3] };
  let hex = color.replace("#", "");
  if (hex.length === 3) hex = hex.split("").map((c) => c + c).join("");
  const n = parseInt(hex, 16);
  return isNaN(n) ? null : { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}
