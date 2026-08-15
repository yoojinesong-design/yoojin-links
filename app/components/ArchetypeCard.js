"use client";

import React, { useEffect, useRef, useState } from "react";

/* ── Canvas emblem drawing functions ── */
function drawConnector(ctx, cx, cy, size, color) {
  const r = size * 0.32;
  const offset = r * 0.55;
  ctx.globalAlpha = 0.18;
  ctx.beginPath();
  ctx.arc(cx - offset, cy, r, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.beginPath();
  ctx.arc(cx + offset, cy, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;
  /* vesica piscis intersection */
  ctx.save();
  ctx.beginPath();
  ctx.arc(cx - offset, cy, r, 0, Math.PI * 2);
  ctx.clip();
  ctx.beginPath();
  ctx.arc(cx + offset, cy, r, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.globalAlpha = 0.45;
  ctx.fill();
  ctx.restore();
  /* outer strokes */
  ctx.globalAlpha = 0.6;
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = color;
  ctx.beginPath();
  ctx.arc(cx - offset, cy, r, 0, Math.PI * 2);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(cx + offset, cy, r, 0, Math.PI * 2);
  ctx.stroke();
  ctx.globalAlpha = 1;
}

function drawBuilder(ctx, cx, cy, size, color) {
  const w = size * 0.55;
  const h = size * 0.6;
  const top = cy - h * 0.48;
  const bottom = cy + h * 0.48;
  const blockH = h * 0.15;
  const gap = 2;
  /* arch keystone */
  ctx.globalAlpha = 0.35;
  ctx.fillStyle = color;
  const archW = w * 0.6;
  const archTop = top + blockH + gap;
  ctx.beginPath();
  ctx.moveTo(cx - archW / 2, bottom);
  ctx.lineTo(cx - archW / 2, archTop + archW / 2);
  ctx.arc(cx, archTop + archW / 2, archW / 2, Math.PI, 0, false);
  ctx.lineTo(cx + archW / 2, bottom);
  ctx.fill();
  /* blocks */
  ctx.globalAlpha = 0.7;
  const bw = w * 0.42;
  /* top block (keystone) */
  roundRect(ctx, cx - bw / 2, top, bw, blockH, 2);
  ctx.fill();
  /* left column */
  const colW = w * 0.25;
  roundRect(ctx, cx - w / 2, top + blockH + gap, colW, h - blockH - gap, 2);
  ctx.fill();
  /* right column */
  roundRect(ctx, cx + w / 2 - colW, top + blockH + gap, colW, h - blockH - gap, 2);
  ctx.fill();
  ctx.globalAlpha = 1;
}

function drawGuide(ctx, cx, cy, size, color) {
  const r = size * 0.34;
  const points = 8;
  ctx.fillStyle = color;
  ctx.strokeStyle = color;
  /* outer star */
  ctx.globalAlpha = 0.2;
  ctx.beginPath();
  for (let i = 0; i < points * 2; i++) {
    const angle = (i * Math.PI) / points - Math.PI / 2;
    const radius = i % 2 === 0 ? r : r * 0.42;
    const x = cx + Math.cos(angle) * radius;
    const y = cy + Math.sin(angle) * radius;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.fill();
  /* inner star (north star emphasis) */
  ctx.globalAlpha = 0.55;
  ctx.beginPath();
  const inner = 4;
  for (let i = 0; i < inner * 2; i++) {
    const angle = (i * Math.PI) / inner - Math.PI / 2;
    const radius = i % 2 === 0 ? r * 0.85 : r * 0.2;
    const x = cx + Math.cos(angle) * radius;
    const y = cy + Math.sin(angle) * radius;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.fill();
  /* center dot */
  ctx.globalAlpha = 0.8;
  ctx.beginPath();
  ctx.arc(cx, cy, r * 0.08, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;
}

function drawSolver(ctx, cx, cy, size, color) {
  const r1 = size * 0.22;
  const r2 = size * 0.18;
  const offset = r1 * 0.72;
  ctx.fillStyle = color;
  ctx.strokeStyle = color;
  drawGear(ctx, cx - offset, cy - offset * 0.3, r1, 8, color, 0.35);
  drawGear(ctx, cx + offset, cy + offset * 0.3, r2, 7, color, 0.5);
  /* center dots */
  ctx.globalAlpha = 0.6;
  ctx.beginPath();
  ctx.arc(cx - offset, cy - offset * 0.3, r1 * 0.15, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.arc(cx + offset, cy + offset * 0.3, r2 * 0.15, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;
}

function drawGear(ctx, cx, cy, r, teeth, color, alpha) {
  const toothDepth = r * 0.22;
  const toothWidth = (Math.PI * 2) / (teeth * 3);
  ctx.globalAlpha = alpha;
  ctx.beginPath();
  for (let i = 0; i < teeth; i++) {
    const a = (i / teeth) * Math.PI * 2 - Math.PI / 2;
    /* tooth tip */
    ctx.lineTo(
      cx + Math.cos(a - toothWidth) * (r + toothDepth),
      cy + Math.sin(a - toothWidth) * (r + toothDepth)
    );
    ctx.lineTo(
      cx + Math.cos(a + toothWidth) * (r + toothDepth),
      cy + Math.sin(a + toothWidth) * (r + toothDepth)
    );
    /* valley */
    const nextA = ((i + 0.5) / teeth) * Math.PI * 2 - Math.PI / 2;
    ctx.lineTo(
      cx + Math.cos(nextA - toothWidth) * r,
      cy + Math.sin(nextA - toothWidth) * r
    );
    ctx.lineTo(
      cx + Math.cos(nextA + toothWidth) * r,
      cy + Math.sin(nextA + toothWidth) * r
    );
  }
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
  /* inner ring cutout */
  ctx.globalAlpha = alpha * 0.4;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(cx, cy, r * 0.55, 0, Math.PI * 2);
  ctx.strokeStyle = color;
  ctx.stroke();
  ctx.globalAlpha = 1;
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

const drawFns = {
  connector: drawConnector,
  builder: drawBuilder,
  guide: drawGuide,
  solver: drawSolver,
};

/* ── Emblem component ── */
function Emblem({ type, color, size = 120 }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, size, size);
    const draw = drawFns[type];
    if (draw) draw(ctx, size / 2, size / 2, size, color);
  }, [type, color, size]);

  return <canvas ref={canvasRef} className="archetype-emblem-canvas" role="img" aria-label={`${type} archetype emblem`} />;
}

/* ── Main ArchetypeCard component ── */
function ArchetypeCard({ archetype, typeKey, mode = "full" }) {
  const [showResearch, setShowResearch] = useState(false);
  const [showGrowth, setShowGrowth] = useState(false);

  const [isDark, setIsDark] = useState(false);
  useEffect(() => {
    const check = () => {
      const dt = document.documentElement.getAttribute("data-theme");
      setIsDark(dt === "dark" || (dt !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches));
    };
    check();
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", check);
    const observer = new MutationObserver(check);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => { mq.removeEventListener("change", check); observer.disconnect(); };
  }, []);

  if (!archetype) return null;

  const color = isDark ? archetype.colorHex.dark : archetype.colorHex.light;

  /* Mini mode for dashboard header */
  if (mode === "mini") {
    return (
      <div className="archetype-mini" style={{ "--arch-color": color }}>
        <Emblem type={typeKey} color={color} size={48} />
        <div className="archetype-mini-info">
          <span className="archetype-mini-name">{archetype.name}</span>
          <span className="archetype-mini-tagline">{archetype.tagline}</span>
        </div>
      </div>
    );
  }

  /* Full type card for reveal */
  return (
    <div className="archetype-card" style={{ "--arch-color": color }}>
      {/* Emblem */}
      <div className="archetype-emblem-wrap">
        <Emblem type={typeKey} color={color} size={120} />
      </div>

      {/* Name + tagline */}
      <h2 className="archetype-card-name">{archetype.name}</h2>
      <p className="archetype-card-tagline">{archetype.tagline}</p>

      {/* Traits chips */}
      <div className="archetype-traits">
        {archetype.traits.map((t) => (
          <span key={t} className="archetype-trait">{t}</span>
        ))}
      </div>

      {/* Description */}
      <p className="archetype-card-desc">{archetype.description}</p>

      {/* Strengths */}
      <div className="archetype-section">
        <h3 className="archetype-section-label">Your strengths</h3>
        <ul className="archetype-strengths">
          {archetype.strengths.map((s) => (
            <li key={s} className="archetype-strength">
              <span className="strength-dot" />
              {s}
            </li>
          ))}
        </ul>
      </div>

      {/* Growth areas */}
      <div className="archetype-section">
        <button
          className="archetype-section-toggle"
          aria-expanded={showGrowth}
          onClick={() => setShowGrowth(!showGrowth)}
        >
          <h3 className="archetype-section-label">Growth edges</h3>
          <span className={`toggle-arrow ${showGrowth ? "open" : ""}`}>▾</span>
        </button>
        {showGrowth && (
          <ul className="archetype-growth">
            {archetype.growth.map((g) => (
              <li key={g} className="archetype-growth-item">{g}</li>
            ))}
          </ul>
        )}
      </div>

      {/* Research evidence */}
      <div className="archetype-section archetype-research-section">
        <button
          className="archetype-section-toggle"
          aria-expanded={showResearch}
          onClick={() => setShowResearch(!showResearch)}
        >
          <h3 className="archetype-section-label">The research</h3>
          <span className={`toggle-arrow ${showResearch ? "open" : ""}`}>▾</span>
        </button>
        {showResearch && (
          <div className="archetype-research">
            <p className="archetype-research-framework">
              <strong>Framework:</strong> {archetype.psychology.framework}
            </p>
            <ul className="archetype-research-list">
              {archetype.psychology.constructs.map((c) => (
                <li key={c} className="archetype-research-item">{c}</li>
              ))}
            </ul>
            <div className="archetype-research-impact">
              <strong>Impact evidence:</strong> {archetype.psychology.impact}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default React.memo(ArchetypeCard);
