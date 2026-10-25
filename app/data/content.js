export const quizCategories = [
  {
    id: "purpose",
    name: "Purpose",
    icon: "✦",
    description: "What drives you to make a difference?",
    dimensions: [
      { key: "connector", label: "Connector" },
      { key: "builder", label: "Builder" },
      { key: "guide", label: "Guide" },
      { key: "solver", label: "Solver" },
    ],
    questions: [
      {
        text: "You walk into a room full of strangers. What do you notice first?",
        options: [
          { text: "The person sitting alone by the wall", type: "connector" },
          { text: "The room itself — what could be rearranged to make it work better", type: "builder" },
          { text: "The youngest person and whether anyone's paying attention to them", type: "guide" },
          { text: "What's not working — the bad acoustics, the confusing layout", type: "solver" },
        ],
      },
      {
        text: "A friend cancels plans last minute. You suddenly have a free Saturday. What pulls you?",
        options: [
          { text: "Calling someone I haven't checked in on in a while", type: "connector" },
          { text: "Finally starting that project I've been sketching in my head", type: "builder" },
          { text: "Dropping by to help that kid who's been struggling with math", type: "guide" },
          { text: "Diving into a problem I've been turning over in my mind", type: "solver" },
        ],
      },
      {
        text: "You overhear someone say: \"Nobody cares.\" What's your gut reaction?",
        options: [
          { text: "I want to sit next to them and prove them wrong", type: "connector" },
          { text: "I want to build something that shows people do care", type: "builder" },
          { text: "I want to find out who failed them and what they needed", type: "guide" },
          { text: "I want to understand what system let them fall through the cracks", type: "solver" },
        ],
      },
      {
        text: "You're telling a story about your proudest moment. What's it about?",
        options: [
          { text: "A time I made someone feel truly seen when no one else did", type: "connector" },
          { text: "Something I created from nothing — and people are still using it", type: "builder" },
          { text: "Someone I believed in who went further than they ever thought possible", type: "guide" },
          { text: "A problem everyone said couldn't be solved — until I solved it", type: "solver" },
        ],
      },
      {
        text: "If you had to leave one thing behind for your community, what would it be?",
        options: [
          { text: "A tradition that brings people together every year", type: "connector" },
          { text: "A place that will still be standing in 50 years", type: "builder" },
          { text: "A person I mentored who now mentors others", type: "guide" },
          { text: "A system so well-designed it runs itself", type: "solver" },
        ],
      },
    ],
  },
  {
    id: "wellbeing",
    name: "Wellbeing",
    icon: "◈",
    description: "How connected do you feel right now?",
    dimensions: [
      { key: "social", label: "Social" },
      { key: "emotional", label: "Emotional" },
      { key: "belonging", label: "Belonging" },
      { key: "drive", label: "Drive" },
    ],
    questions: [
      {
        text: "It's 10pm and you feel restless. What do you reach for?",
        options: [
          { text: "My phone — to call someone and talk about nothing important", type: "social" },
          { text: "My journal — something's been stirring and I need to name it", type: "emotional" },
          { text: "My shoes — a walk through the neighborhood always settles me", type: "belonging" },
          { text: "My laptop — I have an idea I can't let go of", type: "drive" },
        ],
      },
      {
        text: "Think of a day last month that felt really good. What made it good?",
        options: [
          { text: "I laughed hard with someone and felt completely myself", type: "social" },
          { text: "I had a quiet moment where everything just made sense", type: "emotional" },
          { text: "I ran into familiar faces and felt like I was exactly where I belong", type: "belonging" },
          { text: "I finished something meaningful and felt the momentum carry me", type: "drive" },
        ],
      },
      {
        text: "You're moving to a new city. What's the first thing you do?",
        options: [
          { text: "Find my people — a group, a class, anywhere I can meet someone real", type: "social" },
          { text: "Set up my space so it feels like me — the right corners, the right light", type: "emotional" },
          { text: "Explore the neighborhood — the coffee shop, the park, the regulars", type: "belonging" },
          { text: "Find a project to pour myself into right away", type: "drive" },
        ],
      },
      {
        text: "When life gets heavy, what's the voice in your head?",
        options: [
          { text: "\"I need to talk to someone who understands\"", type: "social" },
          { text: "\"I need to slow down and figure out what I'm actually feeling\"", type: "emotional" },
          { text: "\"I need to go somewhere that feels like home\"", type: "belonging" },
          { text: "\"I need to do something — anything — that moves me forward\"", type: "drive" },
        ],
      },
      {
        text: "If you could bottle one feeling and keep it forever, which one?",
        options: [
          { text: "That warmth when someone really knows you", type: "social" },
          { text: "That stillness when you finally understand yourself", type: "emotional" },
          { text: "That comfort of walking into a room where you belong", type: "belonging" },
          { text: "That fire when you know exactly what you're here to do", type: "drive" },
        ],
      },
    ],
  },
  {
    id: "skills",
    name: "Skills",
    icon: "◆",
    description: "What can you uniquely contribute?",
    dimensions: [
      { key: "communication", label: "Communication" },
      { key: "organization", label: "Organization" },
      { key: "creating", label: "Creating" },
      { key: "analysis", label: "Analysis" },
    ],
    questions: [
      {
        text: "You're helping a friend start a small business. What do you naturally take over?",
        options: [
          { text: "Writing the pitch — I know how to tell their story", type: "communication" },
          { text: "The spreadsheet — budget, timeline, launch checklist", type: "organization" },
          { text: "The brand — logo, colors, how it looks and feels", type: "creating" },
          { text: "The market research — who's buying, why, and what's missing", type: "analysis" },
        ],
      },
      {
        text: "A meeting is going in circles. Everyone's frustrated. What do you do?",
        options: [
          { text: "Name the tension out loud so people can actually talk about it", type: "communication" },
          { text: "Grab a whiteboard and give the conversation structure", type: "organization" },
          { text: "Suggest a completely different approach nobody's considered", type: "creating" },
          { text: "Quietly identify the one assumption that's throwing everything off", type: "analysis" },
        ],
      },
      {
        text: "You just spent 3 hours on something and lost track of time. What were you doing?",
        options: [
          { text: "Writing — an essay, a letter, something that needed the perfect words", type: "communication" },
          { text: "Planning — color-coded, every detail in place, deeply satisfying", type: "organization" },
          { text: "Making something — drawing, building, designing, hands moving", type: "creating" },
          { text: "Figuring something out — a pattern, a puzzle, a system I finally cracked", type: "analysis" },
        ],
      },
      {
        text: "Your 12-year-old self would be most impressed that you can now…",
        options: [
          { text: "Walk into any room and start a real conversation", type: "communication" },
          { text: "Turn chaos into a plan that actually works", type: "organization" },
          { text: "Make beautiful things that didn't exist before", type: "creating" },
          { text: "See through problems that confuse everyone else", type: "analysis" },
        ],
      },
      {
        text: "A community center just opened nearby. They need volunteers. What excites you?",
        options: [
          { text: "Hosting a storytelling night or conversation circle", type: "communication" },
          { text: "Running the volunteer schedule and making it actually work", type: "organization" },
          { text: "Turning the blank walls into something people want to photograph", type: "creating" },
          { text: "Figuring out what programs the neighborhood actually needs", type: "analysis" },
        ],
      },
    ],
  },
  {
    id: "values",
    name: "Values",
    icon: "◇",
    description: "What principles guide your choices?",
    dimensions: [
      { key: "justice", label: "Justice" },
      { key: "compassion", label: "Compassion" },
      { key: "growth", label: "Growth" },
      { key: "stewardship", label: "Stewardship" },
    ],
    questions: [
      {
        text: "Two kids are fighting over the last seat on the bus. What bothers you most?",
        options: [
          { text: "That the bigger kid always wins — size shouldn't equal power", type: "justice" },
          { text: "That the smaller kid looks like they might cry", type: "compassion" },
          { text: "That neither kid was taught how to handle this", type: "growth" },
          { text: "That the bus only has this many seats in the first place", type: "stewardship" },
        ],
      },
      {
        text: "You discover a local business is paying workers unfairly. What's your instinct?",
        options: [
          { text: "Organize — someone needs to hold them accountable", type: "justice" },
          { text: "Find those workers and make sure they're okay right now", type: "compassion" },
          { text: "Connect them with resources to build leverage for themselves", type: "growth" },
          { text: "Document it — this pattern needs to stop before it spreads", type: "stewardship" },
        ],
      },
      {
        text: "You have a million dollars and one rule: it must help your city. Where does it go?",
        options: [
          { text: "Legal aid for people who can't afford to fight for their rights", type: "justice" },
          { text: "A crisis fund — rent, medical bills, the emergencies that break families", type: "compassion" },
          { text: "Scholarships and programs that open doors for the next generation", type: "growth" },
          { text: "Buying land to protect green spaces before developers take them all", type: "stewardship" },
        ],
      },
      {
        text: "Your grandchild asks: \"What did you stand for?\" What do you want to say?",
        options: [
          { text: "\"I made sure the rules were fair, even when it was uncomfortable\"", type: "justice" },
          { text: "\"I never walked past someone who was hurting\"", type: "compassion" },
          { text: "\"I helped people see what they were capable of\"", type: "growth" },
          { text: "\"I protected the things that mattered so you could have them too\"", type: "stewardship" },
        ],
      },
      {
        text: "A new highway is planned through a historic neighborhood. What upsets you most?",
        options: [
          { text: "It always cuts through the poorest neighborhoods — always", type: "justice" },
          { text: "The elderly residents who'll lose the only home they've ever known", type: "compassion" },
          { text: "The kids who'll grow up without the community that shaped their parents", type: "growth" },
          { text: "A hundred years of history about to be erased for concrete", type: "stewardship" },
        ],
      },
    ],
  },
];

export const archetypes = {
  connector: {
    name: "The Connector",
    accent: "Connector",
    tagline: "You see people others walk past.",
    description:
      "You see people — really see them. In a world that's learned to look away, your instinct to reach toward others isn't just kindness. It's a radical act. Someone in your neighborhood went to bed last night wondering if anyone would notice if they disappeared. You're the answer to that question.",
    badge: "✦ The Connector",
    color: "var(--cat-connect)",
    colorHex: { light: "#c8793a", dark: "#e09a5a" },
    traits: ["Empathic", "Present", "Warm", "Intuitive"],
    strengths: ["Deep listening", "Building trust quickly", "Holding space for others", "Noticing who's missing"],
    growth: ["Setting boundaries", "Asking for help yourself", "Letting people sit with discomfort"],
    psychology: {
      framework: "Empathic Concern & Relational Motivation",
      constructs: [
        "Empathy-Altruism Hypothesis — Batson (2011) showed that empathic concern produces genuinely altruistic motivation, not self-interest. Connectors score high on dispositional empathic concern.",
        "Belongingness Need — Baumeister & Leary (1995) established that humans have a fundamental need to form and maintain lasting social bonds. Connectors are driven to fulfill this need in others.",
        "Prosocial Motivation — Grant (2008) found that other-oriented motivation leads to greater persistence, performance, and productivity in relational tasks.",
      ],
      impact: "Holt-Lunstad et al. (2015) meta-analysis: social connection reduces mortality risk by 50%. Regular social contact — even brief, genuine interactions — reduces loneliness by up to 40%. Volunteering adds purpose, which doubles the effect.",
    },
  },
  builder: {
    name: "The Builder",
    accent: "Builder",
    tagline: "You see potential where others see decay.",
    description:
      "You look at what's broken and see what it could become. Where others walk past the vacant lot, the fading mural, the crumbling steps — you see a garden, a story, a gathering place. Communities don't build themselves. They need people who show up with a hammer and a vision. That's you.",
    badge: "✦ The Builder",
    color: "var(--cat-build)",
    colorHex: { light: "#2a6f5e", dark: "#3d9b84" },
    traits: ["Resourceful", "Persistent", "Visionary", "Hands-on"],
    strengths: ["Turning vision into reality", "Rallying people around a project", "Working with what you have", "Seeing the long game"],
    growth: ["Finishing before starting something new", "Delegating instead of doing it all", "Celebrating progress, not just completion"],
    psychology: {
      framework: "Competence Motivation & Generativity",
      constructs: [
        "Self-Determination Theory — Deci & Ryan (2000) identified competence as a core psychological need. Builders are driven by the intrinsic reward of mastering tangible challenges.",
        "Generativity — Erikson (1963) described the adult need to create things that outlast oneself. McAdams & de St. Aubin (1992) showed generative adults report higher wellbeing.",
        "Place Attachment — Lewicka (2011) found that active investment in physical spaces creates place identity and social cohesion. Builders strengthen communities through tangible creation.",
      ],
      impact: "Studies find that building something tangible with others creates lasting social bonds. Kok et al. (2013) showed physical group activity lowers cortisol and increases oxytocin. The act of making something together is neurologically bonding.",
    },
  },
  guide: {
    name: "The Guide",
    accent: "Guide",
    tagline: "You light the path others can't yet see.",
    description:
      "You light the path for others because someone once lit it for you — or because no one did, and you know how that felt. Teaching isn't about having all the answers. It's about believing in someone's potential before they do. There's a kid in your city right now who needs exactly that belief.",
    badge: "✦ The Guide",
    color: "var(--cat-guide)",
    colorHex: { light: "#4a72a8", dark: "#6b9fd4" },
    traits: ["Patient", "Perceptive", "Encouraging", "Wise"],
    strengths: ["Seeing potential before it's obvious", "Breaking complexity into clarity", "Giving people confidence", "Playing the long game on human growth"],
    growth: ["Letting people fail and learn", "Not over-identifying with others' outcomes", "Valuing your own development too"],
    psychology: {
      framework: "Mentoring Psychology & Growth Mindset",
      constructs: [
        "Generativity — McAdams & de St. Aubin (1992) found that generative concern (caring about guiding the next generation) is one of the strongest predictors of psychological wellbeing in adulthood.",
        "Growth Mindset — Dweck (2006) showed that believing in others' capacity to grow changes their actual outcomes. Guides instinctively operate from a growth mindset about others.",
        "Scaffolding — Vygotsky's (1978) Zone of Proximal Development shows that learners advance most with a guide who pitches challenge just beyond their current reach.",
      ],
      impact: "Mentoring benefits the mentor as much as the mentee. Gruenewald et al. (2016) found that teachers and mentors report 60% higher life satisfaction and significantly lower feelings of isolation. The DuBois et al. (2011) meta-analysis confirmed positive effects across 73 mentoring studies.",
    },
  },
  solver: {
    name: "The Solver",
    accent: "Solver",
    tagline: "You fix what everyone else accepts as broken.",
    description:
      "You can't unsee inefficiency. While the world accepts \"that's just how it works,\" you're already sketching a better system on a napkin. The organizations trying to do good in your community are drowning in problems they can't see clearly. You see them. And you know how to fix them.",
    badge: "✦ The Solver",
    color: "var(--cat-solve)",
    colorHex: { light: "#7a5caa", dark: "#a085cc" },
    traits: ["Analytical", "Systematic", "Direct", "Innovative"],
    strengths: ["Diagnosing root causes", "Designing elegant solutions", "Cutting through noise", "Scaling what works"],
    growth: ["Listening before solving", "Valuing emotional context", "Accepting 'good enough' when perfect isn't possible"],
    psychology: {
      framework: "Effectance Motivation & Systems Thinking",
      constructs: [
        "Effectance Motivation — White (1959) proposed that humans have an intrinsic drive to interact effectively with their environment. Solvers express this as a compulsion to fix broken systems.",
        "Problem-Focused Coping — Lazarus & Folkman (1984) showed that people who engage directly with problems (vs. avoiding them) report higher self-efficacy and lower distress.",
        "Flow — Csikszentmihalyi (1990) found that complex problem-solving produces the deepest states of flow, especially when challenge matches skill. Solvers are flow-seekers.",
      ],
      impact: "Contributing your skills to solve real problems produces measurable increases in self-worth. Piliavin & Siegl (2007) found that feeling useful is one of the strongest predictors of wellbeing. Skills-based volunteering shows 2.5× the retention rate of general volunteering.",
    },
  },
};

/* Psychological framework behind the quizzes */
export const quizMethodology = {
  purpose: {
    framework: "Prosocial Motivation Typology",
    basis: "Adapted from Grant (2008) on other-oriented motivation and Batson (2011) on empathic concern. Each question measures the dominant prosocial orientation: relational (connector), generative (builder), developmental (guide), or systemic (solver).",
    citation: "Grant, A. M. (2008). Does intrinsic motivation fuel the prosocial fire? Motivational synergy in predicting persistence, performance, and productivity. Journal of Applied Psychology, 93(1), 48–58.",
  },
  wellbeing: {
    framework: "Social & Psychological Wellbeing",
    basis: "Draws on Keyes (1998) social wellbeing model and Ryan & Deci (2000) Self-Determination Theory. Measures four foundations: social connection, emotional awareness, community belonging, and intrinsic drive.",
    citation: "Keyes, C. L. M. (1998). Social well-being. Social Psychology Quarterly, 61(2), 121–140.",
  },
  skills: {
    framework: "Contribution Strengths",
    basis: "Adapted from the VIA Classification of Character Strengths (Peterson & Seligman, 2004) and Gardner's (1983) multiple intelligences, focused on how strengths translate to community contribution.",
    citation: "Peterson, C., & Seligman, M. E. P. (2004). Character strengths and virtues: A handbook and classification. Oxford University Press.",
  },
  values: {
    framework: "Moral Foundations & Basic Values",
    basis: "Grounded in Schwartz's (1992) Theory of Basic Human Values and Haidt's (2012) Moral Foundations Theory. Measures the primary value lens through which a person evaluates the world: fairness, care, development, or preservation.",
    citation: "Schwartz, S. H. (1992). Universals in the content and structure of values. Advances in Experimental Social Psychology, 25, 1–65.",
  },
};

export const opportunities = {
  connector: [
    { title: "Visit lonely adults at Sunrise Senior Living", desc: "Share afternoon tea and stories with residents who rarely have visitors. No experience needed — just show up and listen.", tag: "Human Connection", dist: "2.3 mi", sched: "Thu & Sat, 2–4pm", by: "Maria L.", joined: 12, cat: "connect" },
    { title: "Befriend a new refugee family", desc: "Help a family navigate their first months in a new country. Show them the grocery store. Share a meal. Be the friend they don't have yet.", tag: "Welcome & Belonging", dist: "4.1 mi", sched: "Flexible", by: "Amir K.", joined: 8, cat: "connect" },
    { title: "Crisis text line listener", desc: "Answer texts from people in crisis. Full training provided. Two hours a week from your couch could save a life.", tag: "Mental Health", dist: "Remote", sched: "2 hrs/week", by: "Crisis Text Line", joined: 34, cat: "connect" },
    { title: "Sit with hospice patients", desc: "No one should die alone. Sit with patients in their final days. Hold a hand. Read aloud. Be present.", tag: "Compassion", dist: "1.8 mi", sched: "Mon & Wed eves", by: "Grace Hospice", joined: 6, cat: "connect" },
  ],
  builder: [
    { title: "Restore the community garden on Oak St", desc: "The garden that fed 40 families last summer needs rebuilding after the storm. Help us raise beds, plant seeds, and bring it back.", tag: "Community Spaces", dist: "0.7 mi", sched: "Weekends, 9am–1pm", by: "Oak St. Neighbors", joined: 19, cat: "build" },
    { title: "Build a little free library", desc: "Design and build a weatherproof book-sharing box for a neighborhood that has no bookstore within 5 miles.", tag: "Access", dist: "3.4 mi", sched: "One weekend project", by: "Literacy First", joined: 4, cat: "build" },
    { title: "Paint the mural at Jefferson Elementary", desc: "Kids designed it. We need hands to paint it. Bring the wall to life and give them something to point at and say 'I made that.'", tag: "Public Art", dist: "2.1 mi", sched: "Aug 15–16", by: "Ms. Thompson", joined: 15, cat: "build" },
    { title: "Weekend build with Habitat for Humanity", desc: "Frame walls, hang drywall, paint a home for a family who's been on the waiting list for three years.", tag: "Housing", dist: "5.2 mi", sched: "3rd Sat / month", by: "Habitat LC", joined: 28, cat: "build" },
  ],
  guide: [
    { title: "Tutor 3rd graders in reading", desc: "Third grade is the pivot point — kids who can't read by then fall behind for life. Forty-five minutes of your Tuesday can change that trajectory.", tag: "Education", dist: "1.2 mi", sched: "Tue, 3:30–4:15pm", by: "Lincoln Library", joined: 9, cat: "guide" },
    { title: "Mentor a first-gen college applicant", desc: "They have the grades. They don't have anyone who's been through it. Help them navigate applications, essays, and believing they belong.", tag: "Mentorship", dist: "2.8 mi", sched: "Biweekly, 1 hour", by: "College Possible", joined: 11, cat: "guide" },
    { title: "Teach English at the community center", desc: "New arrivals with so much to say and no way to say it yet. Patient conversation partners needed — no credential required.", tag: "Language", dist: "1.5 mi", sched: "Mon & Wed, 6–7pm", by: "Newcomers Alliance", joined: 7, cat: "guide" },
    { title: "Lead a coding workshop for teens", desc: "Teach the basics to kids who've never seen a line of code. Show them what's possible. You might be the reason they choose this path.", tag: "Tech Access", dist: "4.5 mi", sched: "Saturdays, 10am–12pm", by: "Code Youth", joined: 13, cat: "guide" },
  ],
  solver: [
    { title: "Redesign the food bank intake process", desc: "Families wait 3 hours for a 10-minute pickup. The system is broken. Help us fix the flow so dignity isn't the cost of eating.", tag: "Systems Design", dist: "3.1 mi", sched: "Project-based", by: "Metro Food Bank", joined: 3, cat: "solve" },
    { title: "Map accessibility gaps downtown", desc: "Wheelchair users can't get from the bus stop to the library. Document every barrier, curb, and missing ramp so the city can't ignore it.", tag: "Accessibility", dist: "1.5 mi", sched: "5 hrs total", by: "Access Now", joined: 5, cat: "solve" },
    { title: "Optimize meal delivery routes", desc: "Meals on Wheels delivers 200 meals with a route designed in 1998. Modern routing could save 3 hours a day — and those meals arrive warm.", tag: "Logistics", dist: "2.9 mi", sched: "One-time analysis", by: "Meals on Wheels", joined: 2, cat: "solve" },
    { title: "Build a dashboard for the homeless shelter", desc: "They track beds, meals, and services on paper. A simple dashboard could free up 10 hours a week for actual care.", tag: "Data", dist: "2.0 mi", sched: "Ongoing, remote OK", by: "Haven House", joined: 4, cat: "solve" },
  ],
};

export const catColors = {
  connect: "var(--cat-connect)",
  build: "var(--cat-build)",
  guide: "var(--cat-guide)",
  solve: "var(--cat-solve)",
};

export const evidence = {
  connect:
    "Research shows regular social contact — even brief, genuine interactions — reduces loneliness by up to 40%. Volunteering adds purpose, which doubles the effect.",
  build:
    "Studies find that building something tangible with others creates lasting social bonds. Physical group activity lowers cortisol and increases oxytocin.",
  guide:
    "Mentoring benefits the mentor as much as the mentee. Teachers report 60% higher life satisfaction and significantly lower feelings of isolation.",
  solve:
    "Contributing your skills to solve real problems produces measurable increases in self-worth. Feeling useful is one of the strongest predictors of wellbeing.",
};

export const offerCategories = [
  {
    id: "tickets",
    name: "Tickets",
    icon: "🎟️",
    tagline: "Connect & transfer in one tap",
    detail: "Link your Ticketmaster, AXS, SeatGeek, or Eventbrite account. We pull your upcoming events, verify each ticket, and transfer directly — no screenshots, no PDFs, no guessing.",
    fields: [],
  },
  {
    id: "food",
    name: "Food",
    icon: "🍲",
    tagline: "Meals that shouldn't go to waste",
    detail: "Restaurant surplus, catering leftovers, or grocery donations go directly to community events, shelters, and families in need.",
    fields: [
      { key: "foodType", label: "What kind of food?", type: "text", placeholder: "e.g., 30 boxed lunches" },
      { key: "pickupBy", label: "Pickup by", type: "text", placeholder: "e.g., Today by 6pm" },
      { key: "location", label: "Pickup location", type: "text", placeholder: "e.g., 123 Main St" },
      { key: "value", label: "Estimated value ($)", type: "number", placeholder: "150" },
    ],
  },
  {
    id: "services",
    name: "Services",
    icon: "🛠️",
    tagline: "Your time & expertise",
    detail: "Pro bono consulting, design work, legal advice, tutoring, photography — your skills directly power community organizations.",
    fields: [
      { key: "serviceType", label: "What can you offer?", type: "text", placeholder: "e.g., Logo design for nonprofits" },
      { key: "hours", label: "Hours available", type: "number", placeholder: "5" },
      { key: "availability", label: "When?", type: "text", placeholder: "e.g., Weekday evenings" },
      { key: "value", label: "Hourly rate equivalent ($)", type: "number", placeholder: "75" },
    ],
  },
  {
    id: "goods",
    name: "Goods",
    icon: "📦",
    tagline: "Items in good shape",
    detail: "Clothing, furniture, supplies, equipment — things you don't need that someone else does. Matched to community projects and families.",
    fields: [
      { key: "itemDescription", label: "What are you donating?", type: "text", placeholder: "e.g., 10 winter coats, adult sizes" },
      { key: "condition", label: "Condition", type: "select", options: ["New", "Like new", "Good", "Fair"] },
      { key: "pickupOrDrop", label: "Pickup or drop-off?", type: "select", options: ["I can drop off", "Needs pickup"] },
      { key: "value", label: "Estimated value ($)", type: "number", placeholder: "200" },
    ],
  },
];

/* ── Personality Analysis System ── */

export const dimensionMeta = {
  purpose: {
    connector: { short: "Co", label: "Connector", emoji: "🤝", desc: "Driven by human connection and empathy" },
    builder: { short: "Bu", label: "Builder", emoji: "🔨", desc: "Driven by tangible creation and legacy" },
    guide: { short: "Gu", label: "Guide", emoji: "⭐", desc: "Driven by mentorship and human growth" },
    solver: { short: "So", label: "Solver", emoji: "⚙️", desc: "Driven by elegant solutions to real problems" },
  },
  wellbeing: {
    social: { short: "Sc", label: "Social", emoji: "💬", desc: "Recharged through deep conversation" },
    emotional: { short: "Em", label: "Emotional", emoji: "🌊", desc: "Grounded in self-awareness" },
    belonging: { short: "Be", label: "Belonging", emoji: "🏘️", desc: "Rooted in community and place" },
    drive: { short: "Dr", label: "Drive", emoji: "🔥", desc: "Fueled by purpose and progress" },
  },
  skills: {
    communication: { short: "Cm", label: "Communication", emoji: "✍️", desc: "Strength in words and connection" },
    organization: { short: "Or", label: "Organization", emoji: "📋", desc: "Strength in structure and planning" },
    creating: { short: "Cr", label: "Creating", emoji: "🎨", desc: "Strength in imagination and design" },
    analysis: { short: "An", label: "Analysis", emoji: "🔍", desc: "Strength in pattern recognition" },
  },
  values: {
    justice: { short: "Ju", label: "Justice", emoji: "⚖️", desc: "Guided by fairness and equity" },
    compassion: { short: "Cp", label: "Compassion", emoji: "💛", desc: "Guided by care and kindness" },
    growth: { short: "Gr", label: "Growth", emoji: "🌱", desc: "Guided by potential and development" },
    stewardship: { short: "St", label: "Stewardship", emoji: "🌍", desc: "Guided by preservation and legacy" },
  },
};

export const compositeTypes = {
  connector: {
    communication: { name: "The Empathic Voice", desc: "You combine deep emotional intelligence with the rare ability to articulate what others feel but can't say. People don't just feel heard around you — they feel understood for the first time." },
    organization: { name: "The Community Weaver", desc: "You don't just connect people — you build the structures that keep them connected. Potlucks, check-in schedules, neighborhood networks — you architect belonging." },
    creating: { name: "The Heart Artist", desc: "Your empathy flows into everything you make. Whether it's a letter, a meal, or a space — what you create makes people feel less alone." },
    analysis: { name: "The Social Scientist", desc: "You read people like data — not coldly, but with a precision that lets you understand why someone is hurting before they tell you. You see the patterns others miss." },
  },
  builder: {
    communication: { name: "The Rallying Force", desc: "You don't just build things — you build movements. Your ability to articulate a vision pulls people toward something bigger than themselves." },
    organization: { name: "The Master Planner", desc: "Nothing slips through. You turn ambitious visions into actionable plans, and your projects finish when others stall. You're the one who makes it real." },
    creating: { name: "The Visionary Maker", desc: "You see what doesn't exist yet and build it. Not in theory — in wood, in pixels, in brick. Your creations outlast conversations." },
    analysis: { name: "The Strategic Architect", desc: "You build with intention and evidence. Where others see an empty lot, you see load-bearing walls, traffic patterns, and a community gathering two years from now." },
  },
  guide: {
    communication: { name: "The Inspiring Teacher", desc: "You make the complex feel simple and the impossible feel reachable. Your words don't just inform — they transform how people see themselves." },
    organization: { name: "The Program Director", desc: "You don't just mentor one person — you design systems that mentor many. Curricula, mentorship programs, structured growth paths — you scale human development." },
    creating: { name: "The Creative Mentor", desc: "You teach through making. Your instinct is to hand someone a brush, a keyboard, a tool — and watch their eyes change when they realize what they can do." },
    analysis: { name: "The Insight Coach", desc: "You see what people can't see about themselves — the pattern in their failures, the thread in their strengths. Your observations change trajectories." },
  },
  solver: {
    communication: { name: "The Translator", desc: "You make the invisible visible. Complex systems, tangled policies, broken processes — you explain them so clearly that everyone in the room can see the fix." },
    organization: { name: "The Systems Optimizer", desc: "You don't just solve problems — you prevent them. Your gift is designing processes that make good outcomes automatic and bad ones nearly impossible." },
    creating: { name: "The Innovation Engineer", desc: "You prototype solutions while others are still debating the problem. Your creations are functional first and beautiful because they work." },
    analysis: { name: "The Root Cause Detective", desc: "You find what everyone else missed. Where others treat symptoms, you dig until you find the one broken thing that explains everything." },
  },
};

export const compatibilityMap = {
  connector: {
    best: "builder",
    bestDesc: "Connectors find the people. Builders create the places where those connections deepen. Together, you don't just bring people together — you give them somewhere to belong.",
    growth: "solver",
    growthDesc: "Solvers push you to think systemically, not just personally. They help you see that the loneliest person in the neighborhood might need a better system, not just a better friend.",
  },
  builder: {
    best: "connector",
    bestDesc: "Builders create the physical spaces. Connectors fill them with life. Your structures become gathering places because a Connector knows who needs to be there.",
    growth: "guide",
    growthDesc: "Guides remind you that not everything worth building is tangible. Sometimes the most lasting thing you can build is someone's confidence.",
  },
  guide: {
    best: "solver",
    bestDesc: "Guides nurture individual potential. Solvers remove the barriers blocking it. Together, you don't just believe in someone — you clear the path for them to move.",
    growth: "connector",
    growthDesc: "Connectors remind you that sometimes people don't need a lesson. They need a friend. Your instinct to teach can learn from their instinct to simply be present.",
  },
  solver: {
    best: "guide",
    bestDesc: "Solvers fix systems. Guides develop people. Together, you build organizations that are both efficient and human — where the process serves the person, not the other way around.",
    growth: "builder",
    growthDesc: "Builders teach you that not every problem needs an elegant solution. Sometimes you just need to pick up a hammer and start. Action before optimization.",
  },
};

export function getImprintCode(quizResults) {
  const code = [];
  const catOrder = ["purpose", "wellbeing", "skills", "values"];
  for (const catId of catOrder) {
    const result = quizResults[catId];
    if (result) {
      const primary = getPrimaryDimension(result.scores);
      if (primary && dimensionMeta[catId]?.[primary]) {
        code.push({ catId, key: primary, ...dimensionMeta[catId][primary] });
      }
    }
  }
  return code;
}

export function getDimensionScores(scores, maxPerDimension) {
  const total = Object.values(scores).reduce((a, b) => a + b, 0);
  if (total === 0) return [];
  return Object.entries(scores)
    .map(([key, val]) => ({
      key,
      score: val,
      max: maxPerDimension,
      pct: Math.round((val / maxPerDimension) * 100),
    }))
    .sort((a, b) => b.score - a.score);
}

export function getPersonalityNarrative(quizResults) {
  const parts = [];
  const purpose = quizResults.purpose ? getPrimaryDimension(quizResults.purpose.scores) : null;
  const wellbeing = quizResults.wellbeing ? getPrimaryDimension(quizResults.wellbeing.scores) : null;
  const skills = quizResults.skills ? getPrimaryDimension(quizResults.skills.scores) : null;
  const values = quizResults.values ? getPrimaryDimension(quizResults.values.scores) : null;

  if (purpose && skills && compositeTypes[purpose]?.[skills]) {
    parts.push(compositeTypes[purpose][skills].desc);
  }

  if (wellbeing && dimensionMeta.wellbeing[wellbeing]) {
    const wb = dimensionMeta.wellbeing[wellbeing];
    const wellbeingInsights = {
      social: "Your energy comes from the people around you — real conversation, shared silence, the feeling of being truly known.",
      emotional: "You process the world deeply before you act. That inner clarity is rare, and it makes your decisions count.",
      belonging: "Place matters to you. Not just geography — the feeling of being part of something rooted and real.",
      drive: "You're powered by forward motion. When you know where you're heading, everything else falls into alignment.",
    };
    parts.push(wellbeingInsights[wellbeing]);
  }

  if (values && dimensionMeta.values[values]) {
    const valueInsights = {
      justice: "At your core, you believe the world should be fair — and you're willing to do the uncomfortable work of making it so.",
      compassion: "Your moral compass points toward kindness, even when it's inconvenient. You'd rather err on the side of care.",
      growth: "You see potential everywhere — in people, in systems, in yourself. Standing still feels like falling behind.",
      stewardship: "You carry a sense of responsibility for what comes next. Protecting what matters isn't conservative — it's courageous.",
    };
    parts.push(valueInsights[values]);
  }

  return parts;
}

export function getPrimaryDimension(scores) {
  let max = -1;
  let winners = [];
  for (const [key, val] of Object.entries(scores)) {
    if (val > max) {
      max = val;
      winners = [key];
    } else if (val === max) {
      winners.push(key);
    }
  }
  // Deterministic tie-break: use alphabetical order so results are stable
  if (winners.length > 1) winners.sort();
  return winners[0] || null;
}
