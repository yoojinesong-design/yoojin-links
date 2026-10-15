"use client";

import React, { useEffect, useState } from "react";
import {
  quizCategories,
  archetypes,
  dimensionMeta,
  compositeTypes,
  compatibilityMap,
  getImprintCode,
  getDimensionScores,
  getPersonalityNarrative,
  getPrimaryDimension,
} from "../data/content";

function DimensionBar({ dimKey, catId, score, max, pct, isPrimary }) {
  const meta = dimensionMeta[catId]?.[dimKey];
  if (!meta) return null;
  const catClass = catId === "purpose" ? "purpose"
    : catId === "wellbeing" ? "wellbeing"
    : catId === "skills" ? "skills" : "values";

  return (
    <div className={`dna-bar ${isPrimary ? "dna-bar-primary" : ""}`}>
      <div className="dna-bar-header">
        <span className="dna-bar-label">{meta.label}</span>
        <span className="dna-bar-pct">{pct}%</span>
      </div>
      <div className="dna-bar-track">
        <div
          className={`dna-bar-fill dna-bar-${catClass}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function ImprintCodeChip({ item }) {
  return (
    <div className={`imprint-code-chip imprint-code-${item.catId}`}>
      <span className="imprint-code-short">{item.short}</span>
      <span className="imprint-code-label">{item.label}</span>
    </div>
  );
}

function CompatibilityCard({ purpose }) {
  const compat = compatibilityMap[purpose];
  if (!compat) return null;
  const bestArch = archetypes[compat.best];
  const growthArch = archetypes[compat.growth];
  if (!bestArch || !growthArch) return null;

  return (
    <div className="dna-compatibility">
      <h3 className="dna-section-label">Type Dynamics</h3>
      <div className="dna-compat-cards">
        <div className="dna-compat-card dna-compat-best">
          <div className="dna-compat-header">
            <span className="dna-compat-tag">Power pair</span>
          </div>
          <div className="dna-compat-name">{bestArch.name}</div>
          <p className="dna-compat-desc">{compat.bestDesc}</p>
        </div>
        <div className="dna-compat-card dna-compat-growth">
          <div className="dna-compat-header">
            <span className="dna-compat-tag">Growth partner</span>
          </div>
          <div className="dna-compat-name">{growthArch.name}</div>
          <p className="dna-compat-desc">{compat.growthDesc}</p>
        </div>
      </div>
    </div>
  );
}

function PersonalityDNA({ quizResults }) {
  const [animateIn, setAnimateIn] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setAnimateIn(true), 100);
    return () => clearTimeout(t);
  }, []);

  const completedCount = Object.keys(quizResults).length;
  if (completedCount === 0) return null;

  const code = getImprintCode(quizResults);
  const narrative = getPersonalityNarrative(quizResults);
  const purpose = quizResults.purpose ? getPrimaryDimension(quizResults.purpose.scores) : null;
  const skills = quizResults.skills ? getPrimaryDimension(quizResults.skills.scores) : null;
  const composite = purpose && skills ? compositeTypes[purpose]?.[skills] : null;

  const categoryLabels = {
    purpose: "Purpose",
    wellbeing: "Wellbeing",
    skills: "Skills",
    values: "Values",
  };

  return (
    <div className={`personality-dna ${animateIn ? "dna-visible" : ""}`}>
      <div className="dna-header">
        <h3 className="dna-title">Your Imprint Profile</h3>
        <p className="dna-subtitle">
          {completedCount < 4
            ? `${completedCount} of 4 dimensions mapped — complete more quizzes to unlock your full profile`
            : "Full personality profile unlocked"}
        </p>
      </div>

      {code.length > 0 && (
        <div className="imprint-code-row">
          {code.map((item, i) => (
            <React.Fragment key={item.catId}>
              {i > 0 && <span className="imprint-code-dot">·</span>}
              <ImprintCodeChip item={item} />
            </React.Fragment>
          ))}
        </div>
      )}

      {composite && (
        <div className="dna-composite">
          <span className="dna-composite-label">Your blend</span>
          <h4 className="dna-composite-name">{composite.name}</h4>
          <p className="dna-composite-desc">{composite.desc}</p>
        </div>
      )}

      <div className="dna-dimensions">
        {quizCategories.map((cat) => {
          const result = quizResults[cat.id];
          if (!result) return null;
          const scores = getDimensionScores(result.scores, cat.questions.length);
          const primary = getPrimaryDimension(result.scores);
          return (
            <div key={cat.id} className="dna-category">
              <div className="dna-category-header">
                <span className="dna-category-icon">{cat.icon}</span>
                <span className="dna-category-name">{categoryLabels[cat.id]}</span>
              </div>
              <div className="dna-bars">
                {scores.map((s) => (
                  <DimensionBar
                    key={s.key}
                    dimKey={s.key}
                    catId={cat.id}
                    score={s.score}
                    max={s.max}
                    pct={s.pct}
                    isPrimary={s.key === primary}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {narrative.length > 0 && (
        <div className="dna-narrative">
          <h3 className="dna-section-label">What this means</h3>
          {narrative.map((p, i) => (
            <p key={i} className="dna-narrative-p">{p}</p>
          ))}
        </div>
      )}

      {purpose && <CompatibilityCard purpose={purpose} />}
    </div>
  );
}

export default React.memo(PersonalityDNA);
