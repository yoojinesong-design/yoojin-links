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
        text: "When you imagine a better world, what changes first?",
        options: [
          { text: "No one eats alone", type: "connector" },
          { text: "Every neighborhood has a gathering place", type: "builder" },
          { text: "Every kid has a mentor", type: "guide" },
          { text: "Systems work for people, not against them", type: "solver" },
        ],
      },
      {
        text: "What kind of moment makes you feel most alive?",
        options: [
          { text: "A deep conversation with someone who needed it", type: "connector" },
          { text: "Standing back and seeing something I made with my hands", type: "builder" },
          { text: "Watching someone's face when something finally clicks", type: "guide" },
          { text: "Finding the elegant solution to a messy problem", type: "solver" },
        ],
      },
      {
        text: "What would keep you up at night?",
        options: [
          { text: "Knowing someone nearby has no one to call", type: "connector" },
          { text: "Watching a place you love fall apart", type: "builder" },
          { text: "A kid who's brilliant but has no one in their corner", type: "guide" },
          { text: "A good organization failing because of a fixable problem", type: "solver" },
        ],
      },
      {
        text: "What do people come to you for?",
        options: [
          { text: "When they need someone who'll actually listen", type: "connector" },
          { text: "When something needs to get done, and done right", type: "builder" },
          { text: "When they're stuck and need someone to believe in them", type: "guide" },
          { text: "When they can't figure out what's going wrong", type: "solver" },
        ],
      },
      {
        text: "What would you want to be remembered for?",
        options: [
          { text: "Making people feel less alone", type: "connector" },
          { text: "Building something that outlasted me", type: "builder" },
          { text: "The lives I helped change direction", type: "guide" },
          { text: "Fixing what everyone else accepted as broken", type: "solver" },
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
        text: "What recharges you most after a hard week?",
        options: [
          { text: "A long conversation with someone who gets it", type: "social" },
          { text: "Quiet time to process and reflect", type: "emotional" },
          { text: "Being in a place where people know my name", type: "belonging" },
          { text: "Working on something that matters to me", type: "drive" },
        ],
      },
      {
        text: "What's the best part of your average Tuesday?",
        options: [
          { text: "A moment of real connection with another person", type: "social" },
          { text: "Noticing something beautiful or true", type: "emotional" },
          { text: "The familiar rhythm of my neighborhood", type: "belonging" },
          { text: "Making progress on something I care about", type: "drive" },
        ],
      },
      {
        text: "When you're struggling, what helps most?",
        options: [
          { text: "Talking it out with someone who listens", type: "social" },
          { text: "Sitting with the feeling until it makes sense", type: "emotional" },
          { text: "Going where the community gathers", type: "belonging" },
          { text: "Reminding myself what I'm building toward", type: "drive" },
        ],
      },
      {
        text: "What would make tomorrow better than today?",
        options: [
          { text: "Deeper conversation with someone I trust", type: "social" },
          { text: "More space to feel what I actually feel", type: "emotional" },
          { text: "Knowing my neighbors better", type: "belonging" },
          { text: "A clearer sense of where I'm heading", type: "drive" },
        ],
      },
      {
        text: "What's your strongest foundation right now?",
        options: [
          { text: "The people who show up for me", type: "social" },
          { text: "My ability to understand myself", type: "emotional" },
          { text: "The community I'm part of", type: "belonging" },
          { text: "My sense of purpose and direction", type: "drive" },
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
        text: "Someone hands you a big messy project. What do you instinctively do first?",
        options: [
          { text: "Talk to people to understand the real problem", type: "communication" },
          { text: "Create a plan with steps and deadlines", type: "organization" },
          { text: "Sketch, prototype, or build something rough", type: "creating" },
          { text: "Look at the data to find what's actually going on", type: "analysis" },
        ],
      },
      {
        text: "In a group, people tend to rely on you for…",
        options: [
          { text: "Explaining things clearly and keeping peace", type: "communication" },
          { text: "Making sure everything runs smoothly", type: "organization" },
          { text: "Coming up with ideas no one else thought of", type: "creating" },
          { text: "Spotting the flaw everyone else missed", type: "analysis" },
        ],
      },
      {
        text: "Which of these would you enjoy most?",
        options: [
          { text: "Facilitating a conversation between strangers", type: "communication" },
          { text: "Organizing a community event from scratch", type: "organization" },
          { text: "Designing a poster, website, or space", type: "creating" },
          { text: "Solving a puzzle that's stumped everyone", type: "analysis" },
        ],
      },
      {
        text: "Which compliment would mean the most?",
        options: [
          { text: "\"You have a way of making people feel heard\"", type: "communication" },
          { text: "\"I don't know how you keep everything together\"", type: "organization" },
          { text: "\"That was the most creative solution I've ever seen\"", type: "creating" },
          { text: "\"You see things other people don't\"", type: "analysis" },
        ],
      },
      {
        text: "If you had one free weekend to help a nonprofit, you'd…",
        options: [
          { text: "Run a workshop or write their story", type: "communication" },
          { text: "Streamline their operations or plan an event", type: "organization" },
          { text: "Redesign their space, brand, or materials", type: "creating" },
          { text: "Analyze their data and find the bottleneck", type: "analysis" },
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
        text: "What kind of wrong hits you hardest?",
        options: [
          { text: "Someone being treated unfairly because of who they are", type: "justice" },
          { text: "Someone suffering when help is available", type: "compassion" },
          { text: "Someone never getting the chance to reach their potential", type: "growth" },
          { text: "Something beautiful or valuable being destroyed", type: "stewardship" },
        ],
      },
      {
        text: "What would you fight for?",
        options: [
          { text: "Equal access and fair treatment for everyone", type: "justice" },
          { text: "Kindness, even when it's inconvenient", type: "compassion" },
          { text: "Everyone having the tools to grow", type: "growth" },
          { text: "Preserving what future generations will need", type: "stewardship" },
        ],
      },
      {
        text: "Which leader do you most admire?",
        options: [
          { text: "One who challenges unjust systems", type: "justice" },
          { text: "One who shows up for the most vulnerable", type: "compassion" },
          { text: "One who invests in the next generation", type: "growth" },
          { text: "One who protects what can't protect itself", type: "stewardship" },
        ],
      },
      {
        text: "If you could fix one thing about your city…",
        options: [
          { text: "Close the gaps that divide people", type: "justice" },
          { text: "Make sure no one falls through the cracks", type: "compassion" },
          { text: "Give every kid what they need to thrive", type: "growth" },
          { text: "Protect what makes this place special", type: "stewardship" },
        ],
      },
      {
        text: "What principle would you never compromise?",
        options: [
          { text: "Everyone deserves a voice", type: "justice" },
          { text: "No one should suffer alone", type: "compassion" },
          { text: "People can always become more", type: "growth" },
          { text: "We owe something to what comes next", type: "stewardship" },
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
