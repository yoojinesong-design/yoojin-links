'use client'
import { useState, useCallback, useEffect, useRef } from 'react'

/* ── Lightweight confetti burst (no dependencies) ── */
function fireConfetti() {
  const canvas = document.createElement('canvas')
  canvas.style.cssText = 'position:fixed;inset:0;z-index:9999;pointer-events:none;width:100%;height:100%'
  document.body.appendChild(canvas)
  canvas.width = window.innerWidth * 2
  canvas.height = window.innerHeight * 2
  const ctx = canvas.getContext('2d')
  ctx.scale(2, 2)

  const colors = ['#a855f7', '#ec4899', '#f59e0b', '#8b5cf6', '#f43f5e', '#22d3ee', '#34d399']
  const pieces = Array.from({ length: 60 }, () => ({
    x: window.innerWidth / 2 + (Math.random() - 0.5) * 200,
    y: window.innerHeight / 2,
    vx: (Math.random() - 0.5) * 16,
    vy: -Math.random() * 18 - 4,
    w: Math.random() * 8 + 4,
    h: Math.random() * 6 + 2,
    color: colors[Math.floor(Math.random() * colors.length)],
    rot: Math.random() * Math.PI * 2,
    rv: (Math.random() - 0.5) * 0.3,
    gravity: 0.4 + Math.random() * 0.2,
  }))

  let frame = 0
  const animate = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    let alive = false
    for (const p of pieces) {
      p.x += p.vx
      p.vy += p.gravity
      p.y += p.vy
      p.rot += p.rv
      p.vx *= 0.98
      if (p.y < window.innerHeight + 50) {
        alive = true
        ctx.save()
        ctx.translate(p.x, p.y)
        ctx.rotate(p.rot)
        ctx.fillStyle = p.color
        ctx.globalAlpha = Math.max(0, 1 - frame / 80)
        ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h)
        ctx.restore()
      }
    }
    frame++
    if (alive && frame < 90) requestAnimationFrame(animate)
    else canvas.remove()
  }
  requestAnimationFrame(animate)
}

/* ─────────────────────────────────────────────────────────────
   FREE WILL UTILIZER

   "Amazing use of free will" = when someone takes the mundane
   fact of having free will and uses it for something
   unexpectedly creative, oddly specific, or beautifully absurd.

   These aren't suggestions. They're CHALLENGES.
   Do it. Document it. Post it. Let them comment.
   ───────────────────────────────────────────────────────────── */

const CHALLENGES = [
  // ── MAKE SOMETHING ── things that produce a shareable artifact
  { text: 'Write a Yelp review for your own kitchen. Be devastatingly honest. Post it.', tags: ['solo', 'free', 'indoor'], emoji: '⭐', vibe: 'unhinged', tier: 1 },
  { text: 'Design a national flag for your apartment. Present the symbolism to someone with a straight face.', tags: ['solo', 'free', 'indoor'], emoji: '🏴', vibe: 'genius', tier: 2 },
  { text: 'Make a resume for your pet. Apply to one job.', tags: ['solo', 'free', 'indoor'], emoji: '📄', vibe: 'unhinged', tier: 3 },
  { text: 'Write a formal resignation letter to a bad habit. Read it aloud. Seal it. Burn it.', tags: ['solo', 'free', 'indoor'], emoji: '🔥', vibe: 'genius', tier: 2 },
  { text: 'Build a tiny museum exhibit for the most interesting object in your junk drawer. Write a plaque.', tags: ['solo', 'free', 'indoor'], emoji: '🏛️', vibe: 'genius', tier: 2 },
  { text: 'Create an IKEA-style instruction manual for something you do every day. Illustrate it.', tags: ['solo', 'free', 'indoor'], emoji: '📐', vibe: 'genius', tier: 2 },
  { text: 'Make a PowerPoint proving your favorite snack is the peak of human achievement. Present it.', tags: ['solo', 'free', 'indoor'], emoji: '📊', vibe: 'unhinged', tier: 2 },
  { text: 'Draw a self-portrait using only your non-dominant hand. Frame it. Hang it up. Don\'t explain.', tags: ['solo', 'free', 'indoor'], emoji: '🎨', vibe: 'genius', tier: 1 },
  { text: 'Write your morning routine as a heist movie script. Cast your friends in the roles.', tags: ['solo', 'free', 'indoor'], emoji: '🎬', vibe: 'genius', tier: 2 },
  { text: 'Compose a breakup letter to an app you\'re deleting. Make it emotional.', tags: ['solo', 'free', 'indoor'], emoji: '💔', vibe: 'unhinged', tier: 1 },
  { text: 'Write a 5-star review of water. Post it somewhere. It deserves the recognition.', tags: ['solo', 'free', 'indoor'], emoji: '💧', vibe: 'unhinged', tier: 1 },
  { text: 'Create a nature documentary narration of yourself making coffee. Film it.', tags: ['solo', 'free', 'indoor'], emoji: '🎙️', vibe: 'unhinged', tier: 2 },
  { text: 'Write a formal apology to a plant you forgot to water. Deliver it in person.', tags: ['solo', 'free', 'indoor'], emoji: '🌿', vibe: 'unhinged', tier: 1 },
  { text: 'Build a time capsule in a shoebox. Include something from today that will confuse future you.', tags: ['solo', 'free', 'indoor'], emoji: '📦', vibe: 'wholesome', tier: 2 },
  { text: 'Take a photo of every door in your home. Post it as an art series. Title each one.', tags: ['solo', 'free', 'indoor'], emoji: '🚪', vibe: 'genius', tier: 1 },
  { text: 'Write a recipe for your current emotional state. Include prep time and serving size.', tags: ['solo', 'free', 'indoor'], emoji: '🧑‍🍳', vibe: 'unhinged', tier: 1 },
  { text: 'Create a Wikipedia article for your friend group. Include the "controversies" section.', tags: ['group', 'free', 'indoor'], emoji: '📰', vibe: 'unhinged', tier: 2 },
  { text: 'Map your home from memory. Label the danger zones, the vibes, the contested territories.', tags: ['solo', 'free', 'indoor'], emoji: '🗺️', vibe: 'genius', tier: 1 },
  { text: 'Invent a cocktail with only what you have right now. Name it something absurdly dramatic.', tags: ['solo', 'free', 'indoor'], emoji: '🍹', vibe: 'unhinged', tier: 1 },
  { text: 'Create a playlist that tells the entire story of your week. Track order matters.', tags: ['solo', 'free', 'indoor'], emoji: '🎵', vibe: 'wholesome', tier: 1 },

  // ── GO SOMEWHERE ── outdoor/adventure challenges
  { text: 'Sit on a park bench and write a one-paragraph biography for every person who walks by.', tags: ['solo', 'free', 'outdoor'], emoji: '📝', vibe: 'genius', tier: 1 },
  { text: 'Find the most architecturally ugly building near you. Write it a love letter. Photograph both.', tags: ['solo', 'free', 'outdoor'], emoji: '🏢', vibe: 'unhinged', tier: 2 },
  { text: 'Take a photo walk but only shoot reflections. Post the series.', tags: ['solo', 'free', 'outdoor'], emoji: '📸', vibe: 'genius', tier: 1 },
  { text: 'Walk until you find something beautiful. Take a photo. That\'s it. Walk home.', tags: ['solo', 'free', 'outdoor'], emoji: '🚶', vibe: 'wholesome', tier: 1 },
  { text: 'Pick a cloud. Name it. Watch it until it changes shape. Mourn the old shape publicly.', tags: ['solo', 'free', 'outdoor'], emoji: '☁️', vibe: 'unhinged', tier: 1 },
  { text: 'Go to a bookstore. Read only the first sentence of 20 books. Crown a winner.', tags: ['solo', 'free', 'outdoor'], emoji: '📖', vibe: 'genius', tier: 1 },
  { text: 'Collect 5 interesting leaves. Press them. Start a tiny herbarium. Give it a Latin name.', tags: ['solo', 'free', 'outdoor'], emoji: '🍂', vibe: 'genius', tier: 2 },
  { text: 'Ride a random bus to the last stop. Document everything like you\'re a travel vlogger in a foreign country.', tags: ['solo', 'paid', 'outdoor'], emoji: '🚌', vibe: 'genius', tier: 3 },
  { text: 'Explore a neighborhood you\'ve never been to. Rate it on vibes only. Write a fake travel blog.', tags: ['solo', 'free', 'outdoor'], emoji: '🏘️', vibe: 'unhinged', tier: 2 },
  { text: 'Go to a museum. Pick one painting. Sit with it for 15 minutes. Write down what it told you.', tags: ['solo', 'paid', 'indoor'], emoji: '🖼️', vibe: 'genius', tier: 2 },
  { text: 'Buy a disposable camera. Use all 27 shots in one day. Develop them next month. No previews.', tags: ['solo', 'paid', 'outdoor'], emoji: '📷', vibe: 'genius', tier: 3 },
  { text: 'Find a tree. Sit under it for 10 minutes. Write the tree a thank you note. Leave it.', tags: ['solo', 'free', 'outdoor'], emoji: '🌳', vibe: 'wholesome', tier: 1 },
  { text: 'Take a photo of something completely ordinary every day for a week. See if your eye changes.', tags: ['solo', 'free', 'outdoor'], emoji: '📱', vibe: 'genius', tier: 2 },

  // ── WITH PEOPLE ── group challenges
  { text: 'Host an awards ceremony for everyday objects in your house. Acceptance speeches mandatory.', tags: ['group', 'free', 'indoor'], emoji: '🏆', vibe: 'unhinged', tier: 2 },
  { text: 'Everyone draws a portrait of the person to their left. Host a gallery opening. Serve snacks.', tags: ['group', 'free', 'indoor'], emoji: '🖼️', vibe: 'genius', tier: 2 },
  { text: 'Build a blanket fort. No phones inside. Talk like it\'s 2005.', tags: ['group', 'free', 'indoor'], emoji: '🏰', vibe: 'wholesome', tier: 1 },
  { text: 'Each person pitches a business that should absolutely not exist. The worst idea wins.', tags: ['group', 'free', 'indoor'], emoji: '💼', vibe: 'unhinged', tier: 1 },
  { text: 'Cook a meal where each person controls one ingredient. No communication allowed.', tags: ['group', 'free', 'indoor'], emoji: '🍳', vibe: 'genius', tier: 2 },
  { text: 'Everyone writes a letter to their 10-year-ago self. Read them aloud or don\'t. Your call.', tags: ['group', 'free', 'indoor'], emoji: '✉️', vibe: 'wholesome', tier: 2 },
  { text: 'Play "museum" — everyone brings one object and writes a museum plaque for it.', tags: ['group', 'free', 'indoor'], emoji: '🏛️', vibe: 'genius', tier: 1 },
  { text: 'Write and perform a 3-minute play about something that actually happened to the group.', tags: ['group', 'free', 'indoor'], emoji: '🎭', vibe: 'genius', tier: 3 },
  { text: 'Everyone teaches the group one skill in exactly 5 minutes. Timer is strict. No mercy.', tags: ['group', 'free', 'indoor'], emoji: '⏱️', vibe: 'genius', tier: 1 },
  { text: 'Do a photo walk. Same subject, everyone shoots it differently. Compare. Crown a winner.', tags: ['group', 'free', 'outdoor'], emoji: '📸', vibe: 'genius', tier: 1 },
  { text: 'Pick a random spot on a map. Everyone races to get there by different routes. Meet for food after.', tags: ['group', 'free', 'outdoor'], emoji: '🗺️', vibe: 'unhinged', tier: 3 },
  { text: 'Film a 60-second mockumentary about a completely normal park. Narrate like it\'s the Amazon.', tags: ['group', 'free', 'outdoor'], emoji: '🎥', vibe: 'genius', tier: 2 },
  { text: 'Go thrift shopping. $5 budget. Find the most thoughtful gift for the person next to you.', tags: ['group', 'paid', 'outdoor'], emoji: '🎁', vibe: 'wholesome', tier: 1 },
  { text: 'Everyone buys one weird ingredient. You have 1 hour to make it into an actual meal. Document it.', tags: ['group', 'paid', 'indoor'], emoji: '🛒', vibe: 'genius', tier: 2 },
  { text: 'Stargaze and invent new constellations named after inside jokes. Chart them.', tags: ['group', 'free', 'outdoor'], emoji: '⭐', vibe: 'wholesome', tier: 2 },
  { text: 'Have a walking debate on the most unserious topic possible. Appoint a judge. Take it way too seriously.', tags: ['group', 'free', 'outdoor'], emoji: '⚖️', vibe: 'unhinged', tier: 1 },

  // ── DO GOOD ── charity/kindness challenges
  { text: 'Write 10 specific, encouraging sticky notes. Hide them in library books for strangers.', tags: ['solo', 'charity', 'indoor', 'free'], emoji: '💌', vibe: 'wholesome', tier: 1 },
  { text: 'Bake cookies. Knock on a neighbor\'s door. Just say "these are for you." Leave.', tags: ['solo', 'charity', 'outdoor', 'paid'], emoji: '🍪', vibe: 'wholesome', tier: 1 },
  { text: 'Organize a skill swap — teach someone to cook, learn guitar in return. Film the contrast.', tags: ['group', 'charity', 'indoor', 'free'], emoji: '🔄', vibe: 'genius', tier: 2 },
  { text: 'Fill a backpack with essentials. Give it to someone who needs it. Include a handwritten note.', tags: ['solo', 'charity', 'outdoor', 'paid'], emoji: '🎒', vibe: 'wholesome', tier: 2 },
  { text: 'Organize a "pay what you can" neighborhood dinner. Everyone brings one dish.', tags: ['group', 'charity', 'outdoor', 'free'], emoji: '🍛', vibe: 'genius', tier: 3 },
  { text: 'Write a glowing LinkedIn recommendation for someone who helped you and has no idea.', tags: ['solo', 'charity', 'indoor', 'free'], emoji: '✍️', vibe: 'wholesome', tier: 1 },
  { text: 'Leave a $5 bill tucked into chapter one of a children\'s book at a bookstore.', tags: ['solo', 'charity', 'outdoor', 'paid'], emoji: '💵', vibe: 'genius', tier: 1 },
  { text: 'Compliment 5 strangers today. Specific compliments only. Not "nice shirt." You can do better.', tags: ['solo', 'charity', 'outdoor', 'free'], emoji: '💬', vibe: 'wholesome', tier: 1 },
  { text: 'Buy a stranger\'s coffee. Leave before they can thank you. Tell no one. Except the internet.', tags: ['solo', 'charity', 'outdoor', 'paid'], emoji: '☕', vibe: 'wholesome', tier: 1 },
  { text: 'Create care packages for a local shelter. Include a handwritten note in each one.', tags: ['group', 'charity', 'indoor', 'paid'], emoji: '📦', vibe: 'wholesome', tier: 2 },

  // ── SAVE THE PLANET ── eco challenges
  { text: 'Do a 15-minute trash pickup in your neighborhood. Photograph the haul. Make people feel things.', tags: ['solo', 'eco', 'outdoor', 'free'], emoji: '🗑️', vibe: 'genius', tier: 1 },
  { text: 'Build a bird feeder from a milk carton. Paint it. Give it an address number. Welcome tenants.', tags: ['solo', 'eco', 'outdoor', 'free'], emoji: '🐦', vibe: 'genius', tier: 2 },
  { text: 'Start a windowsill herb garden from grocery store seeds. Name each plant. Document growth.', tags: ['solo', 'eco', 'indoor', 'paid'], emoji: '🌱', vibe: 'wholesome', tier: 1 },
  { text: 'Organize a clothing swap party. Dress code: you must wear your swap home.', tags: ['group', 'eco', 'indoor', 'free'], emoji: '👗', vibe: 'genius', tier: 2 },
  { text: 'Plant a tree. Take a photo with it. Take the same photo every year. Watch you both change.', tags: ['solo', 'eco', 'outdoor', 'paid'], emoji: '🌳', vibe: 'wholesome', tier: 2 },
  { text: 'Organize a beach cleanup. Turn the best trash finds into an art installation. Title each piece.', tags: ['group', 'eco', 'outdoor', 'free'], emoji: '🏖️', vibe: 'genius', tier: 3 },
  { text: 'Repair something you were about to throw away. Film the process. Post it as oddly satisfying content.', tags: ['solo', 'eco', 'indoor', 'free'], emoji: '🔧', vibe: 'genius', tier: 1 },
  { text: 'Set up a Little Free Library. Stock it with your favorites. Add handwritten reviews inside each.', tags: ['group', 'eco', 'outdoor', 'paid'], emoji: '📚', vibe: 'genius', tier: 3 },
  { text: 'Start composting. Give your compost bin a name. Introduce it to guests.', tags: ['solo', 'eco', 'indoor', 'free'], emoji: '♻️', vibe: 'unhinged', tier: 1 },

  // ── GO DEEP ── introspective but shareable
  { text: 'Call someone you haven\'t talked to in a year. Don\'t explain why. Just ask how they are.', tags: ['solo', 'free', 'indoor'], emoji: '📞', vibe: 'wholesome', tier: 1 },
  { text: 'Write a letter to yourself at 80. Tell them what mattered today. Seal it.', tags: ['solo', 'free', 'indoor'], emoji: '✉️', vibe: 'wholesome', tier: 1 },
  { text: 'Rearrange a bookshelf by color. Step back. Feel something. Post the before/after.', tags: ['solo', 'free', 'indoor'], emoji: '📚', vibe: 'wholesome', tier: 1 },
  { text: 'Buy flowers for yourself. You don\'t need a reason. You\'ve been through enough.', tags: ['solo', 'paid', 'outdoor'], emoji: '💐', vibe: 'wholesome', tier: 1 },
  { text: 'Take a pottery class. Make something hideous. Love it unconditionally. Display it.', tags: ['solo', 'paid', 'indoor'], emoji: '🏺', vibe: 'wholesome', tier: 2 },
  { text: 'Go to a random floor of a library. Read the first book your hand touches for 30 minutes.', tags: ['solo', 'free', 'indoor'], emoji: '📕', vibe: 'genius', tier: 1 },
  { text: 'Learn to say "this is a wonderful day" in 7 languages. Use all 7 before bed.', tags: ['solo', 'free', 'indoor'], emoji: '🌐', vibe: 'unhinged', tier: 2 },
  { text: 'Go to a restaurant alone. Order the chef\'s favorite, not yours. Trust the universe.', tags: ['solo', 'paid', 'outdoor'], emoji: '🍽️', vibe: 'genius', tier: 1 },
  { text: 'Walk into a grocery store. Buy only things you\'ve never tried. Cook a mystery dinner. Rate it.', tags: ['solo', 'paid', 'indoor'], emoji: '🛒', vibe: 'genius', tier: 2 },
  { text: 'Spend one hour learning a skill that has zero practical use. Master it anyway.', tags: ['solo', 'free', 'indoor'], emoji: '🎓', vibe: 'unhinged', tier: 1 },
  { text: 'Buy a notebook that costs more than you\'d normally spend. Only write important things in it.', tags: ['solo', 'paid', 'indoor'], emoji: '📓', vibe: 'genius', tier: 1 },
  { text: 'Go to a thrift store. Buy the weirdest mug. It\'s your personality now. No returns.', tags: ['solo', 'paid', 'outdoor'], emoji: '🍵', vibe: 'unhinged', tier: 1 },
  { text: 'Take the scenic route to somewhere boring. See if the journey redeems the destination.', tags: ['solo', 'free', 'outdoor'], emoji: '🛤️', vibe: 'wholesome', tier: 1 },

  // ── PURE AUDACITY ── the ones that make people say "amazing use of free will"
  { text: 'Send a thank you card to a Wikipedia editor. They won\'t know who you are. That\'s the point.', tags: ['solo', 'free', 'indoor'], emoji: '📬', vibe: 'genius', tier: 2 },
  { text: 'Learn to fold one origami animal perfectly. Leave it on a stranger\'s car. No note.', tags: ['solo', 'free', 'outdoor'], emoji: '🦢', vibe: 'genius', tier: 1 },
  { text: 'Go to a park with a sign that says "Free Compliments." Actually follow through.', tags: ['solo', 'free', 'outdoor'], emoji: '🪧', vibe: 'wholesome', tier: 2 },
  { text: 'Narrate your commute as a TED Talk about the human condition. Record it. Don\'t post it. Post it.', tags: ['solo', 'free', 'outdoor'], emoji: '🎤', vibe: 'unhinged', tier: 2 },
  { text: 'Go to a coffee shop. Write a short story in one sitting. Leave it folded on the table when you go.', tags: ['solo', 'paid', 'outdoor'], emoji: '✍️', vibe: 'genius', tier: 2 },
  { text: 'Set an alarm for 3am. Watch the sunrise. Make it the most intentional thing you do this month.', tags: ['solo', 'free', 'outdoor'], emoji: '🌅', vibe: 'genius', tier: 2 },
  { text: 'Send a voice memo to your best friend that\'s just you listing every reason they matter. No warning.', tags: ['solo', 'free', 'indoor'], emoji: '🎧', vibe: 'wholesome', tier: 1 },
  { text: 'Make a zine about something hyper-specific you care about. Staple 10 copies. Distribute them.', tags: ['solo', 'paid', 'indoor'], emoji: '📰', vibe: 'genius', tier: 3 },
  { text: 'Walk into a florist. Ask which flower best represents Tuesday. Buy it. Tell no one why.', tags: ['solo', 'paid', 'outdoor'], emoji: '🌸', vibe: 'unhinged', tier: 1 },
  { text: 'Text everyone in your recent contacts a memory you have with them. No context. Just the memory.', tags: ['solo', 'free', 'indoor'], emoji: '💭', vibe: 'wholesome', tier: 2 },
  { text: 'Go to a farmer\'s market. Buy exactly one of the strangest thing there. Cook dinner around it.', tags: ['solo', 'paid', 'outdoor'], emoji: '🥬', vibe: 'genius', tier: 1 },
  { text: 'Wear something you\'ve been saving "for a special occasion." Today is the occasion. You decided.', tags: ['solo', 'free', 'indoor'], emoji: '👔', vibe: 'genius', tier: 1 },
  { text: 'Host a movie night for films nobody has heard of. Serve snacks that match each film\'s vibe.', tags: ['group', 'paid', 'indoor'], emoji: '🎬', vibe: 'genius', tier: 2 },
  { text: 'Go to a hardware store. Ask an employee which aisle has meaning. Document their response.', tags: ['solo', 'free', 'outdoor'], emoji: '🔨', vibe: 'unhinged', tier: 1 },
  { text: 'Create a gallery wall of your worst photos. Curate them seriously. Invite people to the opening.', tags: ['solo', 'free', 'indoor'], emoji: '🖼️', vibe: 'unhinged', tier: 2 },
  { text: 'Memorize a poem this week. Recite it to someone when the moment is right. You\'ll know when.', tags: ['solo', 'free', 'indoor'], emoji: '📜', vibe: 'genius', tier: 2 },
  { text: 'Make friendship bracelets. You\'re an adult. That makes it better. Give them out with zero irony.', tags: ['solo', 'paid', 'indoor'], emoji: '📿', vibe: 'wholesome', tier: 1 },
  { text: 'Start a neighborhood book club but the only book is the takeout menu from the nearest restaurant.', tags: ['group', 'free', 'outdoor'], emoji: '📕', vibe: 'unhinged', tier: 3 },
  { text: 'Go on a date with yourself. Dress up. Get a table for one. Leave yourself a good review after.', tags: ['solo', 'paid', 'outdoor'], emoji: '🕯️', vibe: 'genius', tier: 2 },
  { text: 'Commission a caricature of yourself. Use it as your LinkedIn photo for a week. Commit fully.', tags: ['solo', 'paid', 'outdoor'], emoji: '🎪', vibe: 'unhinged', tier: 3 },
]

/* ── Filter config ── */
const FILTER_GROUPS = [
  {
    label: 'Who',
    options: [
      { key: 'solo', label: 'Solo', icon: '🧑' },
      { key: 'group', label: 'Crew', icon: '👥' },
    ],
  },
  {
    label: 'Where',
    options: [
      { key: 'indoor', label: 'Indoor', icon: '🏠' },
      { key: 'outdoor', label: 'Outside', icon: '☀️' },
    ],
  },
  {
    label: 'Cost',
    options: [
      { key: 'free', label: 'Free', icon: '✌️' },
      { key: 'paid', label: 'Worth it', icon: '💸' },
    ],
  },
  {
    label: 'Energy',
    options: [
      { key: 'charity', label: 'Kind', icon: '❤️' },
      { key: 'eco', label: 'Eco', icon: '🌍' },
    ],
  },
]

/* ── Vibe styling ── */
const VIBE_META = {
  unhinged: {
    gradient: 'from-rose-500 via-pink-500 to-fuchsia-600',
    glow: 'rgba(244,63,94,0.35)',
    badge: '🫠 beautifully unhinged',
    bg: 'from-rose-500/15 to-fuchsia-500/15',
    border: 'border-rose-500/25',
    canvasBg: ['#1a0a1e', '#2d0a1e'],
    canvasAccent: '#f43f5e',
  },
  genius: {
    gradient: 'from-violet-500 via-purple-500 to-indigo-600',
    glow: 'rgba(139,92,246,0.35)',
    badge: '🧠 lowkey genius',
    bg: 'from-violet-500/15 to-indigo-500/15',
    border: 'border-violet-500/25',
    canvasBg: ['#0f0a2e', '#1a0a2e'],
    canvasAccent: '#8b5cf6',
  },
  wholesome: {
    gradient: 'from-amber-400 via-orange-400 to-yellow-500',
    glow: 'rgba(251,191,36,0.35)',
    badge: '🥹 aggressively wholesome',
    bg: 'from-amber-500/15 to-yellow-500/15',
    border: 'border-amber-500/25',
    canvasBg: ['#1e1405', '#1e1a05'],
    canvasAccent: '#fbbf24',
  },
}

/* ── Tier labels ── */
const TIER_META = {
  1: { label: 'try it now', color: 'text-green-400', border: 'border-green-500/20', desc: '5 min or less' },
  2: { label: 'commit to it', color: 'text-amber-400', border: 'border-amber-500/20', desc: 'set aside an hour' },
  3: { label: 'life event', color: 'text-rose-400', border: 'border-rose-500/20', desc: 'this becomes a story' },
}

/* ── Spin loading messages ── */
const SPIN_WORDS = [
  'Consulting the multiverse...',
  'Channeling chaotic good energy...',
  'Asking the universe politely...',
  'Loading free will.exe...',
  'Rolling the existential dice...',
  'Deploying whimsy...',
  'Calibrating spontaneity...',
  'Summoning audacity...',
  'Contacting your future self...',
  'Scanning for peak human behavior...',
]

const SLOT_EMOJIS = ['🎲', '✨', '🌟', '💫', '🎯', '🔮', '🎪', '🚀', '⚡', '🌈', '🦋', '🌀', '💥', '🫧', '🪄']

export default function FreeWillUtilizer() {
  const [activeFilters, setActiveFilters] = useState(new Set())
  const [current, setCurrent] = useState(null)
  const [isSpinning, setIsSpinning] = useState(false)
  const [slotEmoji, setSlotEmoji] = useState('🎲')
  const [spinWord, setSpinWord] = useState(SPIN_WORDS[0])
  const [history, setHistory] = useState([])
  const [copied, setCopied] = useState(false)
  const [shakeCard, setShakeCard] = useState(false)
  const [totalSpins, setTotalSpins] = useState(0)
  const [accepted, setAccepted] = useState(0)
  const spinRef = useRef(null)

  const [dayStreak, setDayStreak] = useState(0)
  const [lastDay, setLastDay] = useState(null)

  /* ── Load stats from localStorage ── */
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('fwu-stats') || '{}')
      if (saved.spins) setTotalSpins(saved.spins)
      if (saved.accepted) setAccepted(saved.accepted)
      if (saved.streak) setDayStreak(saved.streak)
      if (saved.lastDay) setLastDay(saved.lastDay)

      // Check if streak continues today
      const today = new Date().toDateString()
      if (saved.lastDay) {
        const last = new Date(saved.lastDay)
        const diff = Math.floor((new Date(today) - last) / 86400000)
        if (diff > 1) {
          // Streak broken — reset
          setDayStreak(0)
        }
      }
    } catch { /* */ }
  }, [])

  const saveStats = (spins, acc, streak, day) => {
    try { localStorage.setItem('fwu-stats', JSON.stringify({ spins, accepted: acc, streak, lastDay: day })) } catch { /* */ }
  }

  const toggleFilter = (key) => {
    setActiveFilters((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  const getPool = useCallback(() => {
    if (activeFilters.size === 0) return CHALLENGES
    return CHALLENGES.filter((a) =>
      [...activeFilters].every((f) => a.tags.includes(f))
    )
  }, [activeFilters])

  const poolSize = getPool().length

  const spin = useCallback(() => {
    const pool = getPool()
    if (!pool.length) {
      setShakeCard(true)
      setTimeout(() => setShakeCard(false), 600)
      return
    }

    setIsSpinning(true)
    setSpinWord(SPIN_WORDS[Math.floor(Math.random() * SPIN_WORDS.length)])

    let tick = 0
    spinRef.current = setInterval(() => {
      setSlotEmoji(SLOT_EMOJIS[Math.floor(Math.random() * SLOT_EMOJIS.length)])
      tick++
      if (tick > 14) clearInterval(spinRef.current)
    }, 70)

    setTimeout(() => {
      const pick = pool[Math.floor(Math.random() * pool.length)]
      setCurrent(pick)
      setSlotEmoji(pick.emoji)
      setIsSpinning(false)
      setHistory((prev) => [pick, ...prev.filter((h) => h.text !== pick.text)].slice(0, 12))
      fireConfetti()
      const newSpins = totalSpins + 1
      setTotalSpins(newSpins)

      // Update day streak
      const today = new Date().toDateString()
      let newStreak = dayStreak
      if (lastDay !== today) {
        const last = lastDay ? new Date(lastDay) : null
        const diff = last ? Math.floor((new Date(today) - last) / 86400000) : 999
        newStreak = diff <= 1 ? dayStreak + 1 : 1
        setDayStreak(newStreak)
        setLastDay(today)
      }

      saveStats(newSpins, accepted, newStreak, today)
    }, 1200)
  }, [getPool, totalSpins, accepted, dayStreak, lastDay])

  useEffect(() => () => { if (spinRef.current) clearInterval(spinRef.current) }, [])

  const acceptChallenge = () => {
    const newAcc = accepted + 1
    setAccepted(newAcc)
    saveStats(totalSpins, newAcc, dayStreak, lastDay)
  }

  const vibe = current ? VIBE_META[current.vibe] : null
  const tier = current ? TIER_META[current.tier] : null

  /* ── Share text — uses the actual meme format ── */
  const dayLabel = dayStreak > 0 ? `Day ${dayStreak} of using my free will:` : 'When I remembered I have free will:'
  const shareText = current
    ? `${dayLabel}\n\n${current.text}\n\namazing use of free will ✦`
    : ''

  const tweetUrl = () => `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}`

  const copyText = async () => {
    try {
      await navigator.clipboard.writeText(shareText)
      setCopied(true)
      setTimeout(() => setCopied(false), 2200)
    } catch { /* */ }
  }

  /* ── Canvas share card (1080x1350, IG story) ── */
  const downloadShareCard = useCallback(() => {
    if (!current) return
    const v = VIBE_META[current.vibe]
    const t = TIER_META[current.tier]
    const W = 1080, H = 1350
    const c = document.createElement('canvas')
    c.width = W; c.height = H
    const ctx = c.getContext('2d')

    // Background gradient
    const bg = ctx.createLinearGradient(0, 0, W, H)
    bg.addColorStop(0, v.canvasBg[0]); bg.addColorStop(1, v.canvasBg[1])
    ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H)

    // Subtle grid pattern
    ctx.strokeStyle = 'rgba(255,255,255,0.015)'
    ctx.lineWidth = 1
    for (let x = 0; x < W; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke() }
    for (let y = 0; y < H; y += 40) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke() }

    // Large glow circle
    const grd = ctx.createRadialGradient(W / 2, H * 0.36, 0, W / 2, H * 0.36, 420)
    grd.addColorStop(0, v.glow); grd.addColorStop(0.6, v.glow.replace('0.35', '0.08')); grd.addColorStop(1, 'transparent')
    ctx.fillStyle = grd; ctx.fillRect(0, 0, W, H)

    // Top label — uses the meme format
    ctx.fillStyle = 'rgba(255,255,255,0.3)'
    ctx.font = '500 18px -apple-system, system-ui, sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText('✦  FREE WILL UTILIZER  ✦', W / 2, 70)

    // Day streak label
    ctx.fillStyle = 'rgba(255,255,255,0.5)'
    ctx.font = '400 26px -apple-system, system-ui, sans-serif'
    const dayText = dayStreak > 0 ? `Day ${dayStreak} of using my free will` : 'When I remembered I have free will'
    ctx.fillText(dayText, W / 2, 120)

    // Emoji
    ctx.font = '140px serif'
    ctx.fillText(current.emoji, W / 2, H * 0.3 + 20)

    // Activity text — word wrap
    ctx.fillStyle = '#f5f5f5'
    ctx.font = 'bold 44px -apple-system, system-ui, sans-serif'
    const words = current.text.split(' ')
    let lines = [], line = ''
    for (const w of words) {
      const test = line ? line + ' ' + w : w
      if (ctx.measureText(test).width > W - 180) { lines.push(line); line = w }
      else line = test
    }
    if (line) lines.push(line)
    const lineH = 60
    const textY = H * 0.43
    lines.forEach((l, i) => ctx.fillText(l, W / 2, textY + i * lineH))

    // Vibe + tier badges
    const badgeY = textY + lines.length * lineH + 45
    ctx.fillStyle = 'rgba(255,255,255,0.4)'
    ctx.font = '500 24px -apple-system, system-ui, sans-serif'
    ctx.fillText(`${v.badge}  ·  ${t.label}`, W / 2, badgeY)

    // Divider
    const divY = H * 0.74
    ctx.strokeStyle = 'rgba(255,255,255,0.08)'
    ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(W * 0.15, divY); ctx.lineTo(W * 0.85, divY); ctx.stroke()

    // "amazing use of free will"
    ctx.fillStyle = '#e5e5e5'
    ctx.font = 'italic 36px Georgia, "Times New Roman", serif'
    ctx.fillText('"amazing use of free will"', W / 2, divY + 65)

    // Accent line at bottom
    const accentGrd = ctx.createLinearGradient(W * 0.2, 0, W * 0.8, 0)
    accentGrd.addColorStop(0, 'transparent')
    accentGrd.addColorStop(0.5, v.canvasAccent)
    accentGrd.addColorStop(1, 'transparent')
    ctx.strokeStyle = accentGrd
    ctx.lineWidth = 2
    ctx.beginPath(); ctx.moveTo(W * 0.2, H - 110); ctx.lineTo(W * 0.8, H - 110); ctx.stroke()

    // Footer
    ctx.fillStyle = 'rgba(255,255,255,0.2)'
    ctx.font = '400 20px -apple-system, system-ui, sans-serif'
    ctx.fillText('freewillutilizer.com', W / 2, H - 65)

    // Download
    const link = document.createElement('a')
    link.download = 'amazing-use-of-free-will.png'
    link.href = c.toDataURL('image/png')
    link.click()
  }, [current, dayStreak])

  return (
    <div className="min-h-screen bg-[#08080d] text-neutral-100 overflow-x-hidden selection:bg-purple-500/30">
      {/* Ambient background */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-48 -left-48 w-[500px] h-[500px] bg-purple-600/[0.05] rounded-full blur-[120px]" />
        <div className="absolute top-1/2 -right-32 w-96 h-96 bg-rose-600/[0.04] rounded-full blur-[120px]" />
        <div className="absolute -bottom-32 left-1/4 w-80 h-80 bg-amber-600/[0.03] rounded-full blur-[120px]" />
        {/* Subtle grid */}
        <div className="absolute inset-0 opacity-[0.015]" style={{
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
          backgroundSize: '60px 60px'
        }} />
      </div>

      <div className="relative z-10 max-w-xl mx-auto px-5">

        {/* ── Header ── */}
        <header className="pt-10 pb-6 text-center">
          <p className="text-[10px] font-semibold tracking-[0.3em] uppercase text-neutral-700 mb-4">
            ✦ you have free will ✦ might as well use it ✦
          </p>
          <h1 className="text-5xl sm:text-6xl font-black tracking-tight leading-[1.05] mb-3">
            <span className="bg-gradient-to-r from-purple-400 via-pink-400 to-amber-300 bg-clip-text text-transparent">
              Free Will
            </span>
            <br />
            <span className="text-neutral-300 text-4xl sm:text-5xl font-extrabold">Utilizer</span>
          </h1>
          <p className="text-[13px] text-neutral-600 max-w-xs mx-auto leading-relaxed">
            Wildly creative things you can actually do.
          </p>
          <p className="text-[13px] text-neutral-500 mt-1 italic">
            The kind where people comment <span className="text-neutral-300">&quot;amazing use of free will&quot;</span>
          </p>
        </header>

        {/* ── Stats bar ── */}
        {totalSpins > 0 && (
          <div className="flex items-center justify-center gap-4 sm:gap-6 mb-6 text-[11px] text-neutral-700 flex-wrap">
            {dayStreak > 0 && (
              <>
                <span className="text-purple-400 font-semibold">🔥 Day {dayStreak}</span>
                <span className="w-px h-3 bg-neutral-800" />
              </>
            )}
            <span>🎲 {totalSpins} spin{totalSpins !== 1 ? 's' : ''}</span>
            <span className="w-px h-3 bg-neutral-800" />
            <span>✅ {accepted} accepted</span>
            <span className="w-px h-3 bg-neutral-800" />
            <span>{Math.round((accepted / Math.max(totalSpins, 1)) * 100)}% commit rate</span>
          </div>
        )}

        {/* ── Filters ── */}
        <section className="mb-7">
          <div className="bg-white/[0.025] border border-white/[0.05] rounded-2xl p-4 backdrop-blur-sm">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-semibold tracking-[0.2em] uppercase text-neutral-700">Dial it in</span>
              {activeFilters.size > 0 && (
                <button onClick={() => setActiveFilters(new Set())} className="text-[10px] text-neutral-700 hover:text-neutral-400 transition">
                  Clear
                </button>
              )}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {FILTER_GROUPS.map((g) => (
                <div key={g.label} className="space-y-1.5">
                  <div className="text-[10px] font-medium text-neutral-700 pl-0.5">{g.label}</div>
                  {g.options.map((o) => {
                    const on = activeFilters.has(o.key)
                    return (
                      <button
                        key={o.key}
                        onClick={() => toggleFilter(o.key)}
                        className={`w-full flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium transition-all duration-200 ${
                          on
                            ? 'bg-purple-500/15 border border-purple-400/25 text-purple-300'
                            : 'bg-white/[0.025] border border-white/[0.05] text-neutral-500 hover:bg-white/[0.05] hover:text-neutral-300'
                        }`}
                      >
                        <span className="text-sm">{o.icon}</span>
                        <span>{o.label}</span>
                      </button>
                    )
                  })}
                </div>
              ))}
            </div>
            <p className="mt-2.5 text-center text-[10px] text-neutral-700">
              {poolSize} challenge{poolSize !== 1 ? 's' : ''} loaded
            </p>
          </div>
        </section>

        {/* ── Main card ── */}
        <section className="mb-5">
          <div
            className={`relative rounded-3xl border min-h-[300px] sm:min-h-[340px] flex flex-col items-center justify-center p-7 sm:p-10 text-center transition-all duration-700 ${
              current && !isSpinning
                ? `bg-gradient-to-br ${vibe.bg} ${vibe.border}`
                : 'bg-white/[0.015] border-white/[0.05]'
            }`}
            style={{
              animation: shakeCard ? 'shake 0.6s ease' : isSpinning ? 'pulse-glow 0.35s ease infinite alternate' : 'none',
              boxShadow: current && !isSpinning ? `0 0 80px ${vibe.glow.replace('0.35', '0.1')}` : 'none',
            }}
          >
            {isSpinning ? (
              <div className="flex flex-col items-center gap-5">
                <div className="text-7xl sm:text-8xl" style={{ animation: 'spin-wobble 0.4s ease infinite' }}>{slotEmoji}</div>
                <div className="flex gap-1.5">
                  {[0, 1, 2, 3].map((i) => (
                    <div key={i} className="w-1.5 h-1.5 rounded-full bg-purple-400/60" style={{ animation: `dot-bounce 0.5s ease ${i * 0.1}s infinite alternate` }} />
                  ))}
                </div>
                <p className="text-xs text-neutral-600 italic">{spinWord}</p>
              </div>
            ) : current ? (
              <div className="flex flex-col items-center gap-4" style={{ animation: 'card-reveal 0.6s cubic-bezier(0.16,1,0.3,1)' }}>
                <div className="text-6xl sm:text-7xl">{current.emoji}</div>
                <p className="text-[17px] sm:text-xl font-bold leading-snug text-neutral-100 max-w-sm">
                  {current.text}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <span className={`text-[10px] font-semibold tracking-wide px-2.5 py-1 rounded-full ${vibe.border} bg-black/30 text-neutral-400`}>
                    {vibe.badge}
                  </span>
                  <span className={`text-[10px] font-semibold tracking-wide px-2.5 py-1 rounded-full ${tier.border} bg-black/30 ${tier.color}`}>
                    {tier.label}
                  </span>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <div className="text-6xl opacity-[0.15]" style={{ animation: 'float 3s ease-in-out infinite' }}>🎲</div>
                <p className="text-sm text-neutral-600">Your next amazing use of free will</p>
                <p className="text-[11px] text-neutral-800">is one tap away ↓</p>
              </div>
            )}
          </div>
        </section>

        {/* ── Action buttons ── */}
        <div className="flex flex-col items-center gap-3 mb-7">
          {/* Spin button */}
          <button
            onClick={spin}
            disabled={isSpinning}
            className={`relative px-10 py-4 rounded-2xl font-bold text-base transition-all duration-300 ${
              isSpinning
                ? 'bg-neutral-900 text-neutral-700 cursor-wait'
                : poolSize === 0
                ? 'bg-neutral-900 text-neutral-700 cursor-not-allowed'
                : 'bg-gradient-to-r from-purple-600 via-pink-600 to-purple-600 bg-[length:200%_100%] text-white shadow-[0_4px_30px_rgba(168,85,247,0.25)] hover:shadow-[0_4px_40px_rgba(168,85,247,0.4)] hover:scale-[1.03] active:scale-[0.97]'
            }`}
            style={!isSpinning && poolSize > 0 ? { animation: 'shimmer 3s ease infinite' } : {}}
          >
            {isSpinning
              ? '✨ Spinning...'
              : current
              ? '🎲 Spin Again'
              : poolSize === 0
              ? 'No challenges match'
              : '🎲 Use Your Free Will'}
          </button>

          {/* Accept challenge button */}
          {current && !isSpinning && (
            <button
              onClick={acceptChallenge}
              className="px-6 py-2.5 rounded-xl text-sm font-semibold bg-white/[0.06] border border-white/[0.1] text-neutral-300 hover:bg-white/[0.1] hover:text-white transition-all active:scale-[0.97]"
              style={{ animation: 'card-reveal 0.3s ease' }}
            >
              ✅ Challenge Accepted
            </button>
          )}
        </div>

        {/* ── Share section ── */}
        {current && !isSpinning && (
          <section className="mb-8" style={{ animation: 'card-reveal 0.4s ease' }}>
            <div className="bg-white/[0.02] border border-white/[0.04] rounded-2xl p-5">
              <p className="text-[10px] font-semibold tracking-[0.2em] uppercase text-neutral-700 mb-4 text-center">
                Share it. Do it. Let them comment.
              </p>

              <div className="flex flex-wrap gap-2 justify-center mb-4">
                <a
                  href={tweetUrl()}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-sm font-medium text-neutral-400 hover:bg-white/[0.07] hover:text-white transition-all"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                  Post
                </a>

                <button
                  onClick={downloadShareCard}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-sm font-medium text-neutral-400 hover:bg-white/[0.07] hover:text-white transition-all"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="18" cy="6" r="1.5"/></svg>
                  Story Card
                </button>

                <button
                  onClick={copyText}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-sm font-medium text-neutral-400 hover:bg-white/[0.07] hover:text-white transition-all"
                >
                  {copied ? '✅ Copied!' : '📋 Copy'}
                </button>

                <button
                  onClick={() => {
                    if (typeof navigator !== 'undefined' && navigator.share) {
                      navigator.share({ text: shareText }).catch(() => {})
                    }
                  }}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-sm font-medium text-neutral-400 hover:bg-white/[0.07] hover:text-white transition-all sm:hidden"
                >
                  📤 Share
                </button>
              </div>

              {/* Screenshot-friendly preview — uses the actual meme format */}
              <div className="bg-[#0c0c14] border border-white/[0.06] rounded-xl p-6 text-center">
                <p className="text-xs text-neutral-500 mb-2">
                  {dayStreak > 0 ? `Day ${dayStreak} of using my free will:` : 'When I remembered I have free will:'}
                </p>
                <p className="text-[15px] text-neutral-200 font-semibold leading-relaxed mb-3">
                  {current.text}
                </p>
                <div className="flex items-center justify-center gap-2 mb-2">
                  <span className="text-[10px] text-neutral-500">{vibe.badge}</span>
                  <span className="text-neutral-800">·</span>
                  <span className={`text-[10px] ${tier.color}`}>{tier.label}</span>
                </div>
                <p className="text-[11px] text-neutral-600 italic">amazing use of free will ✦</p>
              </div>
            </div>
          </section>
        )}

        {/* ── History ── */}
        {history.length > 1 && (
          <section className="mb-10">
            <p className="text-[10px] font-semibold tracking-[0.2em] uppercase text-neutral-700 mb-3">
              Free will log
            </p>
            <div className="space-y-1.5">
              {history.slice(1).map((item, i) => (
                <button
                  key={item.text}
                  onClick={() => { setCurrent(item) }}
                  className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl bg-white/[0.015] border border-white/[0.03] text-sm text-neutral-600 text-left hover:bg-white/[0.04] transition-colors"
                  style={{ opacity: 1 - i * 0.06 }}
                >
                  <span className="text-base flex-shrink-0">{item.emoji}</span>
                  <span className="truncate flex-1">{item.text}</span>
                  <span className="text-[10px] flex-shrink-0 text-neutral-800">{VIBE_META[item.vibe].badge.split(' ')[0]}</span>
                </button>
              ))}
            </div>
          </section>
        )}

        {/* ── Footer ── */}
        <footer className="pb-14 text-center border-t border-white/[0.03] pt-8">
          <p className="text-[11px] text-neutral-800 leading-relaxed max-w-xs mx-auto mb-2">
            ~2.5 billion seconds in a life. You just used one to decide how to spend the next few thousand.
          </p>
          <p className="text-[10px] text-neutral-900">
            ✦ built with free will ✦
          </p>
        </footer>
      </div>

      {/* ── Keyframes ── */}
      <style jsx>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0) rotate(0); }
          15% { transform: translateX(-10px) rotate(-2deg); }
          30% { transform: translateX(10px) rotate(2deg); }
          45% { transform: translateX(-6px) rotate(-1deg); }
          60% { transform: translateX(6px) rotate(1deg); }
          75% { transform: translateX(-2px) rotate(-0.5deg); }
        }
        @keyframes card-reveal {
          from { opacity: 0; transform: translateY(16px) scale(0.97); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes pulse-glow {
          from { box-shadow: 0 0 30px rgba(168, 85, 247, 0.06); }
          to { box-shadow: 0 0 60px rgba(168, 85, 247, 0.18); }
        }
        @keyframes dot-bounce {
          from { transform: translateY(0); opacity: 0.4; }
          to { transform: translateY(-8px); opacity: 1; }
        }
        @keyframes spin-wobble {
          0% { transform: rotate(0) scale(1); }
          25% { transform: rotate(10deg) scale(1.08); }
          50% { transform: rotate(-10deg) scale(0.92); }
          75% { transform: rotate(5deg) scale(1.03); }
          100% { transform: rotate(0) scale(1); }
        }
        @keyframes float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-10px); }
        }
        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </div>
  )
}
