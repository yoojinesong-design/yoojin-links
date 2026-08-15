"use client";

import React from "react";

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // In production, send to error reporting service
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  handleReset = () => {
    // Clear potentially corrupted localStorage data
    try {
      localStorage.removeItem("imprint_state");
    } catch {
      /* ignore */
    }
    this.setState({ hasError: false });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            minHeight: "100dvh",
            padding: "32px 24px",
            textAlign: "center",
            fontFamily: "system-ui, -apple-system, sans-serif",
            background: "var(--bg, #f2ede5)",
            color: "var(--text, #1c1917)",
          }}
        >
          <div style={{ fontSize: "48px", marginBottom: "16px" }}>🍀</div>
          <h1
            style={{
              fontSize: "20px",
              fontWeight: 700,
              marginBottom: "8px",
            }}
          >
            Something went wrong
          </h1>
          <p
            style={{
              fontSize: "15px",
              color: "var(--text-mid, #57534e)",
              maxWidth: "340px",
              lineHeight: 1.6,
              marginBottom: "24px",
            }}
          >
            The app ran into an unexpected error. You can try reloading, or reset
            your data if the issue persists.
          </p>
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", justifyContent: "center" }}>
            <button
              onClick={() => window.location.reload()}
              style={{
                padding: "10px 24px",
                fontSize: "15px",
                fontWeight: 600,
                borderRadius: "10px",
                border: "none",
                background: "var(--accent, #2a6f5e)",
                color: "#fff",
                cursor: "pointer",
              }}
            >
              Reload
            </button>
            <button
              onClick={this.handleReset}
              style={{
                padding: "10px 24px",
                fontSize: "15px",
                fontWeight: 600,
                borderRadius: "10px",
                border: "1.5px solid var(--border, #d6d3d1)",
                background: "transparent",
                color: "var(--text, #1c1917)",
                cursor: "pointer",
              }}
            >
              Reset &amp; retry
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
