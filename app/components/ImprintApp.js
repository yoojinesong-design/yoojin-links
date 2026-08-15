"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
  quizCategories,
  archetypes,
  opportunities,
  catColors,
  evidence,
  offerCategories,
  getPrimaryDimension,
} from "../data/content";
import RadarChart from "./RadarChart";
import OfferFlow from "./OfferFlow";
import ArchetypeCard from "./ArchetypeCard";
import {
  isNative,
  getPlatform,
  getCurrentPosition,
  hapticImpact,
  hapticNotification,
  shareContent,
  hideSplashScreen,
  setStatusBarStyle,
  onBackButton,
} from "../lib/native";
import { hexToRgb } from "../lib/color";

const rewards = [
  { emoji: "🎶", name: "Concert tickets", cost: "500 pts" },
  { emoji: "⚽", name: "Sports games", cost: "400 pts" },
  { emoji: "🎭", name: "Theater & shows", cost: "350 pts" },
  { emoji: "☕", name: "Local café credit", cost: "150 pts" },
];

/*
 * Realistic ad-revenue math (US rewarded video):
 *   eCPM ≈ $20  →  $0.02 per completed view (AD_GROSS_REVENUE)
 *   75% to causes  →  $0.015 net per ad (AD_CAUSE_REVENUE)
 *   25% to imprint  →  $0.005 per ad (keeps the app running)
 *
 * Cause costs (via established nonprofits):
 *   Feeding America: $1 = 10 meals → $0.10/meal → ~7 ads = 1 meal
 *   One Tree Planted: $1 = 1 tree → ~67 ads = 1 tree
 *   Books for Africa: ~$0.50/book → ~34 ads = 1 book
 *   charity: water: ~$0.03/liter (well amortized) → ~2 ads = 1 liter
 */
const AD_GROSS_REVENUE = 0.02;  // $ per ad (total revenue)
const CAUSE_SPLIT = 0.75;       // 75% to causes
const APP_SPLIT = 0.25;         // 25% keeps imprint running
const AD_CAUSE_REVENUE = AD_GROSS_REVENUE * CAUSE_SPLIT; // $0.015 to cause
const AD_APP_REVENUE = AD_GROSS_REVENUE * APP_SPLIT;     // $0.005 to imprint

/* imprint+ monthly membership */
const PREMIUM_PRICE = 4.99; // $/month
const PREMIUM_CAUSE_FUND = 3.00; // $3 of $4.99 goes to causes each month
const PREMIUM_PERKS = [
  { emoji: "💚", name: "Monthly Cause Fund", desc: "$3/mo auto-donated to your chosen causes", hero: true },
  { emoji: "⚡", name: "2× Impact Points", desc: "Double points on every action you take" },
  { emoji: "📊", name: "Impact Reports", desc: "Monthly & yearly summaries of your total impact" },
  { emoji: "🌍", name: "Expanded Causes", desc: "Access all cause categories + nominate new ones" },
  { emoji: "🏅", name: "Supporter Badge", desc: "Visible badge showing you power the platform" },
  { emoji: "🌟", name: "Early Access", desc: "New features & causes before everyone else" },
];

/*
 * Every.org Integration
 * ─────────────────────
 * Every.org is a 501(c)(3) nonprofit (EIN 61-1913297) that processes donations
 * on behalf of 1.5M+ US nonprofits. Because donors technically donate TO Every.org,
 * Every.org issues IRS-compliant tax receipts automatically — no action from us.
 *
 * Flow: User taps "Donate" → opens Every.org checkout (parameterized URL) →
 *       donor completes payment → Every.org sends webhook to our backend →
 *       we update the user's impact dashboard.
 *
 * Tax receipts: Every.org emails them instantly. We show a confirmation in-app
 * with a link to the donor's Every.org receipt history.
 */
const EVERY_ORG = {
  baseUrl: "https://www.every.org",
  receiptUrl: "https://www.every.org/settings/donations",
  ein: "61-1913297",
  status: "501(c)(3)",
  // Webhook token — set via env var in production
  // webhookToken: process.env.NEXT_PUBLIC_EVERYORG_WEBHOOK_TOKEN,
};

/*
 * Nonprofit partners — all are 501(c)(3) organizations registered on Every.org.
 * `slug` is the Every.org URL path (e.g. every.org/feeding-america).
 * EINs are displayed for transparency; official receipts come from Every.org.
 */
const NONPROFIT_PARTNERS = {
  "Feeding America":  { ein: "36-3673599", status: "501(c)(3)", slug: "feeding-america", address: "161 N Clark St, Suite 700, Chicago, IL 60601" },
  "One Tree Planted": { ein: "46-4664562", status: "501(c)(3)", slug: "one-tree-planted", address: "145 Pine Haven Shores Rd, Shelburne, VT 05482" },
  "Books for Africa": { ein: "41-1661249", status: "501(c)(3)", slug: "books-for-africa", address: "717 Washington Ave N, Minneapolis, MN 55401" },
  "charity: water":   { ein: "22-3936753", status: "501(c)(3)", slug: "charity-water", address: "40 Worth St, Suite 330, New York, NY 10013" },
};

const timeDonationCauses = [
  { id: "meals", emoji: "🍱", name: "Feed a child", unit: "meal", adsPerUnit: 7, partner: "Feeding America", color: "var(--cat-connect)" },
  { id: "trees", emoji: "🌳", name: "Plant a tree", unit: "tree", adsPerUnit: 67, partner: "One Tree Planted", color: "var(--cat-build)" },
  { id: "books", emoji: "📚", name: "Books for kids", unit: "book", adsPerUnit: 34, partner: "Books for Africa", color: "var(--cat-guide)" },
  { id: "water", emoji: "💧", name: "Clean water", unit: "liter", adsPerUnit: 2, partner: "charity: water", color: "var(--cat-solve)" },
];

/*
 * Direct donation — 100% of money goes to the cause. Zero fees.
 * Cost-per-unit matches the real nonprofit partner rates.
 */
const directDonationCauses = [
  { id: "meals", emoji: "🍱", name: "Feed a child", unit: "meal", costPerUnit: 0.10, partner: "Feeding America", desc: "$1 = 10 meals", color: "var(--cat-connect)" },
  { id: "trees", emoji: "🌳", name: "Plant a tree", unit: "tree", costPerUnit: 1.00, partner: "One Tree Planted", desc: "$1 = 1 tree", color: "var(--cat-build)" },
  { id: "books", emoji: "📚", name: "Books for kids", unit: "book", costPerUnit: 0.50, partner: "Books for Africa", desc: "$1 = 2 books", color: "var(--cat-guide)" },
  { id: "water", emoji: "💧", name: "Clean water", unit: "liter", costPerUnit: 0.03, partner: "charity: water", desc: "$1 = ~33 liters", color: "var(--cat-solve)" },
];

const donationAmounts = [1, 3, 5, 10, 25, 50];

export default function ImprintApp() {
  /* ── Auth State ── */
  const [user, setUser] = useState(null); // { name, email, avatar, joinedAt }
  const [authView, setAuthView] = useState("login"); // login | signup | forgot
  const [authForm, setAuthForm] = useState({ name: "", email: "", password: "" });
  const [authError, setAuthError] = useState(null);
  const [authLoading, setAuthLoading] = useState(false);

  /* ── State ── */
  const [activeView, setActiveView] = useState("landing");
  const [activeQuizId, setActiveQuizId] = useState(null);
  const [quizState, setQuizState] = useState({ currentQ: 0, scores: {}, answers: [] });
  const [quizFading, setQuizFading] = useState(false);
  const [isQuizAnswering, setIsQuizAnswering] = useState(false);
  const [quizResults, setQuizResults] = useState({});
  const [reviewQuizId, setReviewQuizId] = useState(null);
  const [editingQ, setEditingQ] = useState(null);
  const [revealPhase, setRevealPhase] = useState("loading");
  const [joinedCards, setJoinedCards] = useState(new Set());
  const [totalPoints, setTotalPoints] = useState(0);
  const [cardsVisible, setCardsVisible] = useState(false);
  const [offers, setOffers] = useState([]);
  const totalDonationValue = useMemo(
    () => offers.reduce((sum, o) => sum + (o.estimatedValue || 0), 0),
    [offers]
  );

  /* ── Location ── */
  const [userLocation, setUserLocation] = useState("your neighborhood");
  const [locationKey, setLocationKey] = useState(0); // forces contentEditable re-mount on programmatic updates
  const updateLocationProgrammatic = useCallback((loc) => { setUserLocation(loc); setLocationKey((k) => k + 1); }, []);
  const [locationStatus, setLocationStatus] = useState("idle"); // idle | requesting | granted | denied
  const [, setLocationCoords] = useState(null);

  /* ── Time Donation (ad watching) ── */
  const [timeDonation, setTimeDonation] = useState({
    selectedCause: null,
    totalAdsWatched: 0,
    isWatching: false,
    adProgress: 0,
    adPhase: "choose", // choose | watching | complete
    impactLog: {}, // { meals: 12, trees: 1, ... }
  });

  /* ── Premium membership ── */
  const [isPremium, setIsPremium] = useState(false);
  const [premiumPhase, setPremiumPhase] = useState("info"); // info | processing | active
  const premiumTimerRef = useRef(null);

  /* ── Direct Donation (real money, 0% fee) ── */
  const [directDonation, setDirectDonation] = useState({
    selectedCause: null,
    selectedAmount: null,
    customAmount: "",
    phase: "choose", // choose | confirm | processing | complete
    history: [], // [{ causeId, amount, date, unitsGenerated, everyOrgChargeId }, ...]
    totalDonated: 0,
  });

  /* ── Receipt detail view ── */
  const [receiptDetail, setReceiptDetail] = useState(null); // donation object or null
  const [receiptFrom, setReceiptFrom] = useState("myimpact"); // where to go back

  /* ── Quiz double-tap guard ── */
  const quizAnsweringRef = useRef(false);

  /* ── Canvas ripple ── */
  const canvasRef = useRef(null);
  const rafRef = useRef(null);
  const ripplesRef = useRef([]);
  const timerRef = useRef(0);

  const addRipple = useCallback(() => {
    const c = canvasRef.current;
    if (!c) return;
    // Use CSS pixel dimensions (not canvas.width/height which are scaled by DPR)
    const cssW = parseFloat(c.style.width) || c.clientWidth || window.innerWidth;
    const cssH = parseFloat(c.style.height) || c.clientHeight || window.innerHeight;
    ripplesRef.current.push({
      x: cssW / 2 + (Math.random() - 0.5) * 80,
      y: cssH / 2 + (Math.random() - 0.5) * 80,
      r: 0,
      maxR: Math.min(cssW, cssH) * (0.35 + Math.random() * 0.25),
      alpha: 0.08 + Math.random() * 0.04,
    });
  }, []);

  useEffect(() => {
    if (activeView !== "landing") {
      // Stop animation when not on landing page
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      return;
    }
    // Respect reduced motion preference — skip ripple animation
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);
    ripplesRef.current = [];
    addRipple();
    addRipple();
    let stopped = false;
    const style = getComputedStyle(document.documentElement);
    let accentColor = style.getPropertyValue("--accent").trim();
    let rgb = hexToRgb(accentColor) || { r: 42, g: 111, b: 94 };
    const themeObserver = new MutationObserver(() => {
      const newColor = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim();
      if (newColor !== accentColor) {
        accentColor = newColor;
        rgb = hexToRgb(accentColor) || { r: 42, g: 111, b: 94 };
      }
    });
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "data-theme", "style"] });
    const mqDark = window.matchMedia("(prefers-color-scheme: dark)");
    const onMqChange = () => {
      const newColor = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim();
      if (newColor !== accentColor) {
        accentColor = newColor;
        rgb = hexToRgb(accentColor) || { r: 42, g: 111, b: 94 };
      }
    };
    mqDark.addEventListener("change", onMqChange);
    const draw = () => {
      if (stopped) return;
      // Clear in CSS pixel coordinates (transform handles DPR scaling)
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
      const ripples = ripplesRef.current;
      for (let i = ripples.length - 1; i >= 0; i--) {
        const rp = ripples[i];
        rp.r += 0.35;
        const life = rp.r / rp.maxR;
        if (life >= 1) { ripples.splice(i, 1); continue; }
        ctx.beginPath();
        ctx.arc(rp.x, rp.y, rp.r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${rgb.r},${rgb.g},${rgb.b},${rp.alpha * (1 - life)})`;
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }
      timerRef.current++;
      if (timerRef.current % 120 === 0) addRipple();
      rafRef.current = requestAnimationFrame(draw);
    };
    rafRef.current = requestAnimationFrame(draw);
    return () => { stopped = true; themeObserver.disconnect(); mqDark.removeEventListener("change", onMqChange); window.removeEventListener("resize", resize); if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [addRipple, activeView]);

  /* ── Location: auto-detect via timezone on mount ── */
  const tzCities = useRef({
    "America/New_York": "New York", "America/Chicago": "Chicago", "America/Denver": "Denver",
    "America/Los_Angeles": "Los Angeles", "America/Phoenix": "Phoenix",
    "America/Detroit": "Detroit", "America/Indiana/Indianapolis": "Indianapolis",
    "America/Boise": "Boise", "America/Kentucky/Louisville": "Louisville",
    "Pacific/Honolulu": "Honolulu", "America/Anchorage": "Anchorage",
    "Europe/London": "London", "Europe/Paris": "Paris", "Europe/Berlin": "Berlin",
    "Europe/Madrid": "Madrid", "Europe/Rome": "Rome", "Europe/Amsterdam": "Amsterdam",
    "Europe/Istanbul": "Istanbul", "Europe/Moscow": "Moscow",
    "Asia/Tokyo": "Tokyo", "Asia/Seoul": "Seoul", "Asia/Shanghai": "Shanghai",
    "Asia/Hong_Kong": "Hong Kong", "Asia/Singapore": "Singapore", "Asia/Taipei": "Taipei",
    "Asia/Bangkok": "Bangkok", "Asia/Kolkata": "Mumbai", "Asia/Dubai": "Dubai",
    "Australia/Sydney": "Sydney", "Australia/Melbourne": "Melbourne",
    "America/Toronto": "Toronto", "America/Vancouver": "Vancouver",
    "America/Mexico_City": "Mexico City", "America/Sao_Paulo": "São Paulo",
    "America/Argentina/Buenos_Aires": "Buenos Aires",
    "Africa/Lagos": "Lagos", "Africa/Johannesburg": "Johannesburg", "Africa/Cairo": "Cairo",
  });

  const guessCityFromTimezone = useCallback(() => {
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (tzCities.current[tz]) return tzCities.current[tz];
      const parts = tz.split("/");
      const last = parts[parts.length - 1].replace(/_/g, " ");
      if (last && last.length > 2) return last;
    } catch (e) { /* ignore */ }
    return null;
  }, []);

  useEffect(() => {
    const city = guessCityFromTimezone();
    if (city) setUserLocation(city);
  }, [guessCityFromTimezone]);

  /* ── Cleanup animation timers on unmount ── */
  useEffect(() => {
    return () => {
      quizTimersRef.current.forEach(clearTimeout);
      if (switchViewTimerRef.current) clearTimeout(switchViewTimerRef.current);
      if (feedTimerRef.current) clearTimeout(feedTimerRef.current);
      if (donationTimerRef.current) clearTimeout(donationTimerRef.current);
      if (shareStatusTimerRef.current) clearTimeout(shareStatusTimerRef.current);
      if (socialAuthTimerRef.current) clearTimeout(socialAuthTimerRef.current);
      if (premiumTimerRef.current) clearTimeout(premiumTimerRef.current);
      if (authTimerRef.current) clearTimeout(authTimerRef.current);
      if (adTimerRef.current) clearInterval(adTimerRef.current);
    };
  }, []);

  /* ── Native app init ── */
  const backButtonHandleRef = useRef(null);
  useEffect(() => {
    // Hide splash screen once the app loads
    hideSplashScreen().catch(() => {});
    setStatusBarStyle("Dark").catch(() => {});

    // Handle Android back button (uses refs to avoid stale closure)
    onBackButton(() => {
      if (displayViewRef.current !== "landing" && displayViewRef.current !== "dashboard") {
        switchView(userRef.current ? "dashboard" : "landing");
      }
    }).then((handle) => { backButtonHandleRef.current = handle; }).catch(() => {});

    // Register service worker for PWA
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }

    // Browser back button navigates views instead of leaving the app
    const handlePopstate = (e) => {
      const target = e.state?.view;
      if (target) {
        switchView(target, { fromPopstate: true });
      } else {
        // No state — go to dashboard or landing
        const fallback = userRef.current ? "dashboard" : "landing";
        if (displayViewRef.current !== fallback) {
          switchView(fallback, { fromPopstate: true });
        }
      }
    };
    window.addEventListener("popstate", handlePopstate);

    return () => {
      window.removeEventListener("popstate", handlePopstate);
      if (backButtonHandleRef.current) {
        backButtonHandleRef.current.remove();
        backButtonHandleRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const requestUserLocation = useCallback(async () => {
    setLocationStatus("requesting");
    try {
      // Use native bridge (Capacitor on mobile, Web API on browser)
      const coords = await getCurrentPosition();
      setLocationCoords({ lat: coords.latitude, lon: coords.longitude });
      setLocationStatus("granted");
      hapticNotification("Success").catch(() => {});
      // Try reverse geocoding via free API (with timeout)
      try {
        const geoAbort = new AbortController();
        const geoTimeout = setTimeout(() => geoAbort.abort(), 8000);
        const res = await fetch(
          `https://nominatim.openstreetmap.org/reverse?lat=${coords.latitude}&lon=${coords.longitude}&format=json&zoom=12`,
          { headers: { "Accept-Language": "en" }, signal: geoAbort.signal }
        );
        clearTimeout(geoTimeout);
        if (res.ok) {
          const data = await res.json();
          const addr = data.address || {};
          const name = addr.city || addr.town || addr.village || addr.suburb || addr.county || "";
          const state = addr.state || "";
          if (name) {
            updateLocationProgrammatic(state ? `${name}, ${state}` : name);
            return;
          }
        }
      } catch { /* fallback below */ }
      // Fallback to timezone
      const city = guessCityFromTimezone();
      if (city) updateLocationProgrammatic(city);
    } catch {
      setLocationStatus("denied");
      const city = guessCityFromTimezone();
      if (city) updateLocationProgrammatic(city);
    }
  }, [guessCityFromTimezone, updateLocationProgrammatic]);

  /* ── View transition ── */
  /* Refs for back button closure (avoid stale capture) */
  const displayViewRef = useRef("landing");
  const userRef = useRef(user);
  useEffect(() => { userRef.current = user; }, [user]);

  const [headerView, setHeaderView] = useState("landing");
  const switchViewTimerRef = useRef(null);
  const switchView = useCallback((nextView, { fromPopstate = false } = {}) => {
    hapticImpact("Light").catch(() => {});
    if (switchViewTimerRef.current) clearTimeout(switchViewTimerRef.current);
    // Push browser history entry so the back button navigates views
    if (!fromPopstate) {
      try { history.pushState({ view: nextView }, "", ""); } catch { /* ignore */ }
    }
    setHeaderView(nextView);
    setActiveView(null);
    switchViewTimerRef.current = setTimeout(() => {
      switchViewTimerRef.current = null;
      displayViewRef.current = nextView;
      setActiveView(nextView);
      // Reset scroll and move focus on the incoming view only (preserve scroll on other views)
      requestAnimationFrame(() => {
        const newSection = document.querySelector('.view.active');
        if (!newSection) return;
        newSection.scrollTop = 0;
        const target = newSection.querySelector('h1, h2, [autofocus], button.btn-back');
        if (target) {
          const nativelyFocusable = target.matches('a, button, input, select, textarea, [tabindex]');
          if (!nativelyFocusable) target.setAttribute('tabindex', '-1');
          target.focus({ preventScroll: true });
          if (!nativelyFocusable) {
            target.addEventListener('blur', () => target.removeAttribute('tabindex'), { once: true });
          }
        }
      });
    }, 300);
  }, []);

  /* ── Quiz actions ── */
  const startQuiz = (quizId) => {
    // Clear any lingering quiz timers from previous runs
    quizTimersRef.current.forEach(clearTimeout);
    quizTimersRef.current = [];
    quizAnsweringRef.current = false; // reset guard in case restart happened mid-animation
    setIsQuizAnswering(false);
    setActiveQuizId(quizId);
    const cat = quizCategories.find((c) => c.id === quizId);
    const initScores = {};
    cat.dimensions.forEach((d) => (initScores[d.key] = 0));
    setQuizState({ currentQ: 0, scores: initScores, answers: [] });
    setQuizFading(false);
    switchView("quiz");
  };

  const quizTimersRef = useRef([]);
  const handleAnswer = (option) => {
    if (quizAnsweringRef.current) return;
    quizAnsweringRef.current = true;
    setIsQuizAnswering(true);

    const cat = quizCategories.find((c) => c.id === activeQuizId);
    const newScores = { ...quizState.scores };
    newScores[option.type] = (newScores[option.type] || 0) + 1;
    const newAnswers = [...quizState.answers, { type: option.type, text: option.text }];

    const t1 = setTimeout(() => {
      if (quizState.currentQ >= cat.questions.length - 1) {
        setQuizResults((prev) => ({
          ...prev,
          [activeQuizId]: { scores: newScores, answers: newAnswers },
        }));

        if (activeQuizId === "purpose") {
          setRevealPhase("loading");
          switchView("reveal");
          const t2 = setTimeout(() => setRevealPhase("content"), 2200);
          quizTimersRef.current.push(t2);
        } else {
          switchView("dashboard");
        }
        quizAnsweringRef.current = false;
        setIsQuizAnswering(false);
      } else {
        setQuizFading(true);
        const t3 = setTimeout(() => {
          setQuizState(prev => ({ ...prev, currentQ: prev.currentQ + 1, scores: newScores, answers: newAnswers }));
          setQuizFading(false);
          quizAnsweringRef.current = false;
          setIsQuizAnswering(false);
        }, 400);
        quizTimersRef.current.push(t3);
      }
    }, 450);
    quizTimersRef.current.push(t1);
  };

  /* ── Answer review ── */
  const openReview = (quizId) => {
    setReviewQuizId(quizId);
    setEditingQ(null);
    switchView("review");
  };

  const updateAnswer = (questionIndex, newOption) => {
    setQuizResults((prev) => {
      const result = { ...prev[reviewQuizId] };
      const newAnswers = [...result.answers];
      newAnswers[questionIndex] = { type: newOption.type, text: newOption.text };
      const cat = quizCategories.find((c) => c.id === reviewQuizId);
      const newScores = {};
      cat.dimensions.forEach((d) => (newScores[d.key] = 0));
      newAnswers.forEach((a) => { newScores[a.type] = (newScores[a.type] || 0) + 1; });
      return { ...prev, [reviewQuizId]: { scores: newScores, answers: newAnswers } };
    });
    setEditingQ(null);
  };

  /* ── Offer flow ── */
  const [offerFlowKey, setOfferFlowKey] = useState(0);
  const openOffer = () => { setOfferFlowKey((k) => k + 1); switchView("offer"); };

  const handleOfferSubmit = (offer) => {
    setOffers((prev) => [...prev, { ...offer, id: `offer-${Date.now().toString(36)}` }]);
    // totalDonationValue is now derived from offers via useMemo — no setter needed
  };

  /* ── Time Donation actions ── */
  const openTimeDonate = () => {
    setTimeDonation((prev) => ({ ...prev, adPhase: "choose", selectedCause: null }));
    switchView("timedonate");
  };

  const selectCause = (causeId) => {
    setTimeDonation((prev) => ({ ...prev, selectedCause: causeId }));
  };

  const selectedCauseRef = useRef(timeDonation.selectedCause);
  useEffect(() => { selectedCauseRef.current = timeDonation.selectedCause; }, [timeDonation.selectedCause]);

  const startWatchingAd = () => {
    if (!timeDonation.selectedCause) return; // guard: must select a cause first
    setTimeDonation((prev) => ({ ...prev, isWatching: true, adProgress: 0, adPhase: "watching" }));
  };

  const adTimerRef = useRef(null);
  const isPremiumRef = useRef(isPremium);
  useEffect(() => { isPremiumRef.current = isPremium; }, [isPremium]);

  useEffect(() => {
    if (!timeDonation.isWatching) return;
    const duration = 60; // 60 seconds
    let elapsed = 0;
    // Capture cause at start — changing cause mid-ad won't restart the interval
    const causeId = selectedCauseRef.current;
    const cause = timeDonationCauses.find((c) => c.id === causeId);
    if (!cause) return;
    adTimerRef.current = setInterval(() => {
      elapsed += 0.1;
      const progress = Math.min((elapsed / duration) * 100, 100);
      setTimeDonation((prev) => ({ ...prev, adProgress: progress }));
      if (elapsed >= duration) {
        clearInterval(adTimerRef.current);
        setTimeDonation((prev) => {
          const newLog = { ...prev.impactLog };
          // Use integer counting to avoid floating-point accumulation error
          // (e.g. 7 × 1/7 = 0.999999 instead of 1.0, causing Math.floor to under-count)
          const rawTotal = (newLog[cause.id] || 0) + (1 / cause.adsPerUnit);
          newLog[cause.id] = (rawTotal % 1) > 0.9999 ? Math.ceil(rawTotal) : Math.round(rawTotal * 1e6) / 1e6;
          return {
            ...prev,
            isWatching: false,
            adProgress: 100,
            adPhase: "complete",
            totalAdsWatched: prev.totalAdsWatched + 1,
            impactLog: newLog,
          };
        });
        setTotalPoints((prev) => prev + (isPremiumRef.current ? 20 : 10));
      }
    }, 100);
    return () => clearInterval(adTimerRef.current);
  }, [timeDonation.isWatching]); // removed selectedCause dep — captured in ref to prevent mid-ad restart

  const watchAnother = () => {
    setTimeDonation((prev) => ({
      ...prev,
      adPhase: "choose",
      adProgress: 0,
    }));
  };

  /* ── Direct Donation actions ── */
  const openDirectDonate = () => {
    // Cancel any in-flight donation processing timer from a previous session
    if (donationTimerRef.current) { clearTimeout(donationTimerRef.current); donationTimerRef.current = null; }
    donationSubmittedRef.current = false;
    setDirectDonation((prev) => ({ ...prev, phase: "choose", selectedAmount: null, customAmount: "" }));
    switchView("directdonate");
  };

  const selectDirectCause = (causeId) => {
    hapticImpact("Light").catch(() => {});
    setDirectDonation((prev) => ({ ...prev, selectedCause: causeId }));
  };

  const selectDirectAmount = (amount) => {
    hapticImpact("Light").catch(() => {});
    setDirectDonation((prev) => ({ ...prev, selectedAmount: amount, customAmount: "" }));
  };

  const getDirectDonationAmount = () => {
    if (directDonation.selectedAmount) return directDonation.selectedAmount;
    const parsed = parseFloat(directDonation.customAmount);
    if (isNaN(parsed) || parsed < 1) return 0; // minimum $1 donation
    return Math.min(Math.round(parsed * 100) / 100, 25000); // round to cents, cap at $25k
  };

  /* Build Every.org donation URL for a cause */
  const buildEveryOrgUrl = (cause, amount) => {
    const np = NONPROFIT_PARTNERS[cause.partner];
    if (!np?.slug) return null;
    const params = new URLSearchParams({
      amount: amount.toString(),
      frequency: "ONCE",
      success_url: `${window.location.origin}?${new URLSearchParams({ donation: "success", cause: cause.id, amount: amount.toString() })}`,
      exit_url: `${window.location.origin}?${new URLSearchParams({ donation: "cancelled" })}`,
      // webhook_token: EVERY_ORG.webhookToken || "",
      // partner_donation_id: `imp-${Date.now()}`,
    });
    return `${EVERY_ORG.baseUrl}/${np.slug}?${params.toString()}#donate`;
  };

  const donationTimerRef = useRef(null);
  const donationSubmittedRef = useRef(false);
  const confirmDirectDonation = () => {
    if (donationSubmittedRef.current) return;
    const amount = getDirectDonationAmount();
    if (!amount || !directDonation.selectedCause || directDonation.phase === "processing") return;
    donationSubmittedRef.current = true;
    const cause = directDonationCauses.find((c) => c.id === directDonation.selectedCause);
    if (!cause) return;

    /*
     * Production flow:
     *   1. Open Every.org checkout in new tab/webview
     *   2. Every.org handles payment + sends tax receipt to donor
     *   3. Our webhook endpoint receives confirmation
     *   4. We update the user's impact dashboard
     *
     * For the prototype, we simulate the webhook callback after a delay,
     * as if the user completed payment on Every.org and returned.
     * In production, replace this with real Every.org redirect + webhook handler.
     */
    const everyOrgUrl = buildEveryOrgUrl(cause, amount);
    if (everyOrgUrl) {
      // In production: window.open(everyOrgUrl, "_blank");
    }

    setDirectDonation((prev) => ({ ...prev, phase: "processing" }));

    // Simulate Every.org webhook callback (replace with real webhook in production)
    if (donationTimerRef.current) clearTimeout(donationTimerRef.current);
    donationTimerRef.current = setTimeout(() => {
      donationTimerRef.current = null;
      const unitsGenerated = Math.round(amount / cause.costPerUnit);
      const ptsPerDollar = isPremiumRef.current ? 100 : 50;
      const pointsEarned = Math.floor(amount * ptsPerDollar);
      hapticNotification("Success").catch(() => {});
      setDirectDonation((prev) => ({
        ...prev,
        phase: "complete",
        totalDonated: prev.totalDonated + amount,
        history: [
          ...prev.history,
          {
            causeId: cause.id,
            amount,
            unitsGenerated,
            pointsEarned, // store actual points at time of donation (avoids retroactive recalculation)
            wasPremium: isPremiumRef.current,
            date: new Date().toISOString(),
            everyOrgChargeId: `eo-${Date.now().toString(36)}`, // from webhook in production
          },
        ],
      }));
      setTotalPoints((p) => p + pointsEarned);
      donationSubmittedRef.current = false;
    }, 1800);
  };

  const donationByCause = useMemo(() => {
    const map = {};
    directDonation.history.forEach((d) => { map[d.causeId] = (map[d.causeId] || 0) + d.amount; });
    return map;
  }, [directDonation.history]);
  const directDonationForCause = (causeId) => donationByCause[causeId] || 0;

  /* ── Impact card (shareable) ── */
  const impactCardRef = useRef(null);
  const [shareStatus, setShareStatus] = useState(null); // null | "copied" | "error"
  const shareStatusTimerRef = useRef(null);
  const clearShareStatusLater = () => {
    if (shareStatusTimerRef.current) clearTimeout(shareStatusTimerRef.current);
    shareStatusTimerRef.current = setTimeout(() => { shareStatusTimerRef.current = null; setShareStatus(null); }, 2500);
  };
  useEffect(() => () => { if (shareStatusTimerRef.current) clearTimeout(shareStatusTimerRef.current); }, []);

  const openMyImpact = () => switchView("myimpact");

  const openReceiptDetail = (donation, from = "myimpact") => {
    setReceiptDetail(donation);
    setReceiptFrom(from);
    switchView("receipt");
  };

  const impactStats = useMemo(() => {
    const dollarsRaised = timeDonation.totalAdsWatched * AD_CAUSE_REVENUE;
    const grossRevenue = timeDonation.totalAdsWatched * AD_GROSS_REVENUE;
    const appRevenue = timeDonation.totalAdsWatched * AD_APP_REVENUE;
    const minutesDonated = timeDonation.totalAdsWatched;
    const impactItems = timeDonationCauses
      .filter((c) => timeDonation.impactLog[c.id] > 0)
      .map((c) => ({
        ...c,
        total: timeDonation.impactLog[c.id],
        completed: Math.floor(timeDonation.impactLog[c.id]),
      }));
    const activitiesJoined = joinedCards.size;
    const offersCount = offers.length;
    const quizzesCompleted = Object.keys(quizResults).length;
    const directDollars = directDonation.totalDonated;
    const directCount = directDonation.history.length;
    return { dollarsRaised, grossRevenue, appRevenue, minutesDonated, impactItems, activitiesJoined, offersCount, quizzesCompleted, directDollars, directCount };
  }, [timeDonation.totalAdsWatched, timeDonation.impactLog, joinedCards, offers, quizResults, directDonation.totalDonated, directDonation.history.length]);

  // Milestones (memoized)
  const milestones = useMemo(() => {
    const stats = impactStats;
    return [
      { id: "first-quiz", emoji: "🧭", name: "Found My Purpose", desc: "Completed first quiz", unlocked: stats.quizzesCompleted >= 1 },
      { id: "all-quizzes", emoji: "🎓", name: "Self-Aware", desc: "Completed all 4 quizzes", unlocked: stats.quizzesCompleted >= 4 },
      { id: "first-ad", emoji: "👁", name: "First Minute Given", desc: "Watched first clip", unlocked: stats.minutesDonated >= 1 },
      { id: "ten-ads", emoji: "⏱", name: "Timekeeper", desc: "Donated 10 minutes", unlocked: stats.minutesDonated >= 10 },
      { id: "fifty-ads", emoji: "🔥", name: "On Fire", desc: "Donated 50 minutes", unlocked: stats.minutesDonated >= 50 },
      { id: "first-meal", emoji: "🍱", name: "First Meal", desc: "Funded a meal", unlocked: (timeDonation.impactLog.meals || 0) >= 1 },
      { id: "first-offer", emoji: "🤝", name: "Generous Spirit", desc: "Made first donation offer", unlocked: stats.offersCount >= 1 },
      { id: "first-join", emoji: "🙋", name: "Showed Up", desc: "Joined first activity", unlocked: stats.activitiesJoined >= 1 },
      { id: "dollar", emoji: "💚", name: "$1 Raised", desc: "Raised $1 through time", unlocked: stats.dollarsRaised >= 1 },
      { id: "five-dollar", emoji: "🌟", name: "$5 Raised", desc: "Raised $5 through time", unlocked: stats.dollarsRaised >= 5 },
      { id: "first-direct", emoji: "💸", name: "Direct Giver", desc: "Made first direct donation", unlocked: stats.directCount >= 1 },
      { id: "ten-direct", emoji: "💎", name: "Champion Donor", desc: "Donated $10+ directly", unlocked: stats.directDollars >= 10 },
      { id: "fifty-direct", emoji: "🏆", name: "Changemaker", desc: "Donated $50+ directly", unlocked: stats.directDollars >= 50 },
      { id: "premium", emoji: "⚡", name: "Supporter", desc: "Became an imprint+ member", unlocked: isPremium, premium: true },
      { id: "hundred-pts", emoji: "💜", name: "Point Collector", desc: "Earned 100+ points", unlocked: totalPoints >= 100 },
    ];
  }, [impactStats, timeDonation.impactLog, isPremium, totalPoints]);

  const shareImpact = async () => {
    const stats = impactStats;
    const lines = ["My Imprint 🌿"];
    if (arch) lines.push(`Purpose: ${arch.name}`);
    if (stats.minutesDonated > 0) lines.push(`⏱ ${stats.minutesDonated} min donated · $${stats.dollarsRaised.toFixed(2)} raised`);
    if (stats.directDollars > 0) lines.push(`💸 $${stats.directDollars.toFixed(2)} donated directly (100% to causes)`);
    stats.impactItems.forEach((item) => {
      if (item.completed > 0) lines.push(`${item.emoji} ${item.completed} ${item.unit}${item.completed !== 1 ? "s" : ""} funded`);
    });
    if (stats.activitiesJoined > 0) lines.push(`🙋 ${stats.activitiesJoined} activities joined`);
    if (stats.offersCount > 0) lines.push(`🤝 ${stats.offersCount} donation${stats.offersCount > 1 ? "s" : ""} offered`);
    const unlockedCount = milestones.filter((m) => m.unlocked).length;
    if (unlockedCount > 0) lines.push(`🏅 ${unlockedCount} milestone${unlockedCount > 1 ? "s" : ""} unlocked`);
    lines.push("", "imprint — find your purpose, fund the change");
    const text = lines.join("\n");

    try {
      const result = await shareContent({ title: "My Imprint", text });
      if (result === "clipboard") {
        setShareStatus("copied");
        clearShareStatusLater();
      } else if (result) {
        setShareStatus("copied");
        hapticNotification("Success").catch(() => {});
      }
    } catch {
      setShareStatus("error");
      clearShareStatusLater();
    }
  };

  /* ── Tax Receipt — via Every.org ── */
  /*
   * Every.org (EIN 61-1913297) is a 501(c)(3) that processes all donations.
   * They email an IRS-compliant tax receipt to the donor automatically.
   * What we generate here is an in-app SUMMARY for the user's reference —
   * the legally valid receipt comes from Every.org's email.
   */
  const generateDonationSummary = (donation) => {
    const cause = directDonationCauses.find((c) => c.id === donation.causeId);
    if (!cause) return null;
    const np = NONPROFIT_PARTNERS[cause.partner] || {};
    const summaryId = `IMP-${(donation.everyOrgChargeId || Date.now().toString(36)).replace(/^eo-/, "").toUpperCase()}`;
    return {
      summaryId,
      date: donation.date,
      donor: user?.name || "Anonymous",
      donorEmail: user?.email || "",
      amount: donation.amount,
      organization: cause?.partner,
      organizationEin: np.ein,
      organizationStatus: np.status,
      processedBy: "Every.org",
      processedByEin: EVERY_ORG.ein,
      description: `Charitable donation for ${cause?.name?.toLowerCase()} (${donation.unitsGenerated} ${cause?.unit}${donation.unitsGenerated !== 1 ? "s" : ""})`,
    };
  };

  const formatSummaryText = (summary) => {
    return [
      `DONATION SUMMARY`,
      `Reference #: ${summary.summaryId}`,
      `Date: ${new Date(summary.date).toLocaleDateString()}`,
      ``,
      `DONOR`,
      `Name: ${summary.donor}`,
      summary.donorEmail ? `Email: ${summary.donorEmail}` : null,
      ``,
      `RECIPIENT ORGANIZATION`,
      `${summary.organization}`,
      `EIN: ${summary.organizationEin}`,
      `Status: ${summary.organizationStatus}`,
      ``,
      `PROCESSED BY`,
      `Every.org (501(c)(3) fiscal intermediary)`,
      `EIN: ${summary.processedByEin}`,
      ``,
      `DONATION DETAILS`,
      `Amount: $${summary.amount.toFixed(2)}`,
      `Description: ${summary.description}`,
      `Platform fee: $0.00 (0%)`,
      ``,
      `TAX RECEIPT`,
      `Your official IRS tax receipt was emailed by Every.org.`,
      `View all receipts: ${EVERY_ORG.receiptUrl}`,
      `No goods or services were provided in exchange for this donation.`,
      `This contribution is tax-deductible under IRC Section 170.`,
      ``,
      `---`,
      `Generated by imprint · Donations processed by Every.org`,
    ].filter(Boolean).join("\n");
  };

  const downloadReceipt = async (donation) => {
    const summary = generateDonationSummary(donation);
    if (!summary) return;
    const text = formatSummaryText(summary);
    try {
      const result = await shareContent({ title: `Donation Summary ${summary.summaryId}`, text });
      if (result === "clipboard") {
        setShareStatus("copied");
        clearShareStatusLater();
      }
    } catch {
      const blob = new Blob([text], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `imprint-donation-${summary.summaryId}.txt`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  };

  const openEveryOrgReceipts = () => {
    window.open(EVERY_ORG.receiptUrl, "_blank", "noopener,noreferrer");
  };

  const generateAnnualSummary = () => {
    const year = new Date().getFullYear();
    const donations = directDonation.history.filter((d) => {
      try { return new Date(d.date).getFullYear() === year; } catch { return false; }
    });
    if (donations.length === 0) return null;

    const byPartner = {};
    donations.forEach((d) => {
      const cause = directDonationCauses.find((c) => c.id === d.causeId);
      const partner = cause?.partner || "Unknown";
      if (!byPartner[partner]) byPartner[partner] = { total: 0, count: 0, ein: NONPROFIT_PARTNERS[partner]?.ein || "" };
      byPartner[partner].total += d.amount;
      byPartner[partner].count += 1;
    });

    const totalDonated = donations.reduce((s, d) => s + d.amount, 0);

    const lines = [
      `ANNUAL GIVING SUMMARY — ${year}`,
      `Generated by imprint`,
      `Donations processed by Every.org (EIN ${EVERY_ORG.ein})`,
      ``,
      `DONOR: ${user?.name || "Anonymous"}`,
      user?.email ? `EMAIL: ${user.email}` : null,
      ``,
      `SUMMARY`,
      `Total charitable donations: $${totalDonated.toFixed(2)}`,
      `Number of donations: ${donations.length}`,
      `Platform fees: $0.00`,
      ``,
      `BREAKDOWN BY ORGANIZATION`,
      `${"—".repeat(50)}`,
    ].filter(Boolean);

    Object.entries(byPartner).forEach(([partner, data]) => {
      const np = NONPROFIT_PARTNERS[partner] || {};
      lines.push(`${partner}`);
      lines.push(`  EIN: ${data.ein}`);
      lines.push(`  Status: ${np.status || "501(c)(3)"}`);
      lines.push(`  Total donated: $${data.total.toFixed(2)}`);
      lines.push(`  Number of donations: ${data.count}`);
      lines.push(``);
    });

    lines.push(`${"—".repeat(50)}`);
    lines.push(`TOTAL CHARITABLE GIVING: $${totalDonated.toFixed(2)}`);
    lines.push(``);
    lines.push(`TAX RECEIPTS`);
    lines.push(`Official IRS tax receipts for each donation were emailed by Every.org.`);
    lines.push(`View all receipts: ${EVERY_ORG.receiptUrl}`);
    lines.push(``);
    lines.push(`Every.org is a 501(c)(3) nonprofit (EIN ${EVERY_ORG.ein}).`);
    lines.push(`All contributions are tax-deductible under IRC Section 170.`);
    lines.push(``);
    lines.push(`---`);
    lines.push(`Generated by imprint · Donations processed by Every.org`);

    return lines.join("\n");
  };

  const downloadAnnualSummary = async () => {
    const statement = generateAnnualSummary();
    if (!statement) return;
    try {
      const result = await shareContent({ title: `Annual Giving Summary ${new Date().getFullYear()}`, text: statement });
      if (result === "clipboard") {
        setShareStatus("copied");
        clearShareStatusLater();
      }
    } catch {
      const blob = new Blob([statement], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `imprint-annual-summary-${new Date().getFullYear()}.txt`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  };

  /* ── Auth actions ── */
  const isValidEmail = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const authTimerRef = useRef(null);
  const handleAuth = (e) => {
    e.preventDefault();
    setAuthError(null);

    // Validate before starting the loading state
    if (authView === "login") {
      if (!authForm.email || !authForm.password) {
        setAuthError("Please fill in all fields");
        return;
      }
      if (!isValidEmail(authForm.email)) {
        setAuthError("Please enter a valid email address");
        return;
      }
    } else if (authView === "signup") {
      if (!authForm.name || !authForm.email || !authForm.password) {
        setAuthError("Please fill in all fields");
        return;
      }
      if (!isValidEmail(authForm.email)) {
        setAuthError("Please enter a valid email address");
        return;
      }
    } else if (authView === "forgot") {
      if (!authForm.email || !isValidEmail(authForm.email)) {
        setAuthError("Please enter a valid email address");
        return;
      }
      setAuthLoading(true);
      if (authTimerRef.current) clearTimeout(authTimerRef.current);
      authTimerRef.current = setTimeout(() => {
        authTimerRef.current = null;
        if (displayViewRef.current !== "auth") { setAuthLoading(false); return; }
        setAuthLoading(false);
        setAuthError(null);
        setAuthForm({ email: "", password: "", name: "" });
        setAuthView("login");
      }, 800);
      return;
    }

    setAuthLoading(true);
    // Simulate auth — replace with real auth (Firebase/Supabase/NextAuth)
    if (authTimerRef.current) clearTimeout(authTimerRef.current);
    authTimerRef.current = setTimeout(() => {
      authTimerRef.current = null;
      // Guard: abort if user left the auth view (e.g. tapped "Continue without account")
      if (displayViewRef.current !== "auth") { setAuthLoading(false); return; }
      if (authView === "login") {
        setUser({
          name: authForm.email.split("@")[0],
          email: authForm.email,
          avatar: null,
          joinedAt: new Date().toISOString(),
        });
      } else if (authView === "signup") {
        setUser({
          name: authForm.name,
          email: authForm.email,
          avatar: null,
          joinedAt: new Date().toISOString(),
        });
      }
      setAuthLoading(false);
      setAuthForm({ name: "", email: "", password: "" });
      switchView("dashboard");
    }, 800);
  };

  const socialAuthTimerRef = useRef(null);
  const handleSocialAuth = (provider) => {
    if (authLoading) return;
    setAuthLoading(true);
    // Simulate social auth
    if (socialAuthTimerRef.current) clearTimeout(socialAuthTimerRef.current);
    socialAuthTimerRef.current = setTimeout(() => {
      socialAuthTimerRef.current = null;
      // Guard: abort if user left the auth view
      if (displayViewRef.current !== "auth") { setAuthLoading(false); return; }
      try {
        setUser({
          name: "User",
          email: `user@${provider}.com`,
          avatar: null,
          joinedAt: new Date().toISOString(),
        });
        switchView("dashboard");
      } catch { /* auth failed silently */ }
      setAuthLoading(false);
    }, 600);
  };

  const handleLogout = () => {
    // Clear ALL active timers FIRST to prevent stale callbacks from re-populating reset state
    if (adTimerRef.current) { clearInterval(adTimerRef.current); adTimerRef.current = null; }
    if (donationTimerRef.current) { clearTimeout(donationTimerRef.current); donationTimerRef.current = null; }
    donationSubmittedRef.current = false;
    if (premiumTimerRef.current) { clearTimeout(premiumTimerRef.current); premiumTimerRef.current = null; }
    if (authTimerRef.current) { clearTimeout(authTimerRef.current); authTimerRef.current = null; }
    if (socialAuthTimerRef.current) { clearTimeout(socialAuthTimerRef.current); socialAuthTimerRef.current = null; }
    quizTimersRef.current.forEach(clearTimeout); quizTimersRef.current = [];
    setUser(null);
    setAuthForm({ name: "", email: "", password: "" });
    setAuthView("login");
    // Reset all user-specific state so a new login starts fresh
    setActiveQuizId(null);
    setQuizState({ currentQ: 0, scores: {}, answers: [] });
    setReviewQuizId(null);
    setEditingQ(null);
    setRevealPhase("loading");
    setIsQuizAnswering(false);
    setQuizResults({});
    setTotalPoints(0);
    setTimeDonation({ selectedCause: null, isWatching: false, adProgress: 0, adPhase: "choose", totalAdsWatched: 0, impactLog: {} });
    setDirectDonation({ selectedCause: null, selectedAmount: null, customAmount: "", phase: "choose", history: [], totalDonated: 0 });
    setJoinedCards(new Set());
    setOffers([]);
    setIsPremium(false);
    setPremiumPhase("info");
    setSettings({ notifications: true, weeklyDigest: true, publicProfile: false, darkMode: null });
    setUserLocation("your neighborhood");
    setLocationStatus("idle");
    setReceiptDetail(null);
    try { localStorage.removeItem('imprint_state'); } catch (e) { /* ignore */ }
    // Remove dark mode override
    document.documentElement.removeAttribute('data-theme');
    switchView("landing");
  };

  const [settings, setSettings] = useState({
    notifications: true,
    weeklyDigest: true,
    publicProfile: false,
    darkMode: null, // null = follow system, true = dark, false = light
  });

  // Track system dark mode preference reactively (avoids SSR hydration mismatch)
  const [systemDark, setSystemDark] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    setSystemDark(mq.matches);
    const handler = (e) => setSystemDark(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  /* ── localStorage persistence ── */
  // Load saved state on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem('imprint_state');
      if (saved) {
        const data = JSON.parse(saved);
        if (data.user) setUser(data.user);
        if (data.quizResults) setQuizResults(data.quizResults);
        if (typeof data.totalPoints === 'number' && isFinite(data.totalPoints)) setTotalPoints(data.totalPoints);
        if (data.timeDonation) setTimeDonation(prev => ({
          ...prev, ...data.timeDonation,
          totalAdsWatched: typeof data.timeDonation.totalAdsWatched === 'number' && isFinite(data.timeDonation.totalAdsWatched) ? data.timeDonation.totalAdsWatched : 0,
          isWatching: false, adProgress: 0, adPhase: "choose", // reset transient ad state
        }));
        if (data.directDonation) setDirectDonation(prev => ({
          ...prev, ...data.directDonation,
          phase: data.directDonation.phase === "processing" ? "choose" : (data.directDonation.phase || "choose"), // unstick processing
        }));
        if (data.joinedCards) setJoinedCards(new Set(data.joinedCards));
        if (Array.isArray(data.offers)) setOffers(data.offers.filter(o => typeof o.estimatedValue === 'number' && isFinite(o.estimatedValue)));
        if (data.isPremium === true) setIsPremium(true);
        if (data.userLocation) setUserLocation(data.userLocation);
        if (data.settings) setSettings(prev => ({ ...prev, ...data.settings }));
        // Restore dark mode setting to DOM (null = system default)
        if (data.settings?.darkMode === true) {
          document.documentElement.setAttribute('data-theme', 'dark');
        } else if (data.settings?.darkMode === false) {
          document.documentElement.setAttribute('data-theme', 'light');
        }
        // If user was logged in, go to dashboard (or PWA shortcut target)
        if (data.user) {
          const viewParam = new URLSearchParams(window.location.search).get('view');
          const shortcutMap = { myimpact: 'myimpact', feed: 'feed', account: 'account' };
          const target = shortcutMap[viewParam] || 'dashboard';
          displayViewRef.current = target;
          setHeaderView(target);
          setActiveView(target);
          // If restoring to feed, trigger card reveal animation (tracked via feedTimerRef)
          if (target === 'feed') {
            if (feedTimerRef.current) clearTimeout(feedTimerRef.current);
            feedTimerRef.current = setTimeout(() => { feedTimerRef.current = null; setCardsVisible(true); }, 350);
          }
        }
      }
    } catch (e) {
      if (process.env.NODE_ENV === 'development') console.warn('Failed to load saved state:', e);
    }
  }, []);

  // Save state when key data changes
  // Use stable fields only — exclude transient ad state (adProgress, isWatching, adPhase)
  // to avoid writes during ad playback (100ms interval updates adProgress)
  const timeDonationStable = useMemo(() => ({
    selectedCause: timeDonation.selectedCause,
    totalAdsWatched: timeDonation.totalAdsWatched,
    impactLog: timeDonation.impactLog,
  }), [timeDonation.selectedCause, timeDonation.totalAdsWatched, timeDonation.impactLog]);

  // Exclude transient donation flow fields (phase, selectedAmount, customAmount, selectedCause)
  // to avoid writes on every keystroke / selection during the donation flow
  const directDonationStable = useMemo(() => ({
    history: directDonation.history,
    totalDonated: directDonation.totalDonated,
  }), [directDonation.history, directDonation.totalDonated]);

  useEffect(() => {
    if (!user) return; // Don't save if not logged in
    const stateData = JSON.stringify({
      user,
      quizResults,
      totalPoints,
      timeDonation: timeDonationStable,
      directDonation: directDonationStable,
      joinedCards: [...joinedCards],
      offers,
      isPremium,
      settings,
      userLocation,
    });
    try {
      localStorage.setItem('imprint_state', stateData);
    } catch (e) {
      // QuotaExceeded — clear non-essential storage and retry once
      if (e?.name === 'QuotaExceededError' || e?.code === 22) {
        try {
          const keep = ['imprint_state'];
          for (let i = localStorage.length - 1; i >= 0; i--) {
            const k = localStorage.key(i);
            if (k && !keep.includes(k)) localStorage.removeItem(k);
          }
          localStorage.setItem('imprint_state', stateData);
        } catch (_) { /* give up silently */ }
      }
    }
  }, [user, quizResults, totalPoints, timeDonationStable, directDonationStable, joinedCards, offers, isPremium, settings, userLocation]);

  /* ── Feed ── */
  const feedTimerRef = useRef(null);
  useEffect(() => () => { if (feedTimerRef.current) clearTimeout(feedTimerRef.current); }, []);
  const showFeed = () => {
    setCardsVisible(false);
    switchView("feed");
    if (feedTimerRef.current) clearTimeout(feedTimerRef.current);
    feedTimerRef.current = setTimeout(() => { feedTimerRef.current = null; setCardsVisible(true); }, 350);
  };

  const handleJoin = (cardId) => {
    if (joinedCards.has(cardId)) return;
    setJoinedCards((prev) => new Set([...prev, cardId]));
    setTotalPoints((prev) => prev + (isPremiumRef.current ? 100 : 50));
  };

  /* ── Derived data ── */
  const purposeResult = quizResults.purpose;
  const primaryArchetype = purposeResult ? getPrimaryDimension(purposeResult.scores) : null;
  const arch = primaryArchetype ? archetypes[primaryArchetype] : null;
  const opps = primaryArchetype ? opportunities[primaryArchetype] : [];
  const completedCount = Object.keys(quizResults).length;
  const showHeader = headerView && headerView !== "landing";

  const activeQuiz = quizCategories.find((c) => c.id === activeQuizId);
  const reviewQuiz = quizCategories.find((c) => c.id === reviewQuizId);
  const reviewResult = reviewQuizId ? quizResults[reviewQuizId] : null;

  return (
    <div id="app">
      {/* ── Header ── */}
      <header className={`app-header ${showHeader ? "visible" : ""}`}>
        <span className="logo" role={showHeader ? "button" : undefined} tabIndex={showHeader ? 0 : undefined} aria-label={showHeader ? "Go to dashboard" : undefined} onClick={() => showHeader && switchView("dashboard")} onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && showHeader) { e.preventDefault(); switchView("dashboard"); } }} style={{ cursor: showHeader ? "pointer" : "default" }}>imprint</span>
        <div className="header-right">
          {totalPoints > 0 && (
            <div className="points-display visible">
              <span>✦</span>
              <span>{totalPoints} pts</span>
            </div>
          )}
          {showHeader && (
            <button className="header-settings" onClick={() => switchView("account")} title="Settings" aria-label="Settings">
              ⚙️
            </button>
          )}
          {user && (
            <button className="header-avatar" onClick={() => switchView("account")} title="Account" aria-label="Account">
              {user.avatar ? (
                <img src={user.avatar} alt="" className="header-avatar-img" />
              ) : (
                <span className="header-avatar-initial">{user.name?.charAt(0)?.toUpperCase() || "?"}</span>
              )}
            </button>
          )}
        </div>
      </header>

      <main id="main-content" aria-label="imprint app content">
      {/* ── Landing ── */}
      <section className={`view ${activeView === "landing" ? "active" : ""}`} {...(activeView !== "landing" ? { inert: true } : {})}>
        <canvas ref={canvasRef} className="landing-canvas" />
        <div className="landing-content">
          <h1 className="landing-question">
            Everyone has something to <em>give</em>.
          </h1>
          <p className="landing-sub">
            Not just money. Your time. A meal you cooked. Tickets you can&apos;t use.
            Five minutes of attention. The problem was never caring — it was that
            no one made it easy enough.
          </p>
          <div className="landing-quiz-hook">
            <span className="landing-quiz-time">≈ 1 min</span>
            <span className="landing-quiz-label">5 questions that reveal how you make a difference</span>
          </div>
          <button className="btn-begin" onClick={() => startQuiz("purpose")}>
            Begin <span className="arrow">→</span>
          </button>
          <p className="landing-skip">
            <button className="btn-text-link" onClick={() => switchView("dashboard")}>
              Skip for now — explore first
            </button>
          </p>
          <p className="landing-login">
            Already have an account?{" "}
            <button className="btn-text-link" onClick={() => { setAuthView("login"); switchView("auth"); }}>
              Log in
            </button>
          </p>
          <div className="gc-scroll-hint">
            <span className="gc-scroll-arrow">↓</span>
          </div>
        </div>

        <div className="gc-flow">
          <div className="gc-why">
            <div className="gc-why-belief">Most people care. Very few act.<br />Not because they&apos;re selfish — because <em>doing good was designed for people with something to spare</em>.</div>
            <div className="gc-why-body">Donation apps want your credit card. Volunteer sites want your weekends. Food banks want your car. So the person with five minutes and zero dollars? They close the tab and feel guilty instead. That&apos;s not a character flaw. That&apos;s a design failure.</div>
          </div>

          <div className="gc-how">
            <div className="gc-label">How it works</div>
            <div className="gc-how-title">Start with purpose. End with proof.</div>
            <div className="gc-pillars">
              <div className="gc-pillar">
                <span className="gc-pillar-num">1</span>
                <div className="gc-pillar-body">
                  <div className="gc-pillar-name">Figure out what you actually care about</div>
                  <div className="gc-pillar-desc">Not what sounds good on paper. Four research-backed quizzes reveal your purpose archetype — the specific way <em>you</em> show up when it matters.</div>
                </div>
              </div>
              <div className="gc-pillar">
                <span className="gc-pillar-num">2</span>
                <div className="gc-pillar-body">
                  <div className="gc-pillar-name">Give in whatever way fits your life right now</div>
                  <div className="gc-pillar-desc">Got money? Donate directly. Got food? List it. Got nothing but 60 seconds? Watch a clip — 75% of ad revenue funds the cause you pick. No minimums, no guilt.</div>
                </div>
              </div>
              <div className="gc-pillar">
                <span className="gc-pillar-num">3</span>
                <div className="gc-pillar-body">
                  <div className="gc-pillar-name">Know — don&apos;t hope — that it landed</div>
                  <div className="gc-pillar-desc">NFC tap, QR scan, GPS. A verified chain of evidence that your food, tickets, or goods reached a real person. Not a thank-you email. Proof you can see.</div>
                </div>
              </div>
            </div>
          </div>

          <div className="gc-what">
            <div className="gc-label">What this means for you</div>
            <div className="gc-proof-list">
              <div className="gc-proof-item"><span className="gc-proof-icon">💯</span><span className="gc-proof-text"><strong>Zero fees</strong> on every donation — every cent goes to the cause</span></div>
              <div className="gc-proof-item"><span className="gc-proof-icon">⏱</span><span className="gc-proof-text"><strong>No money needed</strong> — donate your time by watching a short clip</span></div>
              <div className="gc-proof-item"><span className="gc-proof-icon">📋</span><span className="gc-proof-text"><strong>Tax-deductible</strong> — IRS-ready receipts sent automatically via Every.org</span></div>
              <div className="gc-proof-item"><span className="gc-proof-icon">🏅</span><span className="gc-proof-text"><strong>Milestones & rewards</strong> — earn points, unlock achievements, redeem perks</span></div>
            </div>
            <div className="gc-cta-wrap">
              <button className="btn-begin" onClick={() => startQuiz("purpose")}>
                Find your purpose <span className="arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ── Auth ── */}
      <section className={`view feed-view ${activeView === "auth" ? "active" : ""}`} {...(activeView !== "auth" ? { inert: true } : {})}>
        <div className="feed-scroll">
          <div className="auth-container">
            <div className="auth-logo">imprint</div>

            {authView === "signup" && arch && (
              <div className="auth-archetype-badge">
                <span className="auth-archetype-icon">{arch.badge}</span>
                <span className="auth-archetype-name">{arch.name}</span>
              </div>
            )}

            <h2 className="auth-title">
              {authView === "login" && "Welcome back"}
              {authView === "signup" && (arch ? "Save your results" : "Create your account")}
              {authView === "forgot" && "Reset password"}
            </h2>
            <p className="auth-subtitle">
              {authView === "login" && "Log in to continue your impact journey"}
              {authView === "signup" && (arch ? `Your archetype, milestones, and impact — all saved.` : "Start tracking your purpose and impact")}
              {authView === "forgot" && "We'll send you a reset link"}
            </p>

            {authView !== "forgot" && (
              <div className="auth-social">
                <button className="auth-social-btn" onClick={() => handleSocialAuth("google")} disabled={authLoading}>
                  <span className="auth-social-icon">G</span>
                  Continue with Google
                </button>
                <button className="auth-social-btn" onClick={() => handleSocialAuth("apple")} disabled={authLoading}>
                  <span className="auth-social-icon"></span>
                  Continue with Apple
                </button>
              </div>
            )}

            {authView !== "forgot" && <div className="auth-divider"><span>or</span></div>}

            <form className="auth-form" onSubmit={handleAuth}>
              {authView === "signup" && (
                <div className="auth-field">
                  <label htmlFor="auth-name">Name</label>
                  <input
                    id="auth-name"
                    type="text" placeholder="Your name"
                    value={authForm.name}
                    required
                    autoComplete="name"
                    onChange={(e) => setAuthForm((f) => ({ ...f, name: e.target.value }))}
                  />
                </div>
              )}
              <div className="auth-field">
                <label htmlFor="auth-email">Email</label>
                <input
                  id="auth-email"
                  type="email" placeholder="you@example.com"
                  value={authForm.email}
                  required
                  autoComplete="email"
                  onChange={(e) => setAuthForm((f) => ({ ...f, email: e.target.value }))}
                />
              </div>
              {authView !== "forgot" && (
                <div className="auth-field">
                  <label htmlFor="auth-password">Password</label>
                  <input
                    id="auth-password"
                    type="password" placeholder="••••••••"
                    value={authForm.password}
                    required
                    minLength={8}
                    autoComplete={authView === "signup" ? "new-password" : "current-password"}
                    onChange={(e) => setAuthForm((f) => ({ ...f, password: e.target.value }))}
                  />
                </div>
              )}
              {authError && <p className="auth-error" role="alert">{authError}</p>}
              <button className="btn-continue btn-wide auth-submit" type="submit" disabled={authLoading}>
                {authLoading ? "..." : authView === "login" ? "Log in" : authView === "signup" ? "Create account" : "Send reset link"}
              </button>
            </form>

            {authView === "login" && (
              <div className="auth-links">
                <button className="auth-link" onClick={() => { setAuthView("forgot"); setAuthError(null); }}>
                  Forgot password?
                </button>
                <button className="auth-link" onClick={() => { setAuthView("signup"); setAuthError(null); }}>
                  Don&apos;t have an account? <strong>Sign up</strong>
                </button>
              </div>
            )}
            {authView === "signup" && (
              <div className="auth-links">
                <button className="auth-link" onClick={() => { setAuthView("login"); setAuthError(null); }}>
                  Already have an account? <strong>Log in</strong>
                </button>
              </div>
            )}
            {authView === "forgot" && (
              <div className="auth-links">
                <button className="auth-link" onClick={() => { setAuthView("login"); setAuthError(null); }}>
                  ← Back to log in
                </button>
              </div>
            )}

            <button className="btn-back auth-skip" onClick={() => switchView("landing")}>
              ← Continue without account
            </button>
          </div>
        </div>
      </section>

      {/* ── Quiz ── */}
      <section className={`view quiz-view ${activeView === "quiz" ? "active" : ""}`} {...(activeView !== "quiz" ? { inert: true } : {})}>
        {activeQuiz && (
          <>
            <div className="quiz-progress" role="group" aria-label={`Question ${quizState.currentQ + 1} of ${activeQuiz.questions.length}`}>
              {activeQuiz.questions.map((_, i) => (
                <div
                  key={i}
                  className={`quiz-dot ${i === quizState.currentQ ? "active" : ""} ${
                    i < quizState.currentQ ? "done" : ""
                  }`}
                  aria-hidden="true"
                />
              ))}
            </div>
            <div className={`quiz-inner ${quizFading ? "fading" : ""}`} aria-live="polite">
              <p className="quiz-label">
                {activeQuiz.name} · Question {quizState.currentQ + 1} of{" "}
                {activeQuiz.questions.length}
              </p>
              <h2 className="quiz-question">
                {activeQuiz.questions[quizState.currentQ].text}
              </h2>
              <div className="quiz-options">
                {activeQuiz.questions[quizState.currentQ].options.map((opt, i) => (
                  <button
                    key={`${activeQuizId}-${quizState.currentQ}-${i}`}
                    className="quiz-option"
                    disabled={isQuizAnswering}
                    onClick={() => handleAnswer(opt)}
                  >
                    {opt.text}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </section>

      {/* ── Reveal (first-time purpose only) ── */}
      <section className={`view reveal-view ${activeView === "reveal" ? "active" : ""}`} {...(activeView !== "reveal" ? { inert: true } : {})}>
        <div className={`reveal-loading ${revealPhase !== "loading" ? "hidden" : ""}`}>
          <div className="reveal-pulse" />
          <p className="reveal-loading-text">Listening to your answers…</p>
        </div>
        {arch && (
          <div className={`reveal-content ${revealPhase === "content" ? "visible" : ""}`} aria-live="polite">
            <p className="reveal-eyebrow">Your purpose archetype</p>
            <ArchetypeCard archetype={arch} typeKey={primaryArchetype} mode="full" />
            {user ? (
              <button className="btn-continue" onClick={() => switchView("dashboard")}>
                See your profile <span className="arrow">→</span>
              </button>
            ) : (
              <>
                <button className="btn-continue" onClick={() => { setAuthView("signup"); switchView("auth"); }}>
                  Save your results <span className="arrow">→</span>
                </button>
                <button className="btn-text-link reveal-skip" onClick={() => switchView("dashboard")}>
                  Skip for now
                </button>
              </>
            )}
          </div>
        )}
      </section>

      {/* ── Dashboard ── */}
      <section className={`view feed-view ${activeView === "dashboard" ? "active" : ""}`} {...(activeView !== "dashboard" ? { inert: true } : {})}>
        <div className="feed-scroll">
          <div className="dashboard-header">
            <h2 className="dashboard-title">Your Imprint</h2>
            {userLocation !== "your neighborhood" && (
              <div className="location-badge">
                <span className="location-badge-icon">📍</span> {userLocation}
              </div>
            )}
            {arch && (
              <ArchetypeCard archetype={arch} typeKey={primaryArchetype} mode="mini" />
            )}
          </div>

          {/* Quiz prompt banner — when no quizzes completed */}
          {completedCount === 0 && (
            <div className="quiz-prompt-banner">
              <div className="quiz-prompt-icon">🧭</div>
              <div className="quiz-prompt-text">
                <strong>What kind of difference-maker are you?</strong>
                <span>1 min · 5 questions · your purpose archetype</span>
              </div>
              <button className="btn-small btn-small-accent" onClick={() => startQuiz("purpose")}>
                Start →
              </button>
            </div>
          )}

          {/* Radar charts */}
          <div className="radars-grid">
            {quizCategories.map((cat) => {
              const result = quizResults[cat.id];
              const isComplete = !!result;
              return (
                <div key={cat.id} className={`radar-card ${isComplete ? "complete" : ""}`}>
                  <div className="radar-card-header">
                    <span className="radar-card-icon">{cat.icon}</span>
                    <span className="radar-card-name">{cat.name}</span>
                  </div>
                  {isComplete ? (
                    <>
                      <RadarChart
                        scores={result.scores}
                        dimensions={cat.dimensions}
                        maxScore={cat.questions.length}
                        size={160}
                      />
                      <div className="radar-card-actions">
                        <button
                          className="btn-small"
                          onClick={() => openReview(cat.id)}
                        >
                          Review answers
                        </button>
                        <button
                          className="btn-small btn-small-outline"
                          onClick={() => startQuiz(cat.id)}
                        >
                          Retake
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="radar-card-empty">
                        <p className="radar-card-desc">{cat.description}</p>
                      </div>
                      <button
                        className="btn-small btn-small-accent"
                        onClick={() => startQuiz(cat.id)}
                      >
                        Start quiz →
                      </button>
                    </>
                  )}
                </div>
              );
            })}
          </div>

          {/* Quest — Purpose app lesson: turn discovery into action */}
          {purposeResult && (
            <div className="quest-section">
              <div className="quest-header">
                <span className="quest-badge">Your Quest</span>
                <span className="quest-archetype-tag" style={{ color: arch?.color }}>{arch?.badge}</span>
              </div>
              <div className="quest-card">
                <div className="quest-card-prompt">
                  {primaryArchetype === "connector" && "Start a conversation with someone you've never spoken to in your neighborhood this week."}
                  {primaryArchetype === "builder" && "Find one broken or neglected thing in your neighborhood and fix it — or photograph it and share the vision."}
                  {primaryArchetype === "guide" && "Ask one person younger than you what they're working on — and actually listen to the answer."}
                  {primaryArchetype === "solver" && "Pick one local problem you've complained about and spend 20 minutes researching who's already working on it."}
                </div>
                <div className="quest-card-why">
                  <span className="quest-why-label">Why this matters</span>
                  <span className="quest-why-text">Small actions compound. This is how {arch?.name?.replace("The ", "")}s make their first dent.</span>
                </div>
              </div>
            </div>
          )}

          {/* Completed summary */}
          <div className="dashboard-progress">
            <div className="progress-bar" role="progressbar" aria-valuenow={completedCount} aria-valuemin={0} aria-valuemax={quizCategories.length} aria-label="Quiz completion progress">
              <div
                className="progress-fill"
                style={{ width: `${(completedCount / quizCategories.length) * 100}%` }}
              />
            </div>
            <p className="progress-label">
              {completedCount} of {quizCategories.length} quizzes completed —{" "}
              {completedCount < quizCategories.length
                ? "keep exploring to sharpen your matches"
                : "full profile unlocked"}
            </p>
          </div>

          {/* Location request */}
          {locationStatus === "idle" && (
            <div className="location-bar">
              <span className="location-bar-icon">📍</span>
              <div className="location-bar-text">
                <strong>Find opportunities near you</strong><br />
                Allow location to see what&apos;s happening in your area
              </div>
              <button className="location-bar-btn" onClick={requestUserLocation}>Allow</button>
            </div>
          )}
          {locationStatus === "denied" && (
            <div className="location-bar location-bar-denied">
              <span className="location-bar-icon">⚠️</span>
              <div className="location-bar-text">
                <strong>Location unavailable</strong><br />
                Check your browser settings to enable access
              </div>
              <button className="location-bar-btn" onClick={() => { setLocationStatus("idle"); requestUserLocation(); }}>Retry</button>
            </div>
          )}

          {/* Offer CTA */}
          <div className="offer-cta-section">
            <button className="offer-cta" onClick={openOffer}>
              <span className="offer-cta-icon">✦</span>
              <div className="offer-cta-text">
                <strong>I have something to offer</strong>
                <span>Donate tickets, food, services, or goods — tax-deductible</span>
              </div>
              <span className="offer-cta-arrow">→</span>
            </button>
            {offers.length > 0 && (
              <div className="offer-cta-summary">
                <span>{offers.length} contribution{offers.length > 1 ? "s" : ""}</span>
                <span className="offer-cta-divider">·</span>
                <span>${totalDonationValue.toLocaleString()} donated</span>
              </div>
            )}
          </div>

          {/* Time Donation CTA */}
          <div className="time-donate-cta-section">
            <button className="time-donate-cta" onClick={openTimeDonate}>
              <span className="time-donate-cta-icon">⏱</span>
              <div className="time-donate-cta-text">
                <strong>Donate your time</strong>
                <span>Watch a clip — 75% of ad revenue goes to causes</span>
              </div>
              <span className="offer-cta-arrow">→</span>
            </button>
            {timeDonation.totalAdsWatched > 0 && (
              <div className="time-donate-cta-summary">
                <span>${(timeDonation.totalAdsWatched * AD_CAUSE_REVENUE).toFixed(2)} raised</span>
                <span className="offer-cta-divider">·</span>
                <span>{timeDonation.totalAdsWatched} clip{timeDonation.totalAdsWatched > 1 ? "s" : ""}</span>
                <span className="offer-cta-divider">·</span>
                <span>✦ {totalPoints} pts total</span>
              </div>
            )}
          </div>

          {/* Direct Donation CTA */}
          <div className="direct-donate-cta-section">
            <button className="direct-donate-cta" onClick={openDirectDonate}>
              <span className="direct-donate-cta-icon">💸</span>
              <div className="direct-donate-cta-text">
                <strong>Give directly</strong>
                <span>100% goes to the cause — zero fees</span>
              </div>
              <span className="offer-cta-arrow">→</span>
            </button>
            {directDonation.totalDonated > 0 && (
              <div className="direct-donate-cta-summary">
                <span>${directDonation.totalDonated.toFixed(2)} donated</span>
                <span className="offer-cta-divider">·</span>
                <span>{directDonation.history.length} donation{directDonation.history.length > 1 ? "s" : ""}</span>
                <span className="offer-cta-divider">·</span>
                <span>✦ +{directDonation.history.reduce((s, d) => s + (d.pointsEarned || Math.floor(d.amount * 50)), 0)} pts</span>
              </div>
            )}
          </div>

          {/* Premium CTA */}
          {!isPremium && (
            <button className="premium-cta" onClick={() => { setPremiumPhase("info"); switchView("premium"); }}>
              <span className="premium-cta-badge">imprint+</span>
              <div className="premium-cta-text">
                <strong>Go premium</strong>
                <span>$3/mo auto-donated to causes + 2× points</span>
              </div>
              <span className="offer-cta-arrow">→</span>
            </button>
          )}
          {isPremium && (
            <div className="premium-active-badge">
              <span className="premium-active-icon">⚡</span>
              <span>imprint+ member — $3/mo to causes + 2× points</span>
            </div>
          )}

          {/* My Impact CTA */}
          {(timeDonation.totalAdsWatched > 0 || offers.length > 0 || joinedCards.size > 0 || Object.keys(quizResults).length > 0 || directDonation.history.length > 0) && (
            <button className="impact-cta" onClick={openMyImpact}>
              <span className="impact-cta-icon">🌿</span>
              <div className="impact-cta-text">
                <strong>My Impact</strong>
                <span>Lifetime achievements &amp; shareable card</span>
              </div>
              <span className="offer-cta-arrow">→</span>
            </button>
          )}

          {/* CTA to feed */}
          {purposeResult && (
            <button className="btn-continue btn-wide" onClick={showFeed}>
              See your opportunities <span className="arrow">→</span>
            </button>
          )}
        </div>
      </section>

      {/* ── Answer Review ── */}
      <section className={`view feed-view ${activeView === "review" ? "active" : ""}`} {...(activeView !== "review" ? { inert: true } : {})}>
        {reviewQuiz && reviewResult && (
          <div className="feed-scroll">
            <button className="btn-back" onClick={() => switchView("dashboard")}>
              ← Back to profile
            </button>

            <div className="review-header">
              <span className="review-icon">{reviewQuiz.icon}</span>
              <h2 className="review-title">{reviewQuiz.name}</h2>
              <p className="review-subtitle">
                Tap &ldquo;Change&rdquo; on any answer to update it. Your profile
                recalculates instantly.
              </p>
            </div>

            <div className="review-chart">
              <RadarChart
                scores={reviewResult.scores}
                dimensions={reviewQuiz.dimensions}
                maxScore={reviewQuiz.questions.length}
                size={180}
              />
            </div>

            <div className="review-questions">
              {reviewQuiz.questions.map((q, qi) => {
                const answer = reviewResult.answers[qi];
                const isEditing = editingQ === qi;
                return (
                  <div key={qi} className={`review-q ${isEditing ? "editing" : ""}`}>
                    <p className="review-q-label">Question {qi + 1}</p>
                    <p className="review-q-text">{q.text}</p>
                    {isEditing ? (
                      <div className="review-options">
                        {q.options.map((opt) => (
                          <button
                            key={opt.type}
                            className={`review-option ${
                              answer && answer.type === opt.type ? "current" : ""
                            }`}
                            onClick={() => updateAnswer(qi, opt)}
                          >
                            {opt.text}
                            {answer && answer.type === opt.type && (
                              <span className="current-badge">current</span>
                            )}
                          </button>
                        ))}
                        <button
                          className="btn-small btn-small-outline"
                          onClick={() => setEditingQ(null)}
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div className="review-answer-row">
                        <p className="review-answer">{answer ? answer.text : "—"}</p>
                        <button
                          className="btn-change"
                          onClick={() => setEditingQ(qi)}
                        >
                          Change
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="review-footer">
              <button
                className="btn-small btn-small-outline"
                onClick={() => startQuiz(reviewQuizId)}
              >
                Retake entire quiz ↺
              </button>
            </div>
          </div>
        )}
      </section>

      {/* ── Offer Flow ── */}
      <section className={`view feed-view ${activeView === "offer" ? "active" : ""}`} {...(activeView !== "offer" ? { inert: true } : {})}>
        <div className="feed-scroll">
          <OfferFlow
            key={offerFlowKey}
            onBack={() => switchView("dashboard")}
            onSubmit={handleOfferSubmit}
          />
        </div>
      </section>

      {/* ── Time Donation ── */}
      <section className={`view feed-view ${activeView === "timedonate" ? "active" : ""}`} {...(activeView !== "timedonate" ? { inert: true } : {})}>
        <div className="feed-scroll">
          <button className="btn-back" onClick={() => switchView("dashboard")}>
            ← Back to profile
          </button>

          <div className="time-donate-header">
            <div className="time-donate-hero-icon">⏱</div>
            <h2 className="time-donate-title">Donate Your Time</h2>
            <p className="time-donate-subtitle">
              Watch a 1-minute clip. <strong>75% of ad revenue</strong> goes directly to the cause you choose. 25% keeps imprint running.
              <br />Zero money from your pocket — just your attention.
            </p>
          </div>

          {/* Phase: Choose cause */}
          {timeDonation.adPhase === "choose" && (
            <div className="time-donate-causes">
              <p className="time-donate-choose-label">Choose where your time goes</p>
              {timeDonationCauses.map((cause) => (
                <button
                  key={cause.id}
                  className={`time-donate-cause ${timeDonation.selectedCause === cause.id ? "selected" : ""}`}
                  aria-pressed={timeDonation.selectedCause === cause.id}
                  onClick={() => selectCause(cause.id)}
                >
                  <span className="time-donate-cause-emoji">{cause.emoji}</span>
                  <div className="time-donate-cause-info">
                    <strong>{cause.name}</strong>
                    <span>{cause.adsPerUnit} ads = 1 {cause.unit} · via {cause.partner}</span>
                  </div>
                  {timeDonation.impactLog[cause.id] > 0 && (
                    <span className="time-donate-cause-count">
                      {Math.floor(timeDonation.impactLog[cause.id])} {cause.unit}{Math.floor(timeDonation.impactLog[cause.id]) !== 1 ? "s" : ""}
                    </span>
                  )}
                  <span className="time-donate-cause-check">
                    {timeDonation.selectedCause === cause.id ? "●" : "○"}
                  </span>
                </button>
              ))}
              {timeDonation.selectedCause && (
                <button className="btn-continue btn-wide" onClick={startWatchingAd} style={{ marginTop: "20px" }}>
                  Watch a clip for {timeDonationCauses.find((c) => c.id === timeDonation.selectedCause)?.name} <span className="arrow">→</span>
                </button>
              )}
            </div>
          )}

          {/* Phase: Watching ad */}
          {timeDonation.adPhase === "watching" && (() => {
            const watchCause = timeDonationCauses.find((c) => c.id === timeDonation.selectedCause);
            return (
            <div className="time-donate-player">
              <div className="ad-player-box">
                <div className="ad-player-content">
                  <div className="ad-player-shimmer" />
                  <p className="ad-player-label">🎬 Ad playing…</p>
                  <p className="ad-player-sponsor">Sponsored content</p>
                </div>
                <div className="ad-progress-bar" role="progressbar" aria-valuenow={Math.round(timeDonation.adProgress)} aria-valuemin={0} aria-valuemax={100} aria-label="Ad playback progress">
                  <div
                    className="ad-progress-fill"
                    style={{ width: `${timeDonation.adProgress}%` }}
                  />
                </div>
                <p className="ad-progress-label">
                  {timeDonation.adProgress >= 100 ? "Done!" : `${Math.ceil(60 - (timeDonation.adProgress / 100) * 60)}s remaining`}
                </p>
              </div>
              <div className="ad-cause-reminder">
                <span>{watchCause?.emoji}</span>
                <span>Revenue going to: <strong>{watchCause?.name}</strong></span>
              </div>
            </div>
            );
          })()}

          {/* Phase: Complete */}
          {timeDonation.adPhase === "complete" && (() => {
            const cause = timeDonationCauses.find((c) => c.id === timeDonation.selectedCause);
            return (
              <div className="time-donate-complete">
                <div className="time-donate-complete-icon">🎉</div>
                <h3 className="time-donate-complete-title">Time donated!</h3>
                <p className="time-donate-complete-desc">
                  Your 1 minute just contributed to <strong>{cause?.name?.toLowerCase()}</strong>.
                </p>

                <div className="time-donate-receipt">
                  <div className="receipt-row">
                    <span>Cause</span>
                    <span>{cause?.emoji} {cause?.name}</span>
                  </div>
                  <div className="receipt-row">
                    <span>Partner</span>
                    <span>{cause?.partner}</span>
                  </div>
                  <div className="receipt-row">
                    <span>Ad revenue generated</span>
                    <span>≈ ${AD_GROSS_REVENUE.toFixed(3)}</span>
                  </div>
                  <div className="receipt-row">
                    <span>To cause (75%)</span>
                    <span style={{ color: "var(--accent)" }}>≈ ${AD_CAUSE_REVENUE.toFixed(3)}</span>
                  </div>
                  <div className="receipt-row">
                    <span>Keeps imprint running (25%)</span>
                    <span>≈ ${AD_APP_REVENUE.toFixed(3)}</span>
                  </div>
                  <div className="receipt-row">
                    <span>Progress to 1 {cause?.unit}</span>
                    <span>{cause ? `${Math.round(((timeDonation.impactLog[cause.id] || 0) % 1) * cause.adsPerUnit)}/${cause.adsPerUnit} ads` : "0/0 ads"}</span>
                  </div>
                  <div className="receipt-row">
                    <span>Total {cause?.unit}s funded</span>
                    <span>{Math.floor(timeDonation.impactLog[cause?.id] || 0)}</span>
                  </div>
                  <div className="receipt-row">
                    <span>Points earned</span>
                    <span>✦ +{isPremium ? 20 : 10} pts{isPremium ? " (2×)" : ""}</span>
                  </div>
                </div>

                <div className="time-donate-actions">
                  <button className="btn-continue btn-wide" onClick={watchAnother}>
                    Watch another <span className="arrow">→</span>
                  </button>
                  <button className="btn-small btn-small-outline" onClick={() => switchView("dashboard")} style={{ marginTop: "10px", width: "100%" }}>
                    Back to profile
                  </button>
                </div>

                {/* Impact summary */}
                {Object.keys(timeDonation.impactLog).length > 0 && (
                  <div className="time-donate-impact-summary">
                    <p className="time-donate-impact-title">Your total time impact</p>
                    <div className="time-donate-impact-grid">
                      {timeDonationCauses
                        .filter((c) => timeDonation.impactLog[c.id] > 0)
                        .map((cause) => {
                          const total = timeDonation.impactLog[cause.id];
                          const completed = Math.floor(total);
                          const progressPct = Math.round((total % 1) * 100);
                          return (
                            <div key={cause.id} className="time-donate-impact-item">
                              <span className="impact-item-emoji">{cause.emoji}</span>
                              <div className="impact-item-detail">
                                <span className="impact-item-num">{completed}</span>
                                <span className="impact-item-unit">{cause.unit}{completed !== 1 ? "s" : ""}</span>
                                {progressPct > 0 && (
                                  <span className="impact-item-progress">+{progressPct}% to next</span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      </section>

      {/* ── Direct Donation ── */}
      <section className={`view feed-view ${activeView === "directdonate" ? "active" : ""}`} {...(activeView !== "directdonate" ? { inert: true } : {})}>
        <div className="feed-scroll">
          <button className="btn-back" onClick={() => switchView("dashboard")}>
            ← Back to profile
          </button>

          <div className="time-donate-header">
            <div className="time-donate-hero-icon">💸</div>
            <h2 className="time-donate-title">Give Directly</h2>
            <p className="time-donate-subtitle">
              100% of your donation goes to the cause.
              <br />Zero fees. Zero middlemen. Just impact.
            </p>
          </div>

          {/* Phase: Choose */}
          {directDonation.phase === "choose" && (
            <div className="time-donate-causes">
              <p className="time-donate-choose-label">Choose a cause</p>
              {directDonationCauses.map((cause) => (
                <button
                  key={cause.id}
                  className={`time-donate-cause ${directDonation.selectedCause === cause.id ? "selected" : ""}`}
                  aria-pressed={directDonation.selectedCause === cause.id}
                  onClick={() => selectDirectCause(cause.id)}
                >
                  <span className="time-donate-cause-emoji">{cause.emoji}</span>
                  <div className="time-donate-cause-info">
                    <strong>{cause.name}</strong>
                    <span>{cause.desc} · via {cause.partner}</span>
                  </div>
                  {directDonationForCause(cause.id) > 0 && (
                    <span className="time-donate-cause-count">
                      ${directDonationForCause(cause.id).toFixed(2)}
                    </span>
                  )}
                  <span className="time-donate-cause-check">
                    {directDonation.selectedCause === cause.id ? "●" : "○"}
                  </span>
                </button>
              ))}

              {directDonation.selectedCause && (
                <>
                  <p className="time-donate-choose-label" style={{ marginTop: "24px" }}>Choose an amount</p>
                  <div className="direct-amount-grid">
                    {donationAmounts.map((amt) => (
                      <button
                        key={amt}
                        className={`direct-amount-btn ${directDonation.selectedAmount === amt ? "selected" : ""}`}
                        aria-pressed={directDonation.selectedAmount === amt}
                        onClick={() => selectDirectAmount(amt)}
                      >
                        ${amt}
                      </button>
                    ))}
                  </div>
                  <div className="direct-custom-row">
                    <span className="direct-custom-dollar">$</span>
                    <input
                      className="direct-custom-input"
                      type="number"
                      placeholder="Other amount"
                      aria-label="Custom donation amount in dollars"
                      min="1"
                      max="25000"
                      step="0.01"
                      value={directDonation.customAmount}
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val === "" || /^\d{0,5}(\.\d{0,2})?$/.test(val)) {
                          setDirectDonation((prev) => ({ ...prev, customAmount: val, selectedAmount: null }));
                        }
                      }}
                    />
                  </div>
                  {directDonation.customAmount && parseFloat(directDonation.customAmount) > 0 && parseFloat(directDonation.customAmount) < 1 && (
                    <p className="direct-min-hint" role="alert">Minimum donation is $1</p>
                  )}

                  {/* Impact preview */}
                  {getDirectDonationAmount() > 0 && (() => {
                    const cause = directDonationCauses.find((c) => c.id === directDonation.selectedCause);
                    const amount = getDirectDonationAmount();
                    const units = Math.round(amount / cause.costPerUnit);
                    return (
                      <div className="direct-impact-preview">
                        <span className="direct-impact-preview-emoji">{cause.emoji}</span>
                        <span className="direct-impact-preview-text">
                          ${amount} → <strong>{units.toLocaleString()} {cause.unit}{units !== 1 ? "s" : ""}</strong> via {cause.partner}
                        </span>
                      </div>
                    );
                  })()}

                  {getDirectDonationAmount() > 0 && (
                    <button className="btn-continue btn-wide" onClick={() => setDirectDonation((prev) => ({ ...prev, phase: "confirm" }))} style={{ marginTop: "16px" }}>
                      Continue <span className="arrow">→</span>
                    </button>
                  )}
                </>
              )}
            </div>
          )}

          {/* Phase: Confirm */}
          {directDonation.phase === "confirm" && (() => {
            const cause = directDonationCauses.find((c) => c.id === directDonation.selectedCause);
            const amount = getDirectDonationAmount();
            const units = Math.round(amount / cause.costPerUnit);
            return (
              <div className="time-donate-complete">
                <h3 className="time-donate-complete-title" style={{ marginTop: "8px" }}>Confirm your donation</h3>
                <div className="time-donate-receipt">
                  <div className="receipt-row">
                    <span>Cause</span>
                    <span>{cause.emoji} {cause.name}</span>
                  </div>
                  <div className="receipt-row">
                    <span>Partner</span>
                    <span>{cause.partner}</span>
                  </div>
                  <div className="receipt-row">
                    <span>EIN</span>
                    <span>{NONPROFIT_PARTNERS[cause.partner]?.ein}</span>
                  </div>
                  <div className="receipt-row">
                    <span>Amount</span>
                    <span><strong>${amount.toFixed(2)}</strong></span>
                  </div>
                  <div className="receipt-row">
                    <span>Fees</span>
                    <span style={{ color: "var(--accent)" }}>$0.00 (0%)</span>
                  </div>
                  <div className="receipt-row">
                    <span>To cause</span>
                    <span style={{ color: "var(--accent)" }}><strong>${amount.toFixed(2)}</strong></span>
                  </div>
                  <div className="receipt-row">
                    <span>Impact</span>
                    <span>{units.toLocaleString()} {cause.unit}{units !== 1 ? "s" : ""}</span>
                  </div>
                  <div className="receipt-row receipt-row-muted">
                    <span>Processed by</span>
                    <span>Every.org</span>
                  </div>
                </div>
                <div className="direct-zero-fee-badge">
                  <span>✓</span> Zero-fee donation — every cent goes to {cause.partner}
                </div>
                <div className="tax-deductible-note">
                  <span>📋</span>
                  <span>Tax-deductible via Every.org (501(c)(3)). You&apos;ll receive an IRS-ready receipt by email.</span>
                </div>
                <div className="everyorg-badge">
                  <span className="everyorg-badge-icon">🌐</span>
                  <span>Secure checkout by <strong>Every.org</strong></span>
                </div>
                <div className="time-donate-actions">
                  <button className="btn-continue btn-wide" onClick={confirmDirectDonation} disabled={directDonation.phase === "processing"}>
                    Donate ${amount.toFixed(2)} <span className="arrow">→</span>
                  </button>
                  <button className="btn-small btn-small-outline" onClick={() => setDirectDonation((prev) => ({ ...prev, phase: "choose" }))} style={{ marginTop: "10px", width: "100%" }}>
                    ← Change amount
                  </button>
                </div>
              </div>
            );
          })()}

          {/* Phase: Processing */}
          {directDonation.phase === "processing" && (
            <div className="time-donate-complete" style={{ textAlign: "center" }}>
              <div className="direct-processing-spinner" />
              <h3 className="time-donate-complete-title">Processing…</h3>
              <p className="time-donate-complete-desc">Securely processing via Every.org</p>
            </div>
          )}

          {/* Phase: Complete */}
          {directDonation.phase === "complete" && (() => {
            const lastDonation = directDonation.history[directDonation.history.length - 1];
            const cause = directDonationCauses.find((c) => c.id === lastDonation?.causeId);
            return (
              <div className="time-donate-complete">
                <div className="time-donate-complete-icon">💚</div>
                <h3 className="time-donate-complete-title">Thank you!</h3>
                <p className="time-donate-complete-desc">
                  Your <strong>${lastDonation?.amount?.toFixed(2)}</strong> was sent to <strong>{cause?.partner}</strong> via Every.org.
                  <br />That&apos;s <strong>{lastDonation?.unitsGenerated?.toLocaleString()} {cause?.unit}{lastDonation?.unitsGenerated !== 1 ? "s" : ""}</strong> funded.
                </p>

                <div className="time-donate-receipt">
                  <div className="receipt-row">
                    <span>Cause</span>
                    <span>{cause?.emoji} {cause?.name}</span>
                  </div>
                  <div className="receipt-row">
                    <span>Partner</span>
                    <span>{cause?.partner}</span>
                  </div>
                  <div className="receipt-row">
                    <span>EIN</span>
                    <span className="receipt-ein">{NONPROFIT_PARTNERS[cause?.partner]?.ein}</span>
                  </div>
                  <div className="receipt-row">
                    <span>Processed by</span>
                    <span>Every.org (501(c)(3))</span>
                  </div>
                  <div className="receipt-row">
                    <span>Amount donated</span>
                    <span>${lastDonation?.amount?.toFixed(2)}</span>
                  </div>
                  <div className="receipt-row">
                    <span>Platform fees</span>
                    <span style={{ color: "var(--accent)" }}>$0.00</span>
                  </div>
                  <div className="receipt-row">
                    <span>Impact</span>
                    <span>{lastDonation?.unitsGenerated?.toLocaleString()} {cause?.unit}{lastDonation?.unitsGenerated !== 1 ? "s" : ""}</span>
                  </div>
                  <div className="receipt-row">
                    <span>Points earned</span>
                    <span>✦ +{lastDonation?.pointsEarned ?? Math.floor((lastDonation?.amount || 0) * 50)} pts{lastDonation?.wasPremium ? " (2×)" : ""}</span>
                  </div>
                </div>

                <div className="tax-receipt-actions">
                  <button className="btn-tax-receipt" onClick={() => openReceiptDetail(lastDonation, "directdonate")}>
                    📋 View full receipt
                  </button>
                  <button className="btn-tax-receipt btn-tax-receipt-secondary" onClick={openEveryOrgReceipts}>
                    🌐 Official receipt on Every.org
                  </button>
                  <p className="tax-receipt-note">
                    Your official IRS tax receipt was emailed by Every.org. No goods or services were received.
                  </p>
                </div>

                <div className="time-donate-actions">
                  <button className="btn-continue btn-wide" onClick={openDirectDonate}>
                    Give again <span className="arrow">→</span>
                  </button>
                  <button className="btn-small btn-small-outline" onClick={() => switchView("dashboard")} style={{ marginTop: "10px", width: "100%" }}>
                    Back to profile
                  </button>
                </div>

                {/* Donation history */}
                {directDonation.history.length > 0 && (
                  <div className="time-donate-impact-summary">
                    <p className="time-donate-impact-title">Your giving history</p>
                    <div className="time-donate-impact-grid">
                      {directDonationCauses
                        .filter((c) => directDonationForCause(c.id) > 0)
                        .map((cause) => (
                          <div key={cause.id} className="time-donate-impact-item">
                            <span className="impact-item-emoji">{cause.emoji}</span>
                            <div className="impact-item-detail">
                              <span className="impact-item-num">${directDonationForCause(cause.id).toFixed(2)}</span>
                              <span className="impact-item-unit">{cause.name}</span>
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      </section>

      {/* ── Premium (imprint+) ── */}
      <section className={`view feed-view ${activeView === "premium" ? "active" : ""}`} {...(activeView !== "premium" ? { inert: true } : {})}>
        <div className="feed-scroll">
          <button className="btn-back" onClick={() => switchView("dashboard")}>
            ← Back to profile
          </button>

          {premiumPhase === "info" && (
            <>
              <div className="premium-header">
                <div className="premium-badge-large">imprint+</div>
                <h2 className="premium-title">Do more good</h2>
                <p className="premium-subtitle">
                  $3 of every $4.99 goes directly to causes you choose.<br />The rest keeps imprint free for everyone.
                </p>
              </div>

              <div className="premium-perks">
                {PREMIUM_PERKS.map((perk) => (
                  <div key={perk.name} className={`premium-perk${perk.hero ? " hero" : ""}`}>
                    <span className="premium-perk-emoji">{perk.emoji}</span>
                    <div className="premium-perk-info">
                      <strong>{perk.name}</strong>
                      <span>{perk.desc}</span>
                    </div>
                  </div>
                ))}
              </div>

              <div className="premium-pricing">
                <div className="premium-price-card">
                  <span className="premium-price-amount">${PREMIUM_PRICE}</span>
                  <span className="premium-price-period">/month</span>
                </div>
                <p className="premium-price-note">Cancel anytime. No long-term commitment.</p>
              </div>

              <div className="premium-revenue-note">
                <span className="premium-revenue-icon">💡</span>
                <p>
                  <strong>Where does $4.99 go?</strong><br />
                  $3.00 → your chosen causes via Every.org (tax-deductible).<br />
                  $1.99 → keeps imprint free, ad-supported, and running for all.
                </p>
              </div>

              <div className="time-donate-actions">
                <button className="btn-continue btn-wide premium-subscribe-btn" disabled={premiumPhase === "processing" || isPremium} onClick={() => {
                  if (isPremium || premiumPhase === "processing") return;
                  setPremiumPhase("processing");
                  // Simulate Stripe/Apple Pay — replace with real payment
                  if (premiumTimerRef.current) clearTimeout(premiumTimerRef.current);
                  premiumTimerRef.current = setTimeout(() => {
                    premiumTimerRef.current = null;
                    setIsPremium(true);
                    setPremiumPhase("active");
                    setTotalPoints((p) => p + 500); // Welcome bonus
                    hapticNotification("Success").catch(() => {});
                  }, 2000);
                }}>
                  {premiumPhase === "processing" ? "Processing…" : <>Subscribe to imprint+ <span className="arrow">→</span></>}
                </button>
                <button className="btn-small btn-small-outline" onClick={() => switchView("dashboard")} style={{ marginTop: "10px", width: "100%" }}>
                  Maybe later
                </button>
              </div>
            </>
          )}

          {premiumPhase === "processing" && (
            <div className="time-donate-complete" style={{ textAlign: "center" }}>
              <div className="direct-processing-spinner" />
              <h3 className="time-donate-complete-title">Setting up your membership…</h3>
              <p className="time-donate-complete-desc">Securely processing payment.</p>
            </div>
          )}

          {premiumPhase === "active" && (
            <div className="time-donate-complete">
              <div className="time-donate-complete-icon">⚡</div>
              <h3 className="time-donate-complete-title">Welcome to imprint+!</h3>
              <p className="time-donate-complete-desc">
                You&apos;re now a premium member. All perks are active.
              </p>

              <div className="time-donate-receipt">
                <div className="receipt-row">
                  <span>Membership</span>
                  <span>imprint+</span>
                </div>
                <div className="receipt-row">
                  <span>Price</span>
                  <span>${PREMIUM_PRICE}/mo</span>
                </div>
                <div className="receipt-row">
                  <span>Monthly cause fund</span>
                  <span style={{ color: "var(--accent)" }}>${PREMIUM_CAUSE_FUND.toFixed(2)}/mo → causes</span>
                </div>
                <div className="receipt-row">
                  <span>Impact Points</span>
                  <span>2× on everything</span>
                </div>
                <div className="receipt-row">
                  <span>Welcome bonus</span>
                  <span>✦ +500 pts</span>
                </div>
              </div>

              <div className="premium-perks" style={{ marginTop: "20px" }}>
                {PREMIUM_PERKS.map((perk) => (
                  <div key={perk.name} className="premium-perk active">
                    <span className="premium-perk-emoji">{perk.emoji}</span>
                    <div className="premium-perk-info">
                      <strong>{perk.name}</strong>
                      <span>{perk.desc}</span>
                    </div>
                    <span className="premium-perk-check">✓</span>
                  </div>
                ))}
              </div>

              <div className="time-donate-actions" style={{ marginTop: "24px" }}>
                <button className="btn-continue btn-wide" onClick={() => switchView("dashboard")}>
                  Start using imprint+ <span className="arrow">→</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ── Account ── */}
      <section className={`view feed-view ${activeView === "account" ? "active" : ""}`} {...(activeView !== "account" ? { inert: true } : {})}>
        <div className="feed-scroll">
          <button className="btn-back" onClick={() => switchView("dashboard")}>
            ← Back to profile
          </button>

          {/* Header — adapts to logged-in vs guest */}
          <div className="account-header">
            {user ? (
              <>
                <div className="account-avatar-large">
                  {user.avatar ? (
                    <img src={user.avatar} alt="" />
                  ) : (
                    <span>{user.name?.charAt(0)?.toUpperCase() || "?"}</span>
                  )}
                </div>
                <h2 className="account-name">{user.name || "Guest"}</h2>
                <p className="account-email">{user.email || ""}</p>
                {user.joinedAt && !isNaN(new Date(user.joinedAt).getTime()) && (
                  <p className="account-joined">Joined {new Date(user.joinedAt).toLocaleDateString("en-US", { month: "long", year: "numeric" })}</p>
                )}
              </>
            ) : (
              <>
                <div className="account-avatar-large" style={{ background: "var(--border)" }}>
                  <span style={{ fontSize: "28px" }}>⚙️</span>
                </div>
                <h2 className="account-name">Settings</h2>
                <p className="account-email" style={{ color: "var(--text-faint)" }}>Sign in to save your data across devices</p>
              </>
            )}
          </div>

          {/* Account / Sign in section */}
          {user ? (
            <>
              {/* Premium status */}
              {isPremium && (
                <div className="account-section">
                  <div className="account-premium-status">
                    <span className="premium-badge-small">⚡ imprint+</span>
                    <span className="account-premium-label">Active member</span>
                  </div>
                  <button className="account-action-btn" onClick={() => { setPremiumPhase("info"); switchView("premium"); }}>Manage subscription</button>
                </div>
              )}
              {!isPremium && (
                <div className="account-section">
                  <button className="premium-cta-small" onClick={() => { setPremiumPhase("info"); switchView("premium"); }}>
                    <span className="premium-badge-small">imprint+</span>
                    <span>Upgrade — $3/mo to causes + 2× points</span>
                  </button>
                </div>
              )}

              {/* Profile section */}
              <div className="account-section">
                <h3 className="account-section-title">Profile</h3>
                <div className="account-field">
                  <label htmlFor="account-name">Display name</label>
                  <input
                    id="account-name"
                    type="text"
                    value={user.name || ""}
                    maxLength={50}
                    onChange={(e) => { const v = e.target.value; if (v.length === 0 || v.trimStart().length > 0) setUser((u) => u ? { ...u, name: v } : u); }}
                    onBlur={(e) => { const trimmed = e.target.value.trim(); if (trimmed.length === 0) { e.target.value = user.name || "User"; setUser((u) => u ? { ...u, name: u.name || "User" } : u); return; } setUser((u) => u ? { ...u, name: trimmed } : u); }}
                    className="account-input"
                  />
                </div>
                <div className="account-field">
                  <label htmlFor="account-email">Email</label>
                  <input id="account-email" type="email" value={user.email || ""} disabled className="account-input disabled" />
                </div>
              </div>
            </>
          ) : (
            <div className="account-section">
              <h3 className="account-section-title">Account</h3>
              <button className="account-action-btn" onClick={() => switchView("auth")} style={{ color: "var(--accent)", fontWeight: 600 }}>
                🔑 Sign in or create account
              </button>
            </div>
          )}

          {/* Preferences */}
          <div className="account-section">
            <h3 className="account-section-title">Preferences</h3>
            <div className="account-toggle-row">
              <div className="account-toggle-info">
                <strong>Push notifications</strong>
                <span>New opportunities and milestone alerts</span>
              </div>
              <button
                className={`account-toggle ${settings.notifications ? "on" : ""}`}
                role="switch"
                aria-checked={settings.notifications}
                onClick={() => setSettings((s) => ({ ...s, notifications: !s.notifications }))}
              >
                <span className="account-toggle-knob" />
              </button>
            </div>
            <div className="account-toggle-row">
              <div className="account-toggle-info">
                <strong>Weekly impact digest</strong>
                <span>Summary of your contributions each week</span>
              </div>
              <button
                className={`account-toggle ${settings.weeklyDigest ? "on" : ""}`}
                role="switch"
                aria-checked={settings.weeklyDigest}
                onClick={() => setSettings((s) => ({ ...s, weeklyDigest: !s.weeklyDigest }))}
              >
                <span className="account-toggle-knob" />
              </button>
            </div>
            <div className="account-toggle-row">
              <div className="account-toggle-info">
                <strong>Public profile</strong>
                <span>Let others see your impact card</span>
              </div>
              <button
                className={`account-toggle ${settings.publicProfile ? "on" : ""}`}
                role="switch"
                aria-checked={settings.publicProfile}
                onClick={() => setSettings((s) => ({ ...s, publicProfile: !s.publicProfile }))}
              >
                <span className="account-toggle-knob" />
              </button>
            </div>
            <div className="account-toggle-row">
              <div className="account-toggle-info">
                <strong>Dark mode</strong>
                <span>Switch to a darker color scheme</span>
              </div>
              {(() => {
                const isDark = settings.darkMode === true || (settings.darkMode === null && systemDark);
                return (
                  <button
                    className={`account-toggle ${isDark ? "on" : ""}`}
                    role="switch"
                    aria-checked={isDark}
                    onClick={() => {
                      const newValue = !isDark;
                      document.documentElement.setAttribute('data-theme', newValue ? 'dark' : 'light');
                      setSettings((s) => ({ ...s, darkMode: newValue }));
                      setStatusBarStyle(newValue ? "Light" : "Dark").catch(() => {});
                    }}
                  >
                    <span className="account-toggle-knob" />
                  </button>
                );
              })()}
            </div>
          </div>

          {/* Data */}
          <div className="account-section">
            <h3 className="account-section-title">Data</h3>
            <button className="account-action-btn" onClick={() => {
              const data = JSON.stringify({ user, quizResults, totalPoints, joinedCards: [...joinedCards], directDonation: directDonationStable, timeDonation: timeDonationStable, offers, isPremium, settings, userLocation }, null, 2);
              const blob = new Blob([data], { type: "application/json" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = "imprint-data.json";
              a.click();
              setTimeout(() => URL.revokeObjectURL(url), 1000);
            }}>Export my data</button>
            {user && <button className="account-action-btn danger" onClick={() => {
              if (window.confirm("Are you sure? This will clear all your data and cannot be undone.")) {
                localStorage.removeItem("imprint_state");
                window.location.reload();
              }
            }}>Delete account</button>}
          </div>

          {/* Logout — only when logged in */}
          {user && (
            <button className="btn-continue btn-wide account-logout" onClick={handleLogout}>
              Log out
            </button>
          )}
        </div>
      </section>

      {/* ── My Impact ── */}
      <section className={`view feed-view ${activeView === "myimpact" ? "active" : ""}`} {...(activeView !== "myimpact" ? { inert: true } : {})}>
        <div className="feed-scroll">
          <button className="btn-back" onClick={() => switchView("dashboard")}>
            ← Back to profile
          </button>

          {(() => {
            const stats = impactStats;
            const unlockedMilestones = milestones.filter((m) => m.unlocked);
            const lockedMilestones = milestones.filter((m) => !m.unlocked);
            return (
              <>
                {/* Shareable card */}
                <div className="impact-card" ref={impactCardRef}>
                  <div className="impact-card-header">
                    <span className="impact-card-logo">imprint</span>
                    <span className="impact-card-label">lifetime impact</span>
                  </div>

                  {arch && (
                    <div className="impact-card-archetype">
                      <span className="impact-card-badge">{arch.badge}</span>
                      <span className="impact-card-archname">{arch.name}</span>
                    </div>
                  )}

                  <div className="impact-card-stats">
                    <div className="impact-card-stat">
                      <span className="impact-card-stat-num">${(stats.dollarsRaised + stats.directDollars).toFixed(2)}</span>
                      <span className="impact-card-stat-label">total given</span>
                    </div>
                    {stats.directDollars > 0 && (
                      <div className="impact-card-stat">
                        <span className="impact-card-stat-num">${stats.directDollars.toFixed(2)}</span>
                        <span className="impact-card-stat-label">donated</span>
                      </div>
                    )}
                    <div className="impact-card-stat">
                      <span className="impact-card-stat-num">{stats.minutesDonated}</span>
                      <span className="impact-card-stat-label">min given</span>
                    </div>
                    <div className="impact-card-stat">
                      <span className="impact-card-stat-num">{totalPoints}</span>
                      <span className="impact-card-stat-label">pts</span>
                    </div>
                  </div>

                  {stats.impactItems.length > 0 && (
                    <div className="impact-card-funded">
                      {stats.impactItems.map((item) => {
                        const pct = Math.round((item.total % 1) * 100);
                        return (
                          <div key={item.id} className="impact-card-funded-item">
                            <span>{item.emoji}</span>
                            <span>
                              {item.completed > 0 ? (
                                <><strong>{item.completed}</strong> {item.unit}{item.completed !== 1 ? "s" : ""}</>
                              ) : (
                                <><strong>{pct}%</strong> to 1 {item.unit}</>
                              )}
                            </span>
                            <span className="impact-card-funded-partner">via {item.partner}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  <div className="impact-card-footer">
                    <span>🌿 find your purpose, fund the change</span>
                  </div>
                </div>

                {/* Share button */}
                <button className="btn-share" onClick={shareImpact}>
                  {shareStatus === "copied" ? "✓ Copied!" : "Share my impact →"}
                </button>

                {/* Milestones */}
                <div className="milestones-section">
                  <h3 className="milestones-title">Milestones</h3>
                  <p className="milestones-subtitle">
                    {unlockedMilestones.length} of {milestones.length} unlocked
                  </p>

                  {unlockedMilestones.length > 0 && (
                    <div className="milestones-grid">
                      {unlockedMilestones.map((m) => (
                        <div key={m.id} className="milestone unlocked">
                          <span className="milestone-emoji">{m.emoji}</span>
                          <div className="milestone-info">
                            <strong>{m.name}</strong>
                            <span>{m.desc}</span>
                          </div>
                          <span className="milestone-check">✓</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {lockedMilestones.length > 0 && (
                    <div className="milestones-grid milestones-locked">
                      {lockedMilestones.map((m) => (
                        <div key={m.id} className="milestone locked">
                          <span className="milestone-emoji">{m.emoji}</span>
                          <div className="milestone-info">
                            <strong>{m.name}</strong>
                            <span>{m.desc}</span>
                          </div>
                          <span className="milestone-lock">🔒</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Tax & Giving Records */}
                {directDonation.history.length > 0 && (
                  <div className="tax-records-section">
                    <h3 className="impact-breakdown-title">Tax &amp; giving records</h3>
                    <p className="tax-records-desc">
                      All donations are processed by Every.org (501(c)(3), EIN {EVERY_ORG.ein}).
                      Official tax receipts are emailed automatically.
                    </p>
                    <button className="btn-tax-receipt btn-wide" onClick={openEveryOrgReceipts}>
                      📋 View all tax receipts on Every.org
                    </button>
                    <button className="btn-tax-receipt btn-tax-receipt-secondary btn-wide" onClick={downloadAnnualSummary} style={{ marginTop: "8px" }}>
                      📥 Download {new Date().getFullYear()} giving summary
                    </button>
                    <div className="tax-records-list">
                      {directDonation.history.slice().reverse().map((d) => {
                        const cause = directDonationCauses.find((c) => c.id === d.causeId);
                        const np = NONPROFIT_PARTNERS[cause?.partner] || {};
                        return (
                          <div key={d.everyOrgChargeId} className="tax-record-row tax-record-row-clickable" role="button" tabIndex={0} onClick={() => openReceiptDetail(d)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openReceiptDetail(d); } }}>
                            <div className="tax-record-info">
                              <strong>{cause?.emoji} ${d.amount.toFixed(2)} → {cause?.partner}</strong>
                              <span>EIN {np.ein} · via Every.org · {new Date(d.date).toLocaleDateString()}</span>
                            </div>
                            <span className="tax-record-arrow">→</span>
                          </div>
                        );
                      })}
                    </div>
                    <div className="everyorg-footer">
                      <span className="everyorg-badge-icon">🌐</span>
                      <span>Donations processed by <strong>Every.org</strong> · 501(c)(3) · EIN {EVERY_ORG.ein}</span>
                    </div>
                  </div>
                )}

                {/* Lifetime breakdown */}
                {offers.length > 0 && (
                  <div className="impact-breakdown">
                    <h3 className="impact-breakdown-title">Donations offered</h3>
                    {offers.map((o) => (
                      <div key={o.id || o.category} className="impact-breakdown-row">
                        <span>✦ {o.category}</span>
                        <span>${(o.estimatedValue || 0).toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            );
          })()}
        </div>
      </section>

      {/* ── Receipt Detail ── */}
      <section className={`view feed-view ${activeView === "receipt" ? "active" : ""}`} {...(activeView !== "receipt" ? { inert: true } : {})}>
        <div className="feed-scroll">
          <button className="btn-back" onClick={() => switchView(receiptFrom)}>
            ← Back
          </button>

          {receiptDetail && (() => {
            const cause = directDonationCauses.find((c) => c.id === receiptDetail.causeId);
            const np = NONPROFIT_PARTNERS[cause?.partner] || {};
            const ptsEarned = receiptDetail.pointsEarned ?? Math.floor(receiptDetail.amount * 50);
            return (
              <>
                <div className="receipt-detail-header">
                  <div className="receipt-detail-icon">{cause?.emoji || "💚"}</div>
                  <h2 className="receipt-detail-title">${(receiptDetail.amount ?? 0).toFixed(2)}</h2>
                  <p className="receipt-detail-subtitle">
                    to <strong>{cause?.partner}</strong> via Every.org
                  </p>
                  <span className="receipt-detail-date">{!isNaN(new Date(receiptDetail.date).getTime()) ? new Date(receiptDetail.date).toLocaleDateString() : "Unknown date"}</span>
                </div>

                <div className="receipt-detail-card">
                  <div className="receipt-detail-section-title">Donation details</div>
                  <div className="time-donate-receipt">
                    <div className="receipt-row">
                      <span>Cause</span>
                      <span>{cause?.emoji} {cause?.name}</span>
                    </div>
                    <div className="receipt-row">
                      <span>Partner</span>
                      <span>{cause?.partner}</span>
                    </div>
                    <div className="receipt-row">
                      <span>Amount</span>
                      <span><strong>${receiptDetail.amount.toFixed(2)}</strong></span>
                    </div>
                    <div className="receipt-row">
                      <span>Platform fees</span>
                      <span style={{ color: "var(--accent)" }}>$0.00 (0%)</span>
                    </div>
                    <div className="receipt-row">
                      <span>Impact</span>
                      <span>{receiptDetail.unitsGenerated?.toLocaleString()} {cause?.unit}{receiptDetail.unitsGenerated !== 1 ? "s" : ""}</span>
                    </div>
                    <div className="receipt-row">
                      <span>Points earned</span>
                      <span>✦ +{ptsEarned} pts</span>
                    </div>
                  </div>
                </div>

                <div className="receipt-detail-card">
                  <div className="receipt-detail-section-title">Tax information</div>
                  <div className="time-donate-receipt">
                    <div className="receipt-row">
                      <span>Organization</span>
                      <span>{cause?.partner}</span>
                    </div>
                    <div className="receipt-row">
                      <span>EIN</span>
                      <span className="receipt-ein">{np.ein}</span>
                    </div>
                    <div className="receipt-row">
                      <span>Status</span>
                      <span>{np.status}</span>
                    </div>
                    <div className="receipt-row">
                      <span>Processed by</span>
                      <span>Every.org</span>
                    </div>
                    <div className="receipt-row">
                      <span>Every.org EIN</span>
                      <span className="receipt-ein">{EVERY_ORG.ein}</span>
                    </div>
                  </div>
                  <div className="receipt-detail-tax-note">
                    <span>📋</span>
                    <span>
                      No goods or services were provided in exchange for this donation.
                      This contribution is tax-deductible under IRC Section 170.
                    </span>
                  </div>
                </div>

                <div className="receipt-detail-actions">
                  <button className="btn-tax-receipt btn-wide" onClick={openEveryOrgReceipts}>
                    📋 View official receipt on Every.org
                  </button>
                  <button className="btn-tax-receipt btn-tax-receipt-secondary btn-wide" onClick={() => downloadReceipt(receiptDetail)} style={{ marginTop: "8px" }}>
                    📥 Download summary
                  </button>
                </div>

                <div className="everyorg-footer" style={{ marginTop: "24px" }}>
                  <span className="everyorg-badge-icon">🌐</span>
                  <span>Official IRS tax receipt emailed by <strong>Every.org</strong></span>
                </div>
              </>
            );
          })()}
        </div>
      </section>

      {/* ── Feed ── */}
      <section className={`view feed-view ${activeView === "feed" ? "active" : ""}`} {...(activeView !== "feed" ? { inert: true } : {})}>
        <div className="feed-scroll">
          <button className="btn-back" onClick={() => switchView("dashboard")}>
            ← Back to profile
          </button>

          <div className="feed-header">
            {arch && <div className="feed-archetype-badge">{arch.badge}</div>}
            <h2 className="feed-title">
              <span className="feed-location-wrap">
                Make a difference in{" "}
                <span
                  key={locationKey}
                  className="place"
                  contentEditable
                  suppressContentEditableWarning
                  spellCheck={false}
                  role="textbox"
                  aria-label="Your location"
                  onBlur={(e) => {
                    const text = (e.target.textContent || "").trim().slice(0, 50);
                    setUserLocation(text || "your neighborhood");
                    e.target.textContent = text || "your neighborhood";
                  }}
                  onPaste={(e) => {
                    e.preventDefault();
                    const text = (e.clipboardData.getData("text/plain") || "").trim().slice(0, 50);
                    const sel = window.getSelection();
                    if (sel.rangeCount) {
                      const range = sel.getRangeAt(0);
                      range.deleteContents();
                      range.insertNode(document.createTextNode(text));
                      range.collapse(false);
                    }
                    setUserLocation(e.target.textContent.trim().slice(0, 50) || "your neighborhood");
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    const text = (e.dataTransfer.getData("text/plain") || "").trim().slice(0, 50);
                    if (text) {
                      const sel = window.getSelection();
                      if (sel.rangeCount) {
                        const range = sel.getRangeAt(0);
                        range.deleteContents();
                        range.insertNode(document.createTextNode(text));
                        range.collapse(false);
                      }
                      setUserLocation(e.target.textContent.trim().slice(0, 50) || "your neighborhood");
                    }
                  }}
                  onInput={(e) => {
                    // Catch-all sanitizer for IME composition and browser-inserted markup
                    // Only fire when actual child elements (tags) are present, not just entity encoding mismatches
                    const text = (e.target.textContent || "").slice(0, 50);
                    if (e.target.childElementCount > 0 || text.length > 50) {
                      e.target.textContent = text;
                      // Move cursor to end
                      const sel = window.getSelection();
                      if (sel.rangeCount) { const range = sel.getRangeAt(0); range.selectNodeContents(e.target); range.collapse(false); }
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") { e.preventDefault(); e.target.blur(); return; }
                    // Block character input at limit (allow navigation/deletion keys)
                    if (e.target.textContent.length >= 50 && !["Backspace","Delete","ArrowLeft","ArrowRight","ArrowUp","ArrowDown","Home","End"].includes(e.key) && !e.ctrlKey && !e.metaKey && e.key.length === 1) {
                      e.preventDefault();
                    }
                  }}
                >
                  {userLocation}
                </span>
                {(locationStatus === "idle" || locationStatus === "denied") && (
                  <button className="feed-location-edit" onClick={() => { if (locationStatus === "denied") setLocationStatus("idle"); requestUserLocation(); }} title="Use my location">📍 Detect</button>
                )}
              </span>
            </h2>
            <p className="feed-subtitle">Evidence-based activities matched to your purpose</p>
          </div>

          {opps.length === 0 && (
            <div style={{
              textAlign: "center",
              padding: "40px 20px",
              color: "var(--text-mid)",
            }}>
              <div style={{ fontSize: "40px", marginBottom: "12px" }}>🧭</div>
              <p style={{ fontSize: "15px", lineHeight: 1.6, marginBottom: "16px" }}>
                Complete the Purpose quiz to unlock opportunities matched to your archetype.
              </p>
              <button
                className="btn-small btn-small-accent"
                onClick={() => startQuiz("purpose")}
              >
                Take the quiz
              </button>
            </div>
          )}
          <div className="feed-cards">
            {opps.map((c, i) => (
              <div
                key={c.title}
                className={`card ${cardsVisible ? "visible" : ""}`}
                style={{ transitionDelay: `${i * 100}ms` }}
              >
                <div className="card-accent" aria-hidden="true" style={{ background: catColors[c.cat] }} />
                <div className="card-body">
                  <p className="card-tag">{c.tag}</p>
                  <h3 className="card-title">{c.title}</h3>
                  <p className="card-desc">{c.desc}</p>
                  <div className="card-evidence">
                    <strong>Why this works: </strong>
                    {evidence[c.cat]}
                  </div>
                  <div className="card-meta">
                    <span>📍 {c.dist}</span>
                    <span>🕐 {c.sched}</span>
                    <span>by {c.by}</span>
                  </div>
                  <div className="card-footer">
                    <div className="card-points">✦ +{isPremium ? 100 : 50} pts per session</div>
                    <div className="card-joined">
                      <span className="count">
                        {joinedCards.has(c.title) ? c.joined + 1 : c.joined}
                      </span>{" "}
                      people joined
                    </div>
                    <button
                      className={`btn-join ${joinedCards.has(c.title) ? "joined" : ""}`}
                      onClick={() => handleJoin(c.title)}
                    >
                      {joinedCards.has(c.title) ? "You're in ✓" : "Count me in"}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Rewards */}
          <div className="rewards-section">
            <h3 className="rewards-heading">Redeem your impact</h3>
            <p className="rewards-sub">
              Earn points for showing up. Spend them on experiences that keep you connected.
            </p>
            <div className="rewards-grid">
              {rewards.map((r) => (
                <div key={r.name} className="reward-card">
                  <div className="reward-emoji">{r.emoji}</div>
                  <div className="reward-name">{r.name}</div>
                  <div className="reward-cost">{r.cost}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="feed-impact">
            <div className="impact-stat">
              <div className="impact-number">{Object.keys(quizResults).length}</div>
              <div className="impact-label">{Object.keys(quizResults).length === 1 ? "quiz" : "quizzes"} completed</div>
            </div>
            <div className="impact-stat">
              <div className="impact-number">{timeDonation.totalAdsWatched}</div>
              <div className="impact-label">{timeDonation.totalAdsWatched === 1 ? "minute" : "minutes"} given</div>
            </div>
            <div className="impact-stat">
              <div className="impact-number">{joinedCards.size}</div>
              <div className="impact-label">{joinedCards.size === 1 ? "activity" : "activities"} joined</div>
            </div>
          </div>

          <div className="feed-closing">
            <p className="feed-closing-text">
              Your purpose isn&apos;t something you find. It&apos;s something you build,
              one act at a time.
            </p>
          </div>
        </div>
      </section>
      </main>
    </div>
  );
}
