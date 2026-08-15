# imprint — App Store Listing Guide

## App Name
**imprint**

## Subtitle (30 chars max)
Find your purpose, make your mark

## Category
- **Primary:** Lifestyle
- **Secondary:** Social Networking

---

## App Store Description (4000 chars max)

### Short Description (Google Play, 80 chars)
Discover your purpose, find volunteer opportunities, and make a real difference.

### Full Description

**Find your purpose. Make your mark.**

imprint helps you discover what drives you and connects you with real opportunities to make a difference in your community.

**🧭 DISCOVER YOUR PURPOSE**
Take our evidence-based purpose quiz to uncover your unique archetype:
• Connector — You build bridges between people and ideas
• Builder — You create lasting systems and solutions
• Guide — You illuminate paths for others to follow
• Solver — You untangle complex challenges others avoid

Your personalized radar chart reveals your strengths across purpose dimensions, giving you a clear picture of how you can create the most impact.

**🌍 FIND OPPORTUNITIES NEAR YOU**
Browse curated volunteer opportunities and social impact causes in your area. Filter by your interests, skills, and availability. Every opportunity is vetted and aligned with your purpose archetype.

**💛 DONATE WITH IMPACT**
Make tax-deductible donations to verified nonprofits through our partner Every.org (501(c)(3), EIN 61-1913297). 100% of your donation goes directly to the cause. Track every dollar and see your cumulative impact grow.

**📊 TRACK YOUR IMPACT**
Your personal dashboard shows:
• Total impact points earned
• Donation history with tax receipts
• Volunteer hours logged
• Milestone achievements unlocked
• Community leaderboard ranking

**🏆 EARN & REDEEM**
Earn impact points through donations and volunteering. Hit milestones to unlock badges and experiences. Every action counts toward your legacy.

**✨ FEATURES**
• Purpose discovery quiz with 4 archetypes
• Interactive radar chart visualization
• Location-based opportunity matching
• Tax-deductible donations via Every.org
• NFC/QR verification for volunteer check-ins
• Impact dashboard with detailed analytics
• Dark and light theme support
• Works offline with PWA support

Start your journey today. Your purpose is waiting.

---

## Keywords (100 chars, comma-separated)
purpose,volunteer,donate,nonprofit,social impact,community,charity,giving,cause,archetype

## Privacy Policy URL
https://imprint-yoojinesong-3887s-projects.vercel.app/privacy

## Terms of Service URL
https://imprint-yoojinesong-3887s-projects.vercel.app/terms

## Support URL / Contact
yoojinesong@gmail.com

---

## Screenshots Needed

### iPhone (6.7" — iPhone 15 Pro Max)
1. **Purpose Quiz** — A question being answered with the warm, inviting UI
2. **Archetype Reveal** — The dramatic reveal showing the user's archetype with canvas emblem
3. **Dashboard** — Impact dashboard showing points, donations, and radar chart
4. **Opportunities** — List of nearby volunteer opportunities with location
5. **Donation Flow** — Making a donation with the Every.org integration

### iPad (12.9" — iPad Pro)
Same 5 screens, landscape or portrait

### Android (Phone)
Same 5 screens

---

## Age Rating
- **Apple:** 4+ (no objectionable content)
- **Google Play:** Everyone

## App Review Notes (for Apple)
- The app uses location services to show nearby volunteer opportunities.
- Donations are processed through Every.org (external link), not in-app purchases.
- No login is required to browse; account creation is optional for tracking impact.
- Test account: Not required — the app works without authentication for basic features.

---

## Build Checklist

### Before Submitting to App Store:
- [ ] App icons generated for all required sizes (already in `/public/icons/`)
- [ ] Splash screens created (already in `/public/icons/`)
- [ ] Privacy Policy page deployed (/privacy)
- [ ] Terms of Service page deployed (/terms)
- [ ] Screenshots captured on required device sizes
- [ ] App tested on physical iOS device
- [ ] Bundle ID registered: `com.imprint.app`
- [ ] App Store Connect listing created

### Before Submitting to Google Play:
- [ ] App icons and feature graphic (1024x500) created
- [ ] Privacy Policy page deployed (/privacy)
- [ ] Screenshots captured (phone + 7" + 10" tablet)
- [ ] App tested on physical Android device
- [ ] Signed AAB (Android App Bundle) generated
- [ ] Play Console listing created
- [ ] 20 testers recruited for closed testing (14-day requirement for new accounts)

---

## Capacitor Build Commands

### iOS
```bash
npm run build:mobile        # Build Next.js + sync to Capacitor
npx cap open ios            # Open in Xcode
# In Xcode: Product → Archive → Distribute to App Store
```

### Android
```bash
npm run build:mobile        # Build Next.js + sync to Capacitor
npx cap open android        # Open in Android Studio
# In Android Studio: Build → Generate Signed Bundle
```
