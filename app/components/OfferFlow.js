"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { offerCategories } from "../data/content";
import { getCurrentPosition } from "../lib/native";

/* ── Ticket platform definitions ── */
const ticketPlatforms = [
  { id: "ticketmaster", prefix: "tm-", name: "Ticketmaster", color: "#026cdf" },
  { id: "axs", prefix: "axs-", name: "AXS", color: "#ff5722" },
  { id: "seatgeek", prefix: "sg-", name: "SeatGeek", color: "#44b244" },
  { id: "eventbrite", prefix: "eb-", name: "Eventbrite", color: "#f05537" },
];

/* Simulated tickets that would come from the platform API */
const mockTickets = {
  ticketmaster: [
    { id: "tm-1", event: "Lakers vs. Celtics", venue: "Crypto.com Arena", date: "Aug 22, 2026 · 7:30 PM", section: "Section 108, Row D", seats: "Seats 7–8", qty: 2, faceValue: 285, status: "valid", barcode: "TM-9284-7291-0042" },
    { id: "tm-2", event: "Billie Eilish — Hit Me Hard and Soft Tour", venue: "SoFi Stadium", date: "Sep 14, 2026 · 8:00 PM", section: "Floor GA", seats: "General Admission", qty: 2, faceValue: 195, status: "valid", barcode: "TM-6138-4420-1187" },
    { id: "tm-3", event: "Dodgers vs. Yankees", venue: "Dodger Stadium", date: "Aug 30, 2026 · 1:10 PM", section: "Loge 151, Row A", seats: "Seats 1–4", qty: 4, faceValue: 89, status: "valid", barcode: "TM-3305-8817-2294" },
  ],
  axs: [
    { id: "axs-1", event: "Coachella 2027 — Weekend 1", venue: "Empire Polo Club", date: "Apr 11–13, 2027", section: "GA", seats: "General Admission", qty: 1, faceValue: 599, status: "valid", barcode: "AXS-7712-3390" },
    { id: "axs-2", event: "LA Kings vs. Rangers", venue: "Crypto.com Arena", date: "Oct 8, 2026 · 7:00 PM", section: "Section 302, Row 5", seats: "Seats 11–12", qty: 2, faceValue: 78, status: "valid", barcode: "AXS-4481-1126" },
  ],
  seatgeek: [
    { id: "sg-1", event: "Hamilton", venue: "Pantages Theatre", date: "Sep 5, 2026 · 8:00 PM", section: "Orchestra, Row K", seats: "Seats 14–15", qty: 2, faceValue: 250, status: "valid", barcode: "SG-2209-5534-8871" },
  ],
  eventbrite: [
    { id: "eb-1", event: "LA Food & Wine Festival", venue: "Grand Park", date: "Sep 20, 2026 · 12:00 PM", section: "VIP", seats: "VIP Access", qty: 2, faceValue: 175, status: "valid", barcode: "EB-6633-2210-4455" },
  ],
};

const taxRates = {
  tickets: { label: "Verified Face Value (platform-confirmed)", rate: 1.0 },
  food: { label: "Enhanced deduction (~75%)", rate: 0.75 },
  services: { label: "Not deductible (IRS rule)", rate: 0 },
  goods: { label: "Fair Market Value", rate: 1.0 },
};

const taxTips = {
  tickets: "Ticket face value is confirmed directly by the platform — no appraisal needed. As a 501(c)(3), your donation receipt is generated automatically with verified pricing.",
  food: "Food donations by businesses qualify for enhanced deductions (up to 15% of AGI). Individuals can deduct the cost basis.",
  services: "The IRS doesn't allow deductions for donated services — but your out-of-pocket expenses (materials, travel) are deductible.",
  goods: "Donated goods in good or better condition are deductible at fair market value. Items over $5,000 require an independent appraisal.",
};

export default function OfferFlow({ onBack, onSubmit }) {
  /* ── General flow state ── */
  const [step, setStep] = useState("choose");
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [formData, setFormData] = useState({});
  const [donorName, setDonorName] = useState("");
  const [donorEmail, setDonorEmail] = useState("");

  /* ── Handoff verification state ── */
  const [handoffPhase, setHandoffPhase] = useState(null); // null|pass|locating|nearby|tapping|confirming|verified
  const [donationId, setDonationId] = useState(null);
  const [gpsCoords, setGpsCoords] = useState(null);
  const [handoffTime, setHandoffTime] = useState(null);
  const [recipientOrg, setRecipientOrg] = useState("");

  /* ── Interval/timer refs for cleanup ── */
  const intervalRef = useRef(null);
  const timersRef = useRef(new Set());
  const trackTimeout = useCallback((fn, ms) => {
    const id = setTimeout(() => { timersRef.current.delete(id); fn(); }, ms);
    timersRef.current.add(id);
    return id;
  }, []);

  /* ── Ticket-specific state ── */
  const [ticketStep, setTicketStep] = useState("platforms"); // platforms | connecting | tickets | review | transferring | done
  const [selectedPlatform, setSelectedPlatform] = useState(null);
  const [connectedPlatforms, setConnectedPlatforms] = useState({});
  const [availableTickets, setAvailableTickets] = useState([]);
  const [selectedTickets, setSelectedTickets] = useState(new Set());
  const [verifyingIds, setVerifyingIds] = useState(new Set());
  const [verifiedIds, setVerifiedIds] = useState(new Set());
  const [transferProgress, setTransferProgress] = useState(0);

  const category = selectedCategory
    ? offerCategories.find((c) => c.id === selectedCategory)
    : null;

  /* ── Email validation ── */
  const isValidEmail = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  /* ── Ticket platform connect (simulated OAuth) ── */
  const connectPlatform = useCallback((platformId) => {
    if (connectedPlatforms[platformId]) return; // already connected
    setSelectedPlatform(platformId);
    setTicketStep("connecting");

    /* Simulate OAuth redirect + callback */
    trackTimeout(() => {
      setConnectedPlatforms((prev) => ({ ...prev, [platformId]: true }));
      const tickets = mockTickets[platformId] || [];
      setAvailableTickets((prev) => {
        const existingIds = new Set(prev.map((t) => t.id));
        return [...prev, ...tickets.filter((t) => !existingIds.has(t.id))];
      });
      setTicketStep("tickets");
    }, 1800);
  }, [trackTimeout, connectedPlatforms]);

  /* ── Ticket selection ── */
  const toggleTicket = (ticketId) => {
    setSelectedTickets((prev) => {
      const next = new Set(prev);
      if (next.has(ticketId)) next.delete(ticketId);
      else next.add(ticketId);
      return next;
    });
  };

  /* ── Verify a ticket (simulated API call) ── */
  const verifyTicket = (ticketId) => {
    setVerifyingIds((prev) => new Set([...prev, ticketId]));
    trackTimeout(() => {
      setVerifiedIds((prev) => new Set([...prev, ticketId]));
      setVerifyingIds((prev) => { const next = new Set(prev); next.delete(ticketId); return next; });
    }, 1200);
  };

  /* ── Transfer tickets ── */
  const startTransfer = () => {
    if (intervalRef.current) return; // guard against double-call
    if (selectedTickets.size === 0) return; // guard: nothing to transfer
    setTicketStep("transferring");
    setTransferProgress(0);
    const total = selectedTickets.size;
    let done = 0;
    intervalRef.current = setInterval(() => {
      done++;
      setTransferProgress(Math.round((done / total) * 100));
      if (done >= total) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
        trackTimeout(() => setTicketStep("done"), 600);
      }
    }, 900);
  };

  /* ── Cleanup interval and timers on unmount ── */
  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      timersRef.current.forEach(clearTimeout);
      timersRef.current.clear();
    };
  }, []);

  /* ── Computed ticket values ── */
  const selectedTicketList = availableTickets.filter((t) => selectedTickets.has(t.id));
  const totalTicketValue = selectedTicketList.reduce((sum, t) => sum + t.faceValue * t.qty, 0);
  const totalTicketQty = selectedTicketList.reduce((sum, t) => sum + t.qty, 0);
  const allSelectedVerified = selectedTicketList.every((t) => verifiedIds.has(t.id));

  /* ── Category select ── */
  const handleCategorySelect = (catId) => {
    setSelectedCategory(catId);
    setEmailError(false);
    if (catId === "tickets") {
      setTicketStep("platforms");
      setSelectedPlatform(null);
      setAvailableTickets([]);
      setSelectedTickets(new Set());
      setVerifiedIds(new Set());
      setStep("tickets");
    } else {
      setFormData({});
      setStep("form");
    }
  };

  /* ── Generic form handlers ── */
  const handleFieldChange = (key, value) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
  };

  const [emailError, setEmailError] = useState(false);
  const handleFormSubmit = (e) => {
    e.preventDefault();
    if (donorEmail && !isValidEmail(donorEmail)) {
      setEmailError(true);
      return;
    }
    setEmailError(false);
    setStep("preview");
  };

  /* ── Generate donation ID ── */
  const genDonationId = () => {
    const t = Date.now().toString(36).toUpperCase();
    return `IMP-${t.slice(-4)}-${Math.random().toString(36).substring(2, 6).toUpperCase()}`;
  };

  /* ── QR-like visual pattern from ID ── */
  const qrCells = (id) => {
    let seed = 0;
    for (let i = 0; i < id.length; i++) seed = ((seed << 5) - seed + id.charCodeAt(i)) | 0;
    const s = 11, cells = [];
    for (let y = 0; y < s; y++) for (let x = 0; x < s; x++) {
      const corner = (x < 3 && y < 3) || (x >= s - 3 && y < 3) || (x < 3 && y >= s - 3);
      const ring = corner && (x % 2 === 0 || y % 2 === 0);
      const center = (x === 1 && y === 1) || (x === s - 2 && y === 1) || (x === 1 && y === s - 2);
      const fill = corner ? (ring || center) : (((seed * (y * s + x + 1) * 7919) & 0xFF) > 105);
      if (fill) cells.push({ x, y });
    }
    return cells;
  };

  /* ── Handoff verification flow ── */
  const handoffCancelledRef = useRef(false);
  const startHandoff = () => {
    handoffCancelledRef.current = false;
    setHandoffPhase("locating");
    getCurrentPosition()
      .then((coords) => {
        if (handoffCancelledRef.current) return;
        setGpsCoords({ lat: coords.latitude.toFixed(4), lng: coords.longitude.toFixed(4), acc: Math.round(coords.accuracy || 0) });
        trackTimeout(() => { if (!handoffCancelledRef.current) setHandoffPhase("nearby"); }, 1800);
      })
      .catch(() => {
        if (handoffCancelledRef.current) return;
        /* Location denied or unavailable — don't fabricate coordinates */
        setGpsCoords(null);
        setHandoffPhase("nearby");
      });
  };

  const startTap = () => {
    handoffCancelledRef.current = false;
    setHandoffPhase("tapping");
    /* Simulate NFC/QR — in production: Web NFC API or camera QR scan */
    trackTimeout(() => { if (!handoffCancelledRef.current) setHandoffPhase("confirming"); }, 2800);
  };

  const cancelHandoff = () => {
    handoffCancelledRef.current = true;
    // Clear all pending handoff timers
    timersRef.current.forEach(clearTimeout);
    timersRef.current.clear();
    setHandoffPhase("pass");
  };

  const handoffSubmittedRef = useRef(false);
  const confirmHandoff = () => {
    if (!category) return;
    if (handoffSubmittedRef.current) return;
    handoffSubmittedRef.current = true;
    const now = new Date();
    setHandoffTime(now.toLocaleString());
    setHandoffPhase("verified");
    const value = parseFloat(formData.value) || 0;
    const tax = taxRates[selectedCategory];
    const deduction = value * tax.rate;
    onSubmit({
      category: selectedCategory,
      categoryName: category.name,
      icon: category.icon,
      formData,
      donorName,
      donorEmail,
      estimatedValue: value,
      estimatedDeduction: deduction,
      verified: true,
      donationId,
      gpsCoords,
      handoffTime: now.toISOString(),
      recipientOrg,
    });
  };

  const servicesSubmittedRef = useRef(false);
  const handleConfirm = () => {
    if (!category) return;
    /* Instead of immediate "done", generate a Donation Pass for handoff verification */
    if (selectedCategory === "services") {
      /* Services: no physical handoff needed — submit directly */
      if (servicesSubmittedRef.current) return;
      servicesSubmittedRef.current = true;
      const value = (parseFloat(formData.hours) || 0) * (parseFloat(formData.value) || 0);
      const tax = taxRates[selectedCategory];
      const deduction = value * tax.rate;
      onSubmit({ category: selectedCategory, categoryName: category.name, icon: category.icon, formData, donorName, donorEmail, estimatedValue: value, estimatedDeduction: deduction });
      setStep("done");
    } else {
      /* Food & Goods: create Donation Pass for verified handoff */
      setDonationId(genDonationId());
      setHandoffPhase("pass");
      setStep("pass");
    }
  };

  /* ── Ticket donation submit (guarded against double-call) ── */
  const ticketSubmittedRef = useRef(false);
  const handleTicketDone = () => {
    if (ticketSubmittedRef.current) return;
    ticketSubmittedRef.current = true;
    onSubmit({
      category: "tickets",
      categoryName: "Tickets",
      icon: "🎟️",
      formData: { tickets: selectedTicketList },
      donorName,
      donorEmail,
      estimatedValue: totalTicketValue,
      estimatedDeduction: totalTicketValue,
    });
  };

  const handleStartOver = () => {
    // Cancel any in-flight timers (e.g. connectPlatform, verifyTicket, handoff animations)
    timersRef.current.forEach(clearTimeout);
    timersRef.current.clear();
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    setStep("choose");
    setSelectedCategory(null);
    setFormData({});
    setDonorName("");
    setDonorEmail("");
    setTicketStep("platforms");
    setConnectedPlatforms({});
    setAvailableTickets([]);
    setSelectedTickets(new Set());
    setVerifiedIds(new Set());
    setTransferProgress(0);
    setHandoffPhase(null);
    setDonationId(null);
    setGpsCoords(null);
    setHandoffTime(null);
    setRecipientOrg("");
    setSelectedPlatform(null);
    setVerifyingIds(new Set());
    setEmailError(false);
    ticketSubmittedRef.current = false;
    handoffSubmittedRef.current = false;
    servicesSubmittedRef.current = false;
  };

  const estimatedValue = selectedCategory === "services"
    ? (parseFloat(formData.hours) || 0) * (parseFloat(formData.value) || 0)
    : parseFloat(formData.value) || 0;
  const tax = selectedCategory ? taxRates[selectedCategory] : null;
  const estimatedDeduction = tax ? estimatedValue * tax.rate : 0;

  return (
    <div className="offer-flow">
      {/* ═══════════════════════ Choose Category ═══════════════════════ */}
      {step === "choose" && (
        <div className="offer-step offer-step-visible">
          <button className="btn-back" onClick={onBack}>← Back to profile</button>
          <div className="offer-header">
            <p className="offer-eyebrow">Give back</p>
            <h2 className="offer-title">I have something to offer</h2>
            <p className="offer-subtitle">
              Your donation goes directly to community members earning their impact.
              As a 501(c)(3) nonprofit, all eligible donations are tax-deductible.
            </p>
          </div>
          <div className="offer-categories">
            {offerCategories.map((cat) => (
              <button
                key={cat.id}
                className="offer-cat-card"
                aria-label={`${cat.name}: ${cat.tagline}`}
                onClick={() => handleCategorySelect(cat.id)}
              >
                <div className="offer-cat-icon">{cat.icon}</div>
                <div className="offer-cat-info">
                  <h3 className="offer-cat-name">{cat.name}</h3>
                  <p className="offer-cat-tagline">{cat.tagline}</p>
                </div>
                <span className="offer-cat-arrow">→</span>
              </button>
            ))}
          </div>
          <div className="offer-tax-note">
            <span className="offer-tax-icon">📋</span>
            <p>
              <strong>imprint</strong> is a registered 501(c)(3) nonprofit.
              Eligible donations receive a tax receipt automatically.
            </p>
          </div>
        </div>
      )}

      {/* ═══════════════════════ TICKET FLOW ═══════════════════════ */}
      {step === "tickets" && (
        <div className="offer-step offer-step-visible">
          {ticketStep !== "connecting" && ticketStep !== "transferring" && ticketStep !== "done" && (
            <button className="btn-back" onClick={() => {
              if (ticketStep === "tickets" || ticketStep === "platforms") {
                setStep("choose");
              } else if (ticketStep === "review") {
                setTicketStep("tickets");
              }
            }}>
              ← {ticketStep === "review" ? "Back to tickets" : "Back to categories"}
            </button>
          )}

          {/* ── Platform Connect ── */}
          {ticketStep === "platforms" && (
            <>
              <div className="offer-form-header">
                <span className="offer-form-icon">🎟️</span>
                <h2 className="offer-form-title">Connect your tickets</h2>
                <p className="offer-form-detail">
                  Link your ticket account and we&apos;ll pull in your upcoming events.
                  Select the ones you can&apos;t attend — we&apos;ll transfer them securely.
                </p>
              </div>

              <div className="ticket-platforms">
                {ticketPlatforms.map((p) => {
                  const isConnected = connectedPlatforms[p.id];
                  return (
                    <button
                      key={p.id}
                      className={`ticket-platform-btn ${isConnected ? "connected" : ""}`}
                      onClick={() => !isConnected && connectPlatform(p.id)}
                      disabled={isConnected}
                    >
                      <div
                        className="ticket-platform-dot"
                        style={{ background: p.color }}
                      />
                      <span className="ticket-platform-name">{p.name}</span>
                      {isConnected ? (
                        <span className="ticket-platform-status connected">✓ Connected</span>
                      ) : (
                        <span className="ticket-platform-status">Connect →</span>
                      )}
                    </button>
                  );
                })}
              </div>

              <div className="ticket-security-note">
                <span className="ticket-security-icon">🔒</span>
                <p>
                  We use secure OAuth — we never see your password.
                  Tickets are transferred directly through the platform&apos;s official API.
                </p>
              </div>

              {availableTickets.length > 0 && (
                <button
                  className="btn-continue btn-wide"
                  onClick={() => setTicketStep("tickets")}
                  style={{ marginTop: 20 }}
                >
                  View your tickets ({availableTickets.length}) <span className="arrow">→</span>
                </button>
              )}
            </>
          )}

          {/* ── Connecting Animation ── */}
          {ticketStep === "connecting" && (
            <div className="ticket-connecting">
              <div className="ticket-connecting-spinner" />
              <p className="ticket-connecting-text">
                Connecting to {ticketPlatforms.find((p) => p.id === selectedPlatform)?.name}…
              </p>
              <p className="ticket-connecting-sub">Securely authenticating via OAuth</p>
            </div>
          )}

          {/* ── Ticket List ── */}
          {ticketStep === "tickets" && (
            <>
              <div className="ticket-list-header">
                <h2 className="ticket-list-title">Your upcoming events</h2>
                <p className="ticket-list-subtitle">
                  Select the tickets you&apos;d like to donate. They&apos;ll be verified before transfer.
                </p>
                <div className="ticket-connected-badges">
                  {Object.keys(connectedPlatforms).map((pid) => {
                    const p = ticketPlatforms.find((tp) => tp.id === pid);
                    return (
                      <span key={pid} className="ticket-connected-badge" style={{ borderColor: p?.color }}>
                        <span className="ticket-badge-dot" style={{ background: p?.color }} />
                        {p?.name}
                      </span>
                    );
                  })}
                  <button className="ticket-add-platform" onClick={() => setTicketStep("platforms")}>
                    + Add platform
                  </button>
                </div>
              </div>

              <div className="ticket-list">
                {availableTickets.map((ticket) => {
                  const isSelected = selectedTickets.has(ticket.id);
                  const isVerified = verifiedIds.has(ticket.id);
                  const isVerifying = verifyingIds.has(ticket.id);
                  const platform = ticketPlatforms.find((p) =>
                    ticket.id.startsWith(p.prefix)
                  );

                  return (
                    <div
                      key={ticket.id}
                      className={`ticket-card ${isSelected ? "selected" : ""}`}
                      onClick={() => toggleTicket(ticket.id)}
                      role="checkbox"
                      aria-checked={isSelected}
                      aria-label={`${ticket.event} — $${ticket.faceValue} × ${ticket.qty}`}
                      tabIndex={0}
                      onKeyDown={(e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); toggleTicket(ticket.id); }}}
                    >
                      <div className="ticket-card-check">
                        <div className={`ticket-checkbox ${isSelected ? "checked" : ""}`}>
                          {isSelected && <span>✓</span>}
                        </div>
                      </div>
                      <div className="ticket-card-body">
                        <div className="ticket-card-top">
                          <h3 className="ticket-event-name">{ticket.event}</h3>
                          <div className="ticket-face-value">
                            ${ticket.faceValue}
                            <span className="ticket-face-label">×{ticket.qty}</span>
                          </div>
                        </div>
                        <div className="ticket-card-details">
                          <span>📍 {ticket.venue}</span>
                          <span>📅 {ticket.date}</span>
                          <span>💺 {ticket.section} · {ticket.seats}</span>
                        </div>
                        <div className="ticket-card-bottom">
                          <span className="ticket-barcode">{ticket.barcode}</span>
                          <div className="ticket-verify-area">
                            {isVerified ? (
                              <span className="ticket-verified-badge">
                                <span className="ticket-verified-check">✓</span> Verified
                              </span>
                            ) : isVerifying ? (
                              <span className="ticket-verifying">
                                <span className="ticket-verify-spinner" /> Verifying…
                              </span>
                            ) : isSelected ? (
                              <button
                                className="ticket-verify-btn"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  verifyTicket(ticket.id);
                                }}
                              >
                                Verify ticket
                              </button>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {selectedTickets.size > 0 && (
                <div className="ticket-selection-bar">
                  <div className="ticket-selection-info">
                    <span className="ticket-selection-count">
                      {totalTicketQty} ticket{totalTicketQty !== 1 ? "s" : ""} selected
                    </span>
                    <span className="ticket-selection-value">
                      ${totalTicketValue.toLocaleString()} face value
                    </span>
                  </div>
                  <button
                    className="btn-continue"
                    onClick={() => setTicketStep("review")}
                  >
                    Review &amp; transfer <span className="arrow">→</span>
                  </button>
                </div>
              )}
            </>
          )}

          {/* ── Review & Transfer ── */}
          {ticketStep === "review" && (
            <>
              <div className="offer-preview-header">
                <span className="offer-preview-icon">🎟️</span>
                <h2 className="offer-preview-title">Review &amp; transfer</h2>
              </div>

              <div className="offer-summary-card">
                <h3 className="offer-summary-label">Tickets to donate</h3>
                <div className="ticket-review-list">
                  {selectedTicketList.map((ticket) => (
                    <div key={ticket.id} className="ticket-review-item">
                      <div className="ticket-review-event">
                        <span className="ticket-review-name">{ticket.event}</span>
                        <span className="ticket-review-date">{ticket.date}</span>
                      </div>
                      <div className="ticket-review-right">
                        <span className="ticket-review-price">
                          ${(ticket.faceValue * ticket.qty).toLocaleString()}
                        </span>
                        {verifiedIds.has(ticket.id) ? (
                          <span className="ticket-verified-badge small">✓</span>
                        ) : (
                          <button
                            className="ticket-verify-btn small"
                            onClick={() => verifyTicket(ticket.id)}
                          >
                            Verify
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="offer-tax-card">
                <h3 className="offer-tax-heading">Tax benefit — platform verified</h3>
                <div className="offer-tax-breakdown">
                  <div className="offer-tax-row">
                    <span>Total face value</span>
                    <span className="offer-tax-amount">${totalTicketValue.toLocaleString()}</span>
                  </div>
                  <div className="offer-tax-row">
                    <span>Verification</span>
                    <span className="offer-tax-method">
                      {allSelectedVerified ? "✓ All tickets verified" : `${verifiedIds.size}/${selectedTickets.size} verified`}
                    </span>
                  </div>
                  <div className="offer-tax-row offer-tax-total">
                    <span>Tax deduction</span>
                    <span className="offer-tax-deduction">${totalTicketValue.toLocaleString()}</span>
                  </div>
                </div>
                <p className="offer-tax-tip">{taxTips.tickets}</p>
              </div>

              {!allSelectedVerified && (
                <p className="ticket-verify-all-note">
                  Verify all tickets before transferring for the strongest tax documentation.
                </p>
              )}

              <div className="offer-field" style={{ marginBottom: 12 }}>
                <label className="offer-label" htmlFor="ticket-donor-name">Your name (for receipt)</label>
                <input
                  id="ticket-donor-name"
                  className="offer-input"
                  type="text"
                  placeholder="Full legal name"
                  value={donorName}
                  onChange={(e) => setDonorName(e.target.value)}
                />
              </div>
              <div className="offer-field" style={{ marginBottom: 20 }}>
                <label className="offer-label" htmlFor="ticket-donor-email">Email</label>
                <input
                  id="ticket-donor-email"
                  className="offer-input"
                  type="email"
                  placeholder="We'll send your receipt here"
                  value={donorEmail}
                  onChange={(e) => setDonorEmail(e.target.value)}
                />
              </div>

              {donorEmail && !isValidEmail(donorEmail) && (
                <p className="auth-error" role="alert" style={{ fontSize: "0.82rem", color: "var(--danger)", marginBottom: "8px" }}>
                  Please enter a valid email address.
                </p>
              )}
              <button
                className="btn-continue btn-wide"
                onClick={startTransfer}
                disabled={!donorName || !donorEmail || !isValidEmail(donorEmail)}
              >
                Transfer {totalTicketQty} ticket{totalTicketQty !== 1 ? "s" : ""} to imprint <span className="arrow">→</span>
              </button>

              <p className="ticket-transfer-note">
                Tickets are transferred via the platform&apos;s official transfer API.
                The recipient will receive them in their imprint account.
              </p>
            </>
          )}

          {/* ── Transferring ── */}
          {ticketStep === "transferring" && (
            <div className="ticket-connecting">
              <div className="ticket-transfer-progress">
                <div
                  className="ticket-transfer-fill"
                  style={{ width: `${transferProgress}%` }}
                />
              </div>
              <p className="ticket-connecting-text">
                Transferring tickets…
              </p>
              <p className="ticket-connecting-sub">
                {transferProgress}% — Securely moving to imprint&apos;s verified account
              </p>
            </div>
          )}

          {/* ── Done ── */}
          {ticketStep === "done" && (
            <div className="offer-done">
              <div className="offer-done-icon">✦</div>
              <h2 className="offer-done-title">Tickets transferred</h2>
              <p className="offer-done-text">
                {totalTicketQty} ticket{totalTicketQty !== 1 ? "s" : ""} have been
                securely transferred to imprint. We&apos;ll match them with a community
                member who earned it. Your tax receipt is on its way to{" "}
                <strong>{donorEmail}</strong>.
              </p>

              <div className="offer-done-deduction">
                <span className="offer-done-deduction-label">Verified tax deduction</span>
                <span className="offer-done-deduction-amount">
                  ${totalTicketValue.toLocaleString()}
                </span>
              </div>

              <div className="ticket-done-details">
                {selectedTicketList.map((t) => (
                  <div key={t.id} className="ticket-done-item">
                    <span className="ticket-done-check">✓</span>
                    <span>{t.event} — {t.qty} ticket{t.qty !== 1 ? "s" : ""}</span>
                  </div>
                ))}
              </div>

              <div className="offer-done-actions">
                <button className="btn-continue" onClick={() => { handleTicketDone(); handleStartOver(); }}>
                  Donate something else
                </button>
                <button className="btn-small btn-small-outline" onClick={() => { handleTicketDone(); onBack(); }}>
                  Back to profile
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════ Generic Form (food/services/goods) ═══════════════════ */}
      {step === "form" && category && (
        <div className="offer-step offer-step-visible">
          <button className="btn-back" onClick={() => setStep("choose")}>← Back to categories</button>
          <div className="offer-form-header">
            <span className="offer-form-icon">{category.icon}</span>
            <h2 className="offer-form-title">{category.name}</h2>
            <p className="offer-form-detail">{category.detail}</p>
          </div>
          <form className="offer-form" onSubmit={handleFormSubmit}>
            {category.fields.map((field) => (
              <div key={field.key} className="offer-field">
                <label className="offer-label" htmlFor={`offer-${field.key}`}>{field.label}</label>
                {field.type === "select" ? (
                  <select id={`offer-${field.key}`} className="offer-input offer-select" value={formData[field.key] || ""} onChange={(e) => handleFieldChange(field.key, e.target.value)} required>
                    <option value="" disabled>Select…</option>
                    {field.options.map((opt) => (<option key={opt} value={opt}>{opt}</option>))}
                  </select>
                ) : (
                  <input id={`offer-${field.key}`} className="offer-input" type={field.type} placeholder={field.placeholder} value={formData[field.key] || ""} onChange={(e) => handleFieldChange(field.key, e.target.value)} required />
                )}
              </div>
            ))}
            <div className="offer-divider" />
            <div className="offer-field">
              <label className="offer-label" htmlFor="offer-donor-name">Your name</label>
              <input id="offer-donor-name" className="offer-input" type="text" placeholder="For the tax receipt" value={donorName} onChange={(e) => setDonorName(e.target.value)} required />
            </div>
            <div className="offer-field">
              <label className="offer-label" htmlFor="offer-donor-email">Email</label>
              <input id="offer-donor-email" className="offer-input" type="email" placeholder="We'll send your receipt here" value={donorEmail} onChange={(e) => { setDonorEmail(e.target.value); setEmailError(false); }} required />
              {emailError && (
                <p className="auth-error" role="alert" style={{ fontSize: "0.82rem", color: "var(--danger)", marginTop: "4px" }}>
                  Please enter a valid email address.
                </p>
              )}
            </div>
            <button type="submit" className="btn-continue btn-wide offer-submit">
              Preview &amp; confirm <span className="arrow">→</span>
            </button>
          </form>
        </div>
      )}

      {/* ═══════════════════ Generic Preview (food/services/goods) ═══════════════════ */}
      {step === "preview" && category && tax && (
        <div className="offer-step offer-step-visible">
          <button className="btn-back" onClick={() => setStep("form")}>← Edit details</button>
          <div className="offer-preview-header">
            <span className="offer-preview-icon">{category.icon}</span>
            <h2 className="offer-preview-title">Confirm your offer</h2>
          </div>
          <div className="offer-summary-card">
            <h3 className="offer-summary-label">What you&apos;re donating</h3>
            <div className="offer-summary-fields">
              {category.fields.map((field) => (
                <div key={field.key} className="offer-summary-row">
                  <span className="offer-summary-key">{field.label}</span>
                  <span className="offer-summary-val">{field.key === "value" ? `$${formData[field.key] || "0"}` : formData[field.key] || "—"}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="offer-tax-card">
            <h3 className="offer-tax-heading">Tax benefit estimate</h3>
            <div className="offer-tax-breakdown">
              <div className="offer-tax-row"><span>Estimated value</span><span className="offer-tax-amount">${estimatedValue.toLocaleString()}</span></div>
              <div className="offer-tax-row"><span>Deduction method</span><span className="offer-tax-method">{tax.label}</span></div>
              <div className="offer-tax-row offer-tax-total"><span>Estimated deduction</span><span className="offer-tax-deduction">{estimatedDeduction > 0 ? `$${estimatedDeduction.toLocaleString()}` : "N/A"}</span></div>
            </div>
            <p className="offer-tax-tip">{taxTips[selectedCategory]}</p>
            <p className="offer-tax-disclaimer">This is an estimate only. Consult a tax professional for your specific situation.</p>
          </div>
          <div className="offer-confirm-actions">
            <button className="btn-continue btn-wide" onClick={handleConfirm}>Confirm donation <span className="arrow">→</span></button>
          </div>
        </div>
      )}

      {/* ═══════════════════ Donation Pass + Handoff (food/goods) ═══════════════════ */}
      {step === "pass" && category && (
        <div className="offer-step offer-step-visible" aria-live="polite">

          {/* ── Pass Card ── */}
          {handoffPhase === "pass" && (
            <>
              <button className="btn-back" onClick={() => setStep("preview")}>← Edit details</button>
              <div className="donation-pass-card">
                <div className="donation-pass-status">
                  <span className="pass-status-dot pending" />
                  <span>Pending Handoff</span>
                </div>
                <div className="donation-pass-top">
                  <div className="donation-pass-icon">{category.icon}</div>
                  <div className="donation-pass-info">
                    <h2 className="donation-pass-title">{category.name} Donation</h2>
                    <p className="donation-pass-id">{donationId}</p>
                  </div>
                </div>
                <div className="donation-pass-qr">
                  <svg viewBox="0 0 44 44" className="qr-visual" role="img" aria-label="Donation QR code">
                    {qrCells(donationId || "").map((c) => (
                      <rect key={`${c.x}-${c.y}`} x={c.x * 4} y={c.y * 4} width={3.4} height={3.4} rx={0.4} fill="currentColor" />
                    ))}
                  </svg>
                  <p className="qr-hint">Show this to the receiving organization</p>
                </div>
                <div className="donation-pass-details">
                  {category.fields.filter(f => formData[f.key]).map((field) => (
                    <div key={field.key} className="pass-detail-row">
                      <span className="pass-detail-label">{field.label}</span>
                      <span className="pass-detail-value">{field.key === "value" ? `$${formData[field.key]}` : formData[field.key]}</span>
                    </div>
                  ))}
                  <div className="pass-detail-row">
                    <span className="pass-detail-label">Donor</span>
                    <span className="pass-detail-value">{donorName}</span>
                  </div>
                </div>
                <div className="donation-pass-footer">
                  <span>imprint verified donation</span>
                </div>
              </div>

              <button className="btn-continue btn-wide handoff-start-btn" onClick={startHandoff}>
                📍 Verify at location <span className="arrow">→</span>
              </button>
              <p className="handoff-help-text">
                Go to the partner organization and tap to verify the handoff. This creates a verified, location-stamped proof of your donation.
              </p>
            </>
          )}

          {/* ── Locating ── */}
          {handoffPhase === "locating" && (
            <div className="handoff-center">
              <div className="handoff-pulse-ring">
                <div className="handoff-pulse-dot" />
              </div>
              <h3 className="handoff-phase-title">Finding your location…</h3>
              <p className="handoff-phase-sub">GPS accuracy improves over a few seconds</p>
              <button className="btn-small btn-small-outline" style={{ marginTop: 20 }} onClick={cancelHandoff}>Cancel</button>
            </div>
          )}

          {/* ── Nearby ── */}
          {handoffPhase === "nearby" && (
            <div className="handoff-center">
              <div className="handoff-nearby-icon">📍</div>
              <h3 className="handoff-phase-title">{gpsCoords ? "Location confirmed" : "Location unavailable"}</h3>
              <p className="handoff-phase-sub">
                {gpsCoords
                  ? `${gpsCoords.lat}, ${gpsCoords.lng} · ±${gpsCoords.acc}m`
                  : "GPS access was denied. The handoff will proceed without location verification."}
              </p>
              <div className="handoff-org-select">
                <label className="offer-label" htmlFor="handoff-org">Receiving organization</label>
                <input
                  id="handoff-org"
                  className="offer-input"
                  type="text"
                  placeholder="e.g., Haven House, Metro Food Bank"
                  value={recipientOrg}
                  onChange={(e) => setRecipientOrg(e.target.value)}
                />
              </div>
              <button className="btn-continue btn-wide handoff-tap-btn" onClick={startTap} disabled={!recipientOrg}>
                📱 Tap to verify handoff <span className="arrow">→</span>
              </button>
              <p className="handoff-help-text">
                Hold your phone near the recipient&apos;s device — NFC tap or QR scan
              </p>
            </div>
          )}

          {/* ── Tapping / Scanning ── */}
          {handoffPhase === "tapping" && (
            <div className="handoff-center">
              <div className="handoff-tap-animation">
                <div className="tap-phone tap-phone-left">📱</div>
                <div className="tap-waves">
                  <div className="tap-wave" />
                  <div className="tap-wave" style={{ animationDelay: "0.3s" }} />
                  <div className="tap-wave" style={{ animationDelay: "0.6s" }} />
                </div>
                <div className="tap-phone tap-phone-right">📱</div>
              </div>
              <h3 className="handoff-phase-title">Connecting…</h3>
              <p className="handoff-phase-sub">Hold phones together</p>
              <button className="btn-small btn-small-outline" style={{ marginTop: 20 }} onClick={cancelHandoff}>Cancel</button>
            </div>
          )}

          {/* ── Confirming ── */}
          {handoffPhase === "confirming" && (
            <div className="handoff-center">
              <div className="handoff-confirm-icon">🤝</div>
              <h3 className="handoff-phase-title">Confirm handoff</h3>
              <p className="handoff-phase-sub">
                {recipientOrg} is ready to receive your {category.name.toLowerCase()} donation
              </p>
              <div className="handoff-confirm-summary">
                {category.fields.filter(f => formData[f.key]).slice(0, 2).map((field) => (
                  <div key={field.key} className="pass-detail-row">
                    <span className="pass-detail-label">{field.label}</span>
                    <span className="pass-detail-value">{field.key === "value" ? `$${formData[field.key]}` : formData[field.key]}</span>
                  </div>
                ))}
              </div>
              <button className="btn-continue btn-wide handoff-confirm-btn" onClick={confirmHandoff}>
                ✓ Confirm — donation received <span className="arrow">→</span>
              </button>
            </div>
          )}

          {/* ── Verified ── */}
          {handoffPhase === "verified" && (
            <div className="handoff-center">
              <div className="handoff-verified-icon">✅</div>
              <h2 className="handoff-verified-title">Donation verified</h2>
              <p className="handoff-verified-sub">
                Your {category.name.toLowerCase()} donation has been received and verified. Tax receipt sent to <strong>{donorEmail}</strong>.
              </p>

              <div className="handoff-proof-card">
                <h3 className="handoff-proof-title">Verification proof</h3>
                <div className="handoff-proof-chain">
                  <div className="proof-step">
                    <span className="proof-step-icon">📋</span>
                    <div className="proof-step-info">
                      <strong>Donation created</strong>
                      <span>{donationId}</span>
                    </div>
                    <span className="proof-step-check">✓</span>
                  </div>
                  <div className="proof-step">
                    <span className="proof-step-icon">📍</span>
                    <div className="proof-step-info">
                      <strong>{gpsCoords ? "Location verified" : "Location skipped"}</strong>
                      <span>{gpsCoords ? `${gpsCoords.lat}, ${gpsCoords.lng}` : "GPS unavailable"}</span>
                    </div>
                    <span className="proof-step-check">{gpsCoords ? "✓" : "—"}</span>
                  </div>
                  <div className="proof-step">
                    <span className="proof-step-icon">📱</span>
                    <div className="proof-step-info">
                      <strong>NFC handoff</strong>
                      <span>Device-to-device verified</span>
                    </div>
                    <span className="proof-step-check">✓</span>
                  </div>
                  <div className="proof-step">
                    <span className="proof-step-icon">🤝</span>
                    <div className="proof-step-info">
                      <strong>Received by</strong>
                      <span>{recipientOrg}</span>
                    </div>
                    <span className="proof-step-check">✓</span>
                  </div>
                  <div className="proof-step">
                    <span className="proof-step-icon">⏰</span>
                    <div className="proof-step-info">
                      <strong>Timestamp</strong>
                      <span>{handoffTime}</span>
                    </div>
                    <span className="proof-step-check">✓</span>
                  </div>
                </div>
              </div>

              {estimatedDeduction > 0 && (
                <div className="offer-done-deduction">
                  <span className="offer-done-deduction-label">Verified tax deduction</span>
                  <span className="offer-done-deduction-amount">${estimatedDeduction.toLocaleString()}</span>
                </div>
              )}

              <div className="offer-done-actions">
                <button className="btn-continue" onClick={handleStartOver}>Donate something else</button>
                <button className="btn-small btn-small-outline" onClick={onBack}>Back to profile</button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════ Generic Done (services only) ═══════════════════ */}
      {step === "done" && (
        <div className="offer-step offer-step-visible">
          <div className="offer-done">
            <div className="offer-done-icon">✦</div>
            <h2 className="offer-done-title">Thank you</h2>
            <p className="offer-done-text">
              Your {category?.name.toLowerCase()} donation has been submitted.
              We&apos;ll match it with a community member and send your tax receipt
              to <strong>{donorEmail}</strong>.
            </p>
            {estimatedDeduction > 0 && (
              <div className="offer-done-deduction">
                <span className="offer-done-deduction-label">Estimated tax deduction</span>
                <span className="offer-done-deduction-amount">${estimatedDeduction.toLocaleString()}</span>
              </div>
            )}
            <div className="offer-done-actions">
              <button className="btn-continue" onClick={handleStartOver}>Donate something else</button>
              <button className="btn-small btn-small-outline" onClick={onBack}>Back to profile</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
