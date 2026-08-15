"use client";

import React, { useRef, useEffect, useState } from "react";
import { hexToRgb } from "../lib/color";

function RadarChart({
  scores,
  dimensions,
  maxScore = 5,
  size = 220,
  accentColor,
  showLabels = true,
}) {
  const canvasRef = useRef(null);

  const [theme, setTheme] = useState("");
  useEffect(() => {
    const update = () => setTheme(
      (document.documentElement.getAttribute("data-theme") || "") +
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    );
    update();
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", update);
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => { mq.removeEventListener("change", update); observer.disconnect(); };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;

    const pad = showLabels ? 36 : 12;
    const totalSize = size + pad * 2;

    canvas.width = totalSize * dpr;
    canvas.height = totalSize * dpr;
    canvas.style.width = totalSize + "px";
    canvas.style.height = totalSize + "px";
    ctx.scale(dpr, dpr);

    const cx = totalSize / 2;
    const cy = totalSize / 2;
    const maxR = size * 0.42;
    const n = dimensions.length;
    const angleStep = (Math.PI * 2) / n;
    const startAngle = -Math.PI / 2;

    const style = getComputedStyle(document.documentElement);
    const gridColor = style.getPropertyValue("--border").trim() || "#d6d0c6";
    const labelColor = style.getPropertyValue("--text-mid").trim() || "#57534e";
    const accent = accentColor || style.getPropertyValue("--accent").trim() || "#2a6f5e";

    ctx.clearRect(0, 0, totalSize, totalSize);

    // Grid polygons
    [0.25, 0.5, 0.75, 1].forEach((level) => {
      ctx.beginPath();
      for (let i = 0; i <= n; i++) {
        const angle = startAngle + (i % n) * angleStep;
        const x = cx + Math.cos(angle) * maxR * level;
        const y = cy + Math.sin(angle) * maxR * level;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.strokeStyle = gridColor;
      ctx.globalAlpha = 0.35;
      ctx.lineWidth = 1;
      ctx.stroke();
    });

    ctx.globalAlpha = 1;

    // Axis lines
    for (let i = 0; i < n; i++) {
      const angle = startAngle + i * angleStep;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(angle) * maxR, cy + Math.sin(angle) * maxR);
      ctx.strokeStyle = gridColor;
      ctx.globalAlpha = 0.25;
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    ctx.globalAlpha = 1;

    // Data polygon
    const hasData = dimensions.some((d) => (scores[d.key] || 0) > 0);
    if (hasData) {
      ctx.beginPath();
      dimensions.forEach((dim, i) => {
        const score = Math.max((scores[dim.key] || 0) / maxScore, 0.06);
        const angle = startAngle + i * angleStep;
        const x = cx + Math.cos(angle) * maxR * score;
        const y = cy + Math.sin(angle) * maxR * score;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.closePath();

      // Parse accent for rgba fill
      const rgb = hexToRgb(accent);
      if (rgb) {
        ctx.fillStyle = `rgba(${rgb.r},${rgb.g},${rgb.b},0.15)`;
      } else {
        ctx.fillStyle = accent;
        ctx.globalAlpha = 0.15;
      }
      ctx.fill();
      ctx.globalAlpha = 1;

      ctx.strokeStyle = accent;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Data points
      dimensions.forEach((dim, i) => {
        const score = Math.max((scores[dim.key] || 0) / maxScore, 0.06);
        const angle = startAngle + i * angleStep;
        const x = cx + Math.cos(angle) * maxR * score;
        const y = cy + Math.sin(angle) * maxR * score;
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fillStyle = accent;
        ctx.fill();
      });
    }

    // Labels
    if (showLabels) {
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.font = '500 11px system-ui, -apple-system, sans-serif';
      ctx.fillStyle = labelColor;
      dimensions.forEach((dim, i) => {
        const angle = startAngle + i * angleStep;
        const labelR = maxR + 22;
        const x = cx + Math.cos(angle) * labelR;
        const y = cy + Math.sin(angle) * labelR;

        // Adjust alignment for readability
        if (Math.abs(Math.cos(angle)) < 0.01) {
          ctx.textAlign = "center";
        } else if (Math.cos(angle) > 0) {
          ctx.textAlign = "left";
        } else {
          ctx.textAlign = "right";
        }

        const label = dim.label;
        const val = scores[dim.key] || 0;
        ctx.fillStyle = labelColor;
        ctx.fillText(label, x, y - 7);
        ctx.font = '600 11px system-ui, -apple-system, sans-serif';
        ctx.fillStyle = accent;
        ctx.fillText(val + "/" + maxScore, x, y + 7);
        ctx.font = '500 11px system-ui, -apple-system, sans-serif';
      });
    }
  }, [scores, dimensions, maxScore, size, accentColor, showLabels, theme]);

  return (
    <canvas
      ref={canvasRef}
      style={{ display: "block", margin: "0 auto" }}
      role="img"
      aria-label={`Radar chart: ${dimensions.map(d => `${d.label} ${scores[d.key] || 0} out of ${maxScore}`).join(', ')}`}
    />
  );
}

export default React.memo(RadarChart);
