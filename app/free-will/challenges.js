/* ─────────────────────────────────────────────
   The list. Edit here, nothing else needs to change.

   The bar every entry has to clear:
   1. It's a twist on something you'd do anyway (a trip, dinner,
      a walk, a hangout) that makes it a different experience.
   2. It's actually fun to do, not just "lol random".
   3. You'd want to post what comes out of it.
   4. It's cheap and low effort. No big spends, no homework.

   Format: c(text, tags, emoji, vibe, tier)
   tags: solo | group, home | out, free | paid (list both when either works)
   vibe: unhinged | genius | wholesome
   tier: 1 right now, 2 make a plan, 3 whole day or trip
   ───────────────────────────────────────────── */
const TAG = { home: 'indoor', out: 'outdoor' }
const c = (text, tags, emoji, vibe, tier) => ({ text, tags: tags.split(' ').map(t => TAG[t] || t), emoji, vibe, tier })

export const CHALLENGES = [
  // ── with people ──
  c("Next trip, everyone picks a color. Only photograph things in your color. Compare at dinner.", 'group out free', '🎨', 'genius', 3),
  c("Bring one disposable camera to the hangout. Pass it around. Nobody sees a photo until it's developed.", 'group home out paid', '📷', 'genius', 2),
  c("Everyone sends $5 to one person. They plan the whole night on that budget.", 'group home out paid', '💸', 'unhinged', 2),
  c("Dinner out. Everyone orders for the person on their left. No hints.", 'group out paid', '🍽️', 'unhinged', 2),
  c("Convenience store dinner. $7 each, three courses. Plate them and judge.", 'group home out paid', '🏪', 'genius', 2),
  c("Go bowling. Loser gives a 3-minute acceptance speech thanking everyone for the loss.", 'group out paid', '🎳', 'unhinged', 2),
  c("Movie night with a movie nobody's seen. Pause it halfway. Everyone writes the ending.", 'group home free', '🍿', 'genius', 2),
  c("Everyone photographs the same thing. Compare. Best shot picks dinner.", 'group out free', '📸', 'genius', 1),
  c("Thrift store. $5 each. Buy one piece for the person next to you. They wear it out tonight.", 'group out paid', '🧥', 'unhinged', 2),
  c("Potluck, but everyone brings the thing they ate most as a kid.", 'group home paid', '🍛', 'wholesome', 2),
  c("Color potluck. Everyone gets a color and brings only snacks in that color.", 'group home paid', '🌈', 'genius', 2),
  c("Everyone overdresses for the most casual plan this week. Formal wear, fast food.", 'group out paid', '🤵', 'unhinged', 2),
  c("Museum trip. Find the painting that looks most like each person in the group. Post the side-by-sides.", 'group out paid', '🖼️', 'unhinged', 2),
  c("Bookstore run. Pick a book for each other by the cover alone. No reading the back.", 'group out paid', '📚', 'genius', 2),
  c("Farmers market. Everyone picks one ingredient without telling. Make one dish out of all of them.", 'group home out paid', '🥬', 'genius', 2),
  c("Everyone adds five songs to one playlist. That's the only music for the whole trip.", 'group out free', '🎶', 'wholesome', 3),
  c("Day trip where everyone plans exactly one hour and keeps it a secret.", 'group out paid', '🗺️', 'genius', 3),
  c("Next trip, everyone scores every stop out of 10 in a shared note. Read the scores on the way home.", 'group out free', '🔟', 'genius', 3),
  c("Outfit swap. Style each other from each other's closets. Go out like that.", 'group home free', '👗', 'unhinged', 2),
  c("Sit somewhere with a view. Everyone gets five minutes to draw it. Compare.", 'group out free', '✏️', 'wholesome', 1),
  c("International grocery store. Everyone picks one snack they've never seen. Taste test, score out of 10.", 'group out paid', '🛒', 'genius', 2),
  c("Everyone teaches the group one skill in exactly five minutes. Timer is law.", 'group home free', '⏱️', 'genius', 2),
  c("Same recipe, two kitchens. Cook it together on FaceTime. Compare plates.", 'group home paid', '🧑‍🍳', 'wholesome', 2),
  c("On your next night out, everyone gets exactly one photo. Choose your moment. Compare tomorrow.", 'group out free', '🎞️', 'genius', 2),
  c("Everyone shows up to dinner dressed as a different decade.", 'group home out free', '🕺', 'unhinged', 2),

  // ── solo, or bring someone ──
  c("Pay for the coffee of the person behind you. Ask the barista to tell them to pass it on.", 'solo out paid', '☕', 'wholesome', 1),
  c("Finally eat at the place you've walked past a hundred times. Order what they recommend. Post it and tag them.", 'solo group out paid', '🍜', 'wholesome', 2),
  c("Shuffle your playlist. The first song sets the vibe for the whole night.", 'solo group home out free', '🎧', 'unhinged', 1),
  c("One photo a day at exactly 3:33pm for a week. Wherever you are. Post all seven.", 'solo home out free', '🕞', 'genius', 2),
  c("Ask the barista to make whatever they wish people would order. Tip well.", 'solo out paid', '🧋', 'wholesome', 1),
  c("Wear the thing you've been saving for a special occasion. Today is the occasion.", 'solo home out free', '👔', 'genius', 1),
  c("Take the long way home. One photo of the best thing you pass.", 'solo out free', '🚶', 'wholesome', 1),
  c("Alphabet walk. Photograph something for every letter, A to Z, before you get home.", 'solo group out free', '🔤', 'genius', 2),
  c("Rate everything you do today out of 10 in your notes app. Post the list tonight.", 'solo home out free', '📝', 'unhinged', 1),
  c("Film your most boring errand today like it's a travel vlog.", 'solo out free', '🎬', 'unhinged', 1),
  c("Give a tour of your place like it's a $4 million listing. Use the voice.", 'solo home free', '🏠', 'unhinged', 1),
  c("Dinner from only what's already in your kitchen. Plate it like a restaurant.", 'solo home free', '🍳', 'genius', 1),
  c("Watch whatever movie the last person you texted picks. No vetoes.", 'solo home free', '📺', 'unhinged', 2),
  c("Watch tonight's sunset from somewhere you've never watched one.", 'solo group out free', '🌇', 'wholesome', 1),
  c("Pick a direction and walk twenty minutes. Eat at whatever you find.", 'solo group out paid', '🧭', 'genius', 2),
  c("New neighborhood, no maps. Ask one local where to eat. Go there.", 'solo group out paid', '📍', 'genius', 2),
  c("Get the same thing from three different places. Fries, boba, whatever. Rank them.", 'solo group out paid', '🍟', 'genius', 2),
  c("Swap playlists with a friend for a week. No skips.", 'solo home out free', '🔁', 'wholesome', 2),
  c("Order from the delivery spot near you with the fewest reviews. If it's good, leave them one.", 'solo group home paid', '🥡', 'wholesome', 1),
  c("Buy every flavor of one snack. Blind rank them.", 'solo group home out paid', '🍫', 'genius', 1),
  c("Take a disposable camera on your next trip. Phone stays in your pocket.", 'solo group out paid', '🏝️', 'genius', 3),
  c("Be a tourist in your own city for a day. Do the three things you always tell visitors to do.", 'solo group out paid', '🗽', 'wholesome', 3),
]
