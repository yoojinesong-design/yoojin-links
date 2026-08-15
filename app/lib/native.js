"use client";

/**
 * Native bridge — wraps Capacitor plugins with web fallbacks.
 * When running inside a Capacitor native shell, uses native APIs.
 * Otherwise falls back to standard Web APIs.
 */

/** Check if we're running inside a Capacitor native app */
export function isNative() {
  if (typeof window === "undefined") return false;
  return !!(window.Capacitor && window.Capacitor.isNativePlatform());
}

/** Get the platform: 'ios' | 'android' | 'web' */
export function getPlatform() {
  if (!isNative()) return "web";
  return window.Capacitor.getPlatform();
}

/** Lazy-load a Capacitor plugin (returns null on web) */
async function getPlugin(name) {
  if (!isNative()) return null;
  try {
    switch (name) {
      case "Geolocation": {
        const mod = await import("@capacitor/geolocation");
        return mod.Geolocation;
      }
      case "Haptics": {
        const mod = await import("@capacitor/haptics");
        return mod.Haptics;
      }
      case "Share": {
        const mod = await import("@capacitor/share");
        return mod.Share;
      }
      case "StatusBar": {
        const mod = await import("@capacitor/status-bar");
        return mod.StatusBar;
      }
      case "SplashScreen": {
        const mod = await import("@capacitor/splash-screen");
        return mod.SplashScreen;
      }
      case "Preferences": {
        const mod = await import("@capacitor/preferences");
        return mod.Preferences;
      }
      case "App": {
        const mod = await import("@capacitor/app");
        return mod.App;
      }
      default:
        return null;
    }
  } catch {
    return null;
  }
}

/* ── Geolocation ── */

export async function getCurrentPosition() {
  const plugin = await getPlugin("Geolocation");
  if (plugin) {
    const result = await plugin.getCurrentPosition({
      enableHighAccuracy: true,
      timeout: 10000,
    });
    return {
      latitude: result.coords.latitude,
      longitude: result.coords.longitude,
      accuracy: result.coords.accuracy,
    };
  }
  // Web fallback
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation not supported"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        resolve({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        }),
      (err) => reject(err),
      { enableHighAccuracy: true, timeout: 10000 }
    );
  });
}

export async function checkLocationPermission() {
  const plugin = await getPlugin("Geolocation");
  if (plugin) {
    const status = await plugin.checkPermissions();
    return status.location; // 'prompt' | 'granted' | 'denied'
  }
  // Web fallback
  if (navigator.permissions) {
    const result = await navigator.permissions.query({ name: "geolocation" });
    return result.state; // 'prompt' | 'granted' | 'denied'
  }
  return "prompt";
}

export async function requestLocationPermission() {
  const plugin = await getPlugin("Geolocation");
  if (plugin) {
    const status = await plugin.requestPermissions();
    return status.location;
  }
  return "prompt"; // Web handles via getCurrentPosition
}

/* ── Haptics ── */

export async function hapticImpact(style = "Medium") {
  const plugin = await getPlugin("Haptics");
  if (plugin) {
    await plugin.impact({ style });
  }
  // No web fallback for haptics
}

export async function hapticNotification(type = "Success") {
  const plugin = await getPlugin("Haptics");
  if (plugin) {
    await plugin.notification({ type });
  }
}

/* ── Share ── */

export async function shareContent({ title, text, url }) {
  const plugin = await getPlugin("Share");
  if (plugin) {
    await plugin.share({ title, text, url });
    return true;
  }
  // Web fallback
  if (navigator.share) {
    await navigator.share({ title, text, url });
    return true;
  }
  // Clipboard fallback
  if (navigator.clipboard) {
    await navigator.clipboard.writeText(url || text);
    return "clipboard";
  }
  return false;
}

/* ── Status Bar ── */

export async function setStatusBarStyle(style = "Dark") {
  const plugin = await getPlugin("StatusBar");
  if (plugin) {
    await plugin.setStyle({ style });
  }
}

export async function hideStatusBar() {
  const plugin = await getPlugin("StatusBar");
  if (plugin) {
    await plugin.hide();
  }
}

/* ── Splash Screen ── */

export async function hideSplashScreen() {
  const plugin = await getPlugin("SplashScreen");
  if (plugin) {
    await plugin.hide({ fadeOutDuration: 300 });
  }
}

/* ── Persistent Storage (Preferences) ── */

export async function setPreference(key, value) {
  const plugin = await getPlugin("Preferences");
  if (plugin) {
    await plugin.set({ key, value: JSON.stringify(value) });
    return;
  }
  // Web fallback
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {}
}

export async function getPreference(key) {
  const plugin = await getPlugin("Preferences");
  if (plugin) {
    const result = await plugin.get({ key });
    return result.value ? JSON.parse(result.value) : null;
  }
  // Web fallback
  try {
    const val = localStorage.getItem(key);
    return val ? JSON.parse(val) : null;
  } catch {
    return null;
  }
}

export async function removePreference(key) {
  const plugin = await getPlugin("Preferences");
  if (plugin) {
    await plugin.remove({ key });
    return;
  }
  try {
    localStorage.removeItem(key);
  } catch {}
}

/* ── App lifecycle ── */

export async function onBackButton(callback) {
  const plugin = await getPlugin("App");
  if (plugin) {
    const handle = await plugin.addListener("backButton", callback);
    return handle; // call handle.remove() to unsubscribe
  }
  return null;
}

export async function exitApp() {
  const plugin = await getPlugin("App");
  if (plugin) {
    await plugin.exitApp();
  }
}

/* ── Safe area insets ── */

export function getSafeAreaInsets() {
  if (typeof window === "undefined") return { top: 0, bottom: 0, left: 0, right: 0 };
  const style = getComputedStyle(document.documentElement);
  return {
    top: parseInt(style.getPropertyValue("--sat") || "0") || 0,
    bottom: parseInt(style.getPropertyValue("--sab") || "0") || 0,
    left: parseInt(style.getPropertyValue("--sal") || "0") || 0,
    right: parseInt(style.getPropertyValue("--sar") || "0") || 0,
  };
}
