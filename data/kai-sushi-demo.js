// Sample dashboard data for KAI Sushi & Roll (Orange, CA).
//
// PUBLIC LISTING INFO — taken from search-result summaries of the restaurant's
// own site (kaisushiorange.com) and its Yelp / Google / delivery-app listings,
// collected mid-2026. The listing pages themselves could not be opened, so
// re-check anything here before showing it to the owner:
//   SHOP_INFO, LISTINGS, MENU
//
// MADE UP FOR THE DEMO — not real activity at this restaurant:
//   ORDERS, RESERVATIONS_*, SAMPLE_REVIEWS, MESSAGES_SENT

export const SHOP_INFO = {
  name: 'KAI Sushi & Roll',
  address: '1448 E Lincoln Ave, Orange, CA 92865',
  phone: '(714) 637-3369',
  // The restaurant's site lists 9:30 PM closing; Yelp lists 9:00 PM.
  hours: 'Mon–Sat 11:00 AM – 9:30 PM',
  lunchHours: '11:00 AM – 3:00 PM',
  closedDay: 'Sunday',
}

export const LISTINGS = [
  { name: 'Yelp', detail: '468 reviews', color: '#D32323' },
  { name: 'Google', detail: '4.3★ average', color: '#4285F4' },
  { name: 'DoorDash', detail: 'Listed for delivery', color: '#FF3008' },
  { name: 'Uber Eats', detail: 'Listed for delivery', color: '#06C167' },
]

export const TABS = [
  { key: 'Today', icon: '📊' },
  { key: 'Orders', icon: '🛵' },
  { key: 'Reservations', icon: '📅' },
  { key: 'My Shop', icon: '🏪' },
  { key: 'Reviews', icon: '⭐' },
  { key: 'Messages', icon: '💬' },
]

export const PLATFORMS = {
  DoorDash: { color: '#FF3008', label: 'DoorDash' },
  UberEats: { color: '#06C167', label: 'Uber Eats' },
  'Walk-in': { color: '#3B82F6', label: 'Walk-in' },
  Phone: { color: '#F59E0B', label: 'Phone' },
}

// Prices as shown on the restaurant's delivery-app listing; in-store prices may differ.
export const MENU = [
  { category: 'Appetizers', items: [
    { name: 'Edamame', price: 6.95 },
    { name: 'Spicy Garlic Edamame', price: 8.95 },
    { name: 'Gyoza (8pc)', price: 12.95 },
    { name: 'Shrimp Tempura (8pc)', price: 14.95 },
    { name: 'Miso Soup', price: 2.95 },
  ]},
  { category: 'Regular Rolls', items: [
    { name: 'California Roll', price: 8.95 },
    { name: 'Spicy California Roll', price: 9.95 },
    { name: 'California Roll (Deep Fried)', price: 10.95 },
    { name: 'Salmon Cut Roll', price: 11.95 },
  ]},
  { category: 'Special Rolls', items: [
    { name: 'House Special Roll', price: 18.95, desc: 'Seared albacore & crab meat with spicy tuna and green onion' },
    { name: 'Rainbow Roll', price: 16.95 },
    { name: 'Dragon Roll', price: 16.95 },
    { name: 'Sushi Burrito', price: 19.95, desc: 'Generous portion wrapped in soy paper' },
    { name: 'Tiger Woods Roll', price: 19.95 },
    { name: 'Ninja Roll', price: 16.95 },
    { name: 'Sunshine Roll', price: 16.95 },
    { name: 'Chicago Roll', price: 19.95 },
    { name: 'Krunch Roll', price: 12.95 },
    { name: 'Hot Night Roll', price: 15.95 },
    { name: 'Miami Vice Roll', price: 17.95 },
  ]},
  { category: 'Sushi, Sashimi & Combos', items: [
    { name: 'Salmon Sushi', price: 7.95 },
    { name: 'Salmon Sashimi', price: 15.95 },
    { name: 'Sushi & Hand Roll Combo', price: 19.99, desc: '4pc assorted sushi, spicy tuna hand roll, California hand roll, miso soup' },
    { name: 'Bento Box', price: 24.95 },
  ]},
]

const PRICE = Object.fromEntries(MENU.flatMap(c => c.items).map(i => [i.name, i.price]))

// Builds a sample order from [name, qty] pairs so totals always match the menu.
function order(id, time, platform, customer, status, lines) {
  for (const [name] of lines) {
    if (!(name in PRICE)) throw new Error(`Sample order uses an item that is not on the menu: ${name}`)
  }
  return {
    id, time, platform, customer, status,
    items: lines.map(([name, qty]) => (qty > 1 ? `${name} × ${qty}` : name)).join(', '),
    amount: Math.round(lines.reduce((sum, [name, qty]) => sum + PRICE[name] * qty, 0) * 100) / 100,
  }
}

export const ORDERS = [
  order(1, '2:45 PM', 'DoorDash', 'Mike T.', 'Preparing', [['Dragon Roll', 1], ['Edamame', 1]]),
  order(2, '2:32 PM', 'UberEats', 'Lisa K.', 'Ready', [['House Special Roll', 1], ['Miso Soup', 1]]),
  order(3, '2:15 PM', 'Walk-in', 'Table 4', 'Done', [['Rainbow Roll', 1], ['Salmon Sashimi', 1], ['Gyoza (8pc)', 1]]),
  order(4, '1:50 PM', 'DoorDash', 'Sarah L.', 'Done', [['Tiger Woods Roll', 1], ['Spicy Garlic Edamame', 1]]),
  order(5, '1:30 PM', 'Phone', 'James W.', 'Done', [['Bento Box', 1], ['California Roll', 1]]),
  order(6, '1:05 PM', 'UberEats', 'Amy C.', 'Done', [['Sushi Burrito', 1], ['Miso Soup', 1]]),
  order(7, '12:40 PM', 'Walk-in', 'Table 2', 'Done', [['Chicago Roll', 1], ['Ninja Roll', 1], ['Edamame', 2]]),
  order(8, '12:15 PM', 'DoorDash', 'Kevin P.', 'Done', [['Krunch Roll', 1], ['Shrimp Tempura (8pc)', 1]]),
  order(9, '11:50 AM', 'Walk-in', 'Table 6', 'Done', [['Sushi & Hand Roll Combo', 2]]),
  order(10, '11:30 AM', 'Phone', 'Diana R.', 'Done', [['Miami Vice Roll', 1], ['Sunshine Roll', 1], ['Edamame', 1]]),
]

export const RESERVATIONS_TODAY = [
  { id: 1, time: '5:30 PM', name: 'Kim Family', phone: '(714) ***-8421', size: 4, request: 'Birthday celebration', status: 'Confirmed' },
  { id: 2, time: '6:00 PM', name: 'Nguyen', phone: '(949) ***-3105', size: 2, request: '', status: 'Confirmed' },
  { id: 3, time: '6:30 PM', name: 'Park Group', phone: '(714) ***-7792', size: 6, request: 'Sushi platter for the table please', status: 'Confirmed' },
  { id: 4, time: '7:00 PM', name: 'Chen', phone: '(562) ***-2248', size: 3, request: 'Allergic to shellfish', status: 'Pending' },
  { id: 5, time: '7:30 PM', name: 'Rodriguez', phone: '(714) ***-6634', size: 2, request: '', status: 'Confirmed' },
  { id: 6, time: '8:00 PM', name: 'Lee', phone: '(949) ***-1187', size: 5, request: 'Window seat if possible', status: 'Confirmed' },
]

export const RESERVATIONS_TOMORROW = [
  { id: 7, time: '11:30 AM', name: 'Office lunch (12)', phone: '(714) ***-5501', size: 12, request: 'Lunch meeting, need separate checks', status: 'Confirmed' },
  { id: 8, time: '5:00 PM', name: 'Johnson', phone: '(949) ***-9923', size: 4, request: '', status: 'Pending' },
  { id: 9, time: '6:00 PM', name: 'Tanaka', phone: '(714) ***-4478', size: 2, request: 'Anniversary dinner', status: 'Confirmed' },
  { id: 10, time: '7:00 PM', name: 'Garcia', phone: '(562) ***-8856', size: 6, request: '', status: 'Confirmed' },
]

// Written for this demo. They echo themes that come up in the restaurant's
// public reviews (fresh fish, friendly family owners, fair prices, a wait at
// peak hours with one chef) but are NOT real customer reviews or owner replies.
export const SAMPLE_REVIEWS = [
  {
    id: 1, stars: 5,
    text: 'The Dragon Roll and House Special were fresh, generous and beautifully presented. You can tell the family running the place cares about every dish.',
    reply: 'Thank you so much! We put our heart into every roll. Hope to see you again soon!',
  },
  {
    id: 2, stars: 5,
    text: 'Great neighborhood spot. Everything is made fresh to order and the owners are so welcoming. Clean, cozy and fairly priced.',
    reply: null,
  },
  {
    id: 3, stars: 4,
    text: 'Great sushi at fair prices. The Rainbow Roll was fresh. Only four stars because of the wait — there is one chef, so at peak hours it can take a while. Worth it though!',
    reply: null,
    aiSuggestion: 'Thank you for the kind words and for your patience! Everything is made fresh to order, so peak hours can take a little longer. We’re working on shortening the wait and hope to see you again soon.',
  },
  {
    id: 4, stars: 5,
    text: 'Brought my parents for dinner and they loved it. The Shrimp Tempura was crispy and the Sushi Burrito is huge.',
    reply: 'So happy your family enjoyed everything! Thank you for dining with us.',
  },
  {
    id: 5, stars: 3,
    text: 'Food was good but it took a while. The California Roll and Edamame were solid. Wish there was more seating — it’s a small spot.',
    reply: null,
  },
]

export const MESSAGES_SENT = [
  { date: 'Nov 10', type: '🚫 Closed', title: 'Closed Thursday, Nov 26 for Thanksgiving', recipients: 312 },
  { date: 'Nov 3', type: '🎉 Special', title: '10% off all Special Rolls this weekend', recipients: 312 },
  { date: 'Oct 24', type: '🆕 New Item', title: 'Now serving Spicy Garlic Edamame', recipients: 287 },
]

export const MESSAGE_TEMPLATES = [
  { icon: '🎉', label: 'Special / Promo', desc: 'Announce deals, happy hour, seasonal specials' },
  { icon: '🚫', label: 'Closed / Hours', desc: 'Holiday closures and adjusted hours' },
  { icon: '🆕', label: 'New Item', desc: 'Let regulars know about new menu additions' },
  { icon: '📅', label: 'Reservation Reminder', desc: 'Remind guests about upcoming reservations' },
]
