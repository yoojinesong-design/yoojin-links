import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.imprint.app",
  appName: "imprint",
  webDir: "out",
  server: {
    // Allow loading from file:// in production
    androidScheme: "https",
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 1200,
      launchAutoHide: true,
      backgroundColor: "#0A0A0C",
      showSpinner: false,
      launchFadeOutDuration: 300,
    },
    StatusBar: {
      style: "DARK",
      backgroundColor: "#0A0A0C",
    },
    Geolocation: {
      // iOS permission descriptions
      NSLocationWhenInUseUsageDescription:
        "imprint uses your location to show volunteer opportunities and causes near you.",
    },
  },
  ios: {
    contentInset: "automatic",
    allowsLinkPreview: false,
    backgroundColor: "#0A0A0C",
    preferredContentMode: "mobile",
  },
  android: {
    backgroundColor: "#0A0A0C",
    allowMixedContent: false,
  },
};

export default config;
