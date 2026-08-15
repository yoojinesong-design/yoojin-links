# imprint

**Find your purpose. Make your mark. Earn your impact.**

An app that helps people discover what gives them meaning — through evidence-based questions — then connects them with real opportunities to make a difference in the places they love. Earn impact points for showing up. Redeem them for experiences that keep you connected.

## The idea

Can an app change the world? What if the cure for loneliness isn't being found — it's finding someone else?

**imprint** is built on three layers:

1. **Purpose Discovery** — A series of reflective questions that uncover your purpose archetype (Connector, Builder, Guide, or Solver). Not personality quiz fluff — real questions grounded in what research says about meaning and motivation.

2. **Evidence-Based Matching** — An algorithm that matches you with local opportunities based on what's scientifically proven to reduce loneliness and increase wellbeing. Every recommendation comes with the research backing it.

3. **Impact Points** — Earn points for every activity you complete. Redeem them for real experiences — concert tickets, sports games, theater, local café credit — inspired by the [Vettix](https://vettix.org) model. The flywheel: do good → feel good → get experiences → stay connected.

## Purpose Archetypes

- **The Connector** — You see people. Really see them. Your superpower is making others feel less alone.
- **The Builder** — You look at what's broken and see what it could become. Communities need your hands and vision.
- **The Guide** — You light the path for others. Teaching, mentoring, believing in potential before anyone else does.
- **The Solver** — You can't unsee inefficiency. You fix systems so organizations can focus on their mission.

## Tech Stack

- [Next.js](https://nextjs.org) 16 (App Router)
- React 19
- CSS Custom Properties (light/dark theme support)
- No external dependencies beyond React + Next.js

## Getting Started

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Structure

```
app/
├── page.js                    # Entry point
├── layout.js                  # Root layout + metadata
├── globals.css                # Design tokens, components, themes
├── components/
│   └── ImprintApp.js          # Main interactive app (client component)
└── data/
    └── content.js             # Questions, archetypes, opportunities
```

## Nonprofit Model

This project is designed as a nonprofit. Revenue comes from:
- Partnerships with experience providers (venues, teams, businesses)
- Grants from foundations focused on loneliness and civic engagement
- Corporate social responsibility sponsors

No user data is sold. No attention is monetized. The algorithm is built to make you feel more valued and provide more value to society in return.

## License

MIT
