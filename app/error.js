"use client";

import { useEffect } from "react";

export default function Error({ error, reset }) {
  useEffect(() => {
    console.error("Uncaught app error:", error);
  }, [error]);

  return (
    <div
      style={{
        minHeight: "100dvh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "40px 24px",
        textAlign: "center",
        fontFamily: "system-ui, -apple-system, sans-serif",
        background: "var(--bg, #f2ede5)",
        color: "var(--text, #1c1917)",
      }}
    >
      <div style={{ fontSize: "48px", marginBottom: "16px" }}>🍀</div>
      <h2 style={{ fontSize: "20px", fontWeight: 700, marginBottom: "8px" }}>
        Something went wrong
      </h2>
      <p
        style={{
          fontSize: "14px",
          color: "var(--text-mid, #57534e)",
          marginBottom: "24px",
          maxWidth: "360px",
          lineHeight: 1.6,
        }}
      >
        We hit an unexpected error. Your data is safe — try refreshing to get back on track.
      </p>
      <button
        onClick={reset}
        style={{
          padding: "12px 28px",
          fontSize: "15px",
          fontWeight: 600,
          color: "#fff",
          background: "var(--accent, #2a6f5e)",
          border: "none",
          borderRadius: "10px",
          cursor: "pointer",
        }}
      >
        Try again
      </button>
    </div>
  );
}
