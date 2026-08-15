# imprint — App Store Deployment Guide

## Architecture

```
yoojin-links/
├── app/                    # Next.js React app (source)
│   ├── components/         # ImprintApp, RadarChart, etc.
│   ├── lib/native.js       # Capacitor ↔ Web bridge
│   └── globals.css         # Styles with safe-area support
├── out/                    # Static export (generated)
├── ios/                    # Xcode project (Capacitor)
├── android/                # Android Studio project (Capacitor)
├── public/
│   ├── icons/              # App icons (72–1024px) + splash screens
│   ├── manifest.json       # PWA manifest
│   └── sw.js               # Service worker for offline
├── capacitor.config.ts     # Capacitor configuration
└── DEPLOY.md               # This file
```

The app uses **Capacitor** to wrap the Next.js web app in native iOS and Android shells. The web app is exported as a static site (`output: "export"` in `next.config.js`) and served from the native WebView.

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Node.js | ≥ 18 | For building the web app |
| Xcode | ≥ 15 | For iOS builds (Mac only) |
| Android Studio | ≥ 2024 | For Android builds |
| CocoaPods | ≥ 1.14 | iOS dependency manager |
| Apple Developer Account | — | $99/year for App Store |
| Google Play Console | — | $25 one-time for Play Store |

---

## Quick Start

### 1. Install Dependencies

```bash
npm install
```

### 2. Build & Sync

```bash
# Build the web app + sync to native projects
npm run build:mobile
```

### 3. Open in IDE

```bash
# iOS (opens Xcode)
npm run cap:ios

# Android (opens Android Studio)
npm run cap:android
```

---

## iOS Deployment

### Development Build

```bash
npm run build:mobile
npm run cap:run:ios    # Run on connected iPhone or Simulator
```

### App Store Submission

1. **Open Xcode**: `npm run cap:ios`

2. **Set Bundle ID**: `com.imprint.app` (or your own)
   - Xcode → Target → General → Bundle Identifier

3. **Set Version**: 1.0.0 (Build 1)

4. **Signing**:
   - Xcode → Target → Signing & Capabilities
   - Select your Apple Developer Team
   - Enable "Automatically manage signing"

5. **App Icons**:
   - Icons are pre-generated in `public/icons/`
   - Copy `icon-1024.png` to Xcode's Asset Catalog (AppIcon set)
   - Or use a tool like [AppIcon Generator](https://appicon.co/) with `icon-1024.png`

6. **Archive & Upload**:
   - Product → Archive
   - Distribute App → App Store Connect
   - Upload

7. **App Store Connect**:
   - Go to [appstoreconnect.apple.com](https://appstoreconnect.apple.com)
   - Create new app → Fill in metadata:
     - **Name**: imprint
     - **Subtitle**: find your purpose, make your mark
     - **Category**: Social Impact / Lifestyle
     - **Description**: (see below)
     - **Screenshots**: Take from Simulator (6.7", 6.5", 5.5")
     - **Privacy Policy URL**: Required
   - Submit for Review

### iOS Capabilities (already configured)

- ✅ Location (When In Use) — for nearby opportunities
- ✅ Haptic feedback — for UI interactions
- ✅ Share sheet — native sharing
- ✅ Safe area insets — notch/Dynamic Island support
- ✅ Portrait lock
- ✅ No encryption declaration (`ITSAppUsesNonExemptEncryption: false`)

---

## Android Deployment

### Development Build

```bash
npm run build:mobile
npm run cap:run:android    # Run on connected device or Emulator
```

### Google Play Store Submission

1. **Open Android Studio**: `npm run cap:android`

2. **App Icons**:
   - Replace files in `android/app/src/main/res/mipmap-*/`
   - Use [Android Asset Studio](https://romannurik.github.io/AndroidAssetStudio/) with `icon-1024.png`
   - Or use Android Studio → Right-click `res` → New → Image Asset

3. **Build Release APK / AAB**:
   ```bash
   cd android
   ./gradlew bundleRelease    # Generates AAB for Play Store
   # or
   ./gradlew assembleRelease  # Generates APK for sideloading
   ```

4. **Sign the Release**:
   - Create a keystore:
     ```bash
     keytool -genkey -v -keystore imprint-release.jks \
       -keyalg RSA -keysize 2048 -validity 10000 \
       -alias imprint
     ```
   - Add to `android/app/build.gradle` or use Android Studio signing config

5. **Google Play Console**:
   - Go to [play.google.com/console](https://play.google.com/console)
   - Create app → Fill in:
     - **App name**: imprint
     - **Short description**: Find your purpose, make your mark
     - **Category**: Social
     - **Content rating**: Everyone
   - Upload AAB → Review → Publish

### Android Permissions (already configured)

- ✅ `INTERNET` — for reverse geocoding
- ✅ `ACCESS_FINE_LOCATION` — GPS for nearby opportunities
- ✅ `ACCESS_COARSE_LOCATION` — network location fallback
- ✅ `VIBRATE` — haptic feedback
- ✅ Portrait lock

---

## PWA (Web App)

The app also works as an installable Progressive Web App:

- **manifest.json** — App name, icons, theme color
- **sw.js** — Service worker for offline caching
- **Apple meta tags** — iOS home screen support with splash screens

Users can "Add to Home Screen" from Safari or Chrome without going through an app store.

To deploy as a web app:
```bash
npm run build
# Deploy the `out/` folder to Vercel, Netlify, or any static host
```

---

## App Store Listing Copy

### Name
**imprint**

### Subtitle
Find your purpose, make your mark

### Description
**Discover what gives you purpose — then act on it.**

imprint helps you understand your values through a quick, evidence-based quiz, then connects you with real volunteer opportunities, donations, and social impact causes in your area.

**How it works:**
🔍 Take the Purpose Quiz — 5 questions across 4 dimensions to discover your archetype
📍 Find local opportunities — volunteer, donate, or offer your skills nearby
⏱ Watch & Give — watch a 60-second ad to fund meals, trees, books, or clean water
📊 Track your impact — see your donations, time given, and milestones earned
🏅 Earn rewards — unlock achievements and redeem points for local experiences

**Your impact is real:**
• 7 ads = 1 meal (via Feeding America)
• 67 ads = 1 tree planted (via One Tree Planted)
• 34 ads = 1 book for a child (via Books for Africa)
• 2 ads = 1 liter of clean water (via charity: water)

No cost to you. Every second counts.

### Keywords
purpose, volunteer, social impact, donate, community, nonprofit, charity, local, give back, impact

### Category
Primary: Social Networking
Secondary: Lifestyle

---

## Environment Variables

No environment variables are required. The app is fully client-side.

---

## Updating the App

After making changes to the web app:

```bash
# Rebuild and sync
npm run build:mobile

# Test on device
npm run cap:run:ios      # or cap:run:android

# When ready, archive in Xcode / build in Android Studio
```

---

## Troubleshooting

**"Module not found" errors on build:**
```bash
npm install
npm run build
```

**Capacitor sync fails:**
```bash
npx cap sync --force
```

**iOS signing issues:**
- Ensure you have a valid Apple Developer account
- Check Xcode → Preferences → Accounts

**Android build fails:**
- Ensure `JAVA_HOME` is set
- Update Gradle: `cd android && ./gradlew wrapper --gradle-version 8.6`

**Icons not showing on device:**
- Run `npx cap sync` again after changing icons
- For iOS: update the Asset Catalog manually in Xcode
- For Android: use Android Studio's Image Asset tool
