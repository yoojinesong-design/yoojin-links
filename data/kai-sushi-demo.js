// Real data for KAI Sushi & Roll — 1448 E Lincoln Ave, Orange, CA 92865
// Sources: kaisushiorange.com, Yelp (468 reviews, 4.4★), Google (4.3★),
// DoorDash, Uber Eats, OpenTable, RestaurantGuru

export const SHOP_INFO = {
  name: 'KAI Sushi & Roll',
  address: '1448 E Lincoln Ave, Orange, CA 92865',
  phone: '(714) 637-3369',
  hours: 'Mon–Sat 11:00 AM – 9:30 PM',
  lunchHours: '11:00 AM – 3:00 PM',
  closedDay: 'Sunday',
  style: 'Family-owned Japanese Sushi Restaurant',
  rating: 4.4,
  reviewCount: 468,
  awards: ['Neighborhood Favorite 2020', 'Neighborhood Favorite 2022', 'Neighborhood Favorite 2023'],
}

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

export const RECENT_ORDERS = [
  { time: '2:45 PM', platform: 'DoorDash', items: 'Dragon Roll, Edamame', amount: 23.90, status: 'Preparing' },
  { time: '2:32 PM', platform: 'UberEats', items: 'House Special Roll, Miso Soup', amount: 21.90, status: 'Ready' },
  { time: '2:15 PM', platform: 'Walk-in', items: 'Rainbow Roll, Salmon Sashimi, Gyoza', amount: 45.85, status: 'Done' },
  { time: '1:50 PM', platform: 'DoorDash', items: 'Tiger Woods Roll, Spicy Garlic Edamame', amount: 28.90, status: 'Done' },
  { time: '1:30 PM', platform: 'Phone', items: 'Bento Box, California Roll', amount: 33.90, status: 'Done' },
]

export const TODAY_RESERVATIONS = [
  { time: '5:30 PM', name: 'Kim', size: 4, request: 'Birthday celebration' },
  { time: '6:00 PM', name: 'Nguyen', size: 2, request: '' },
  { time: '6:30 PM', name: 'Park', size: 6, request: 'Sushi platter for the table please' },
  { time: '7:00 PM', name: 'Chen', size: 3, request: 'Allergic to shellfish' },
]

export const ALL_ORDERS = [
  { id: 1, time: '2:45 PM', platform: 'DoorDash', customer: 'Mike T.', items: 'Dragon Roll, Edamame', amount: 23.90, status: 'Preparing' },
  { id: 2, time: '2:32 PM', platform: 'UberEats', customer: 'Lisa K.', items: 'House Special Roll, Miso Soup', amount: 21.90, status: 'Ready' },
  { id: 3, time: '2:15 PM', platform: 'Walk-in', customer: 'Table 4', items: 'Rainbow Roll, Salmon Sashimi, Gyoza', amount: 45.85, status: 'Done' },
  { id: 4, time: '1:50 PM', platform: 'DoorDash', customer: 'Sarah L.', items: 'Tiger Woods Roll, Spicy Garlic Edamame', amount: 28.90, status: 'Done' },
  { id: 5, time: '1:30 PM', platform: 'Phone', customer: 'James W.', items: 'Bento Box, California Roll', amount: 33.90, status: 'Done' },
  { id: 6, time: '1:05 PM', platform: 'UberEats', customer: 'Amy C.', items: 'Sushi Burrito, Miso Soup', amount: 22.90, status: 'Done' },
  { id: 7, time: '12:40 PM', platform: 'Walk-in', customer: 'Table 2', items: 'Chicago Roll, Ninja Roll, Edamame × 2', amount: 42.85, status: 'Done' },
  { id: 8, time: '12:15 PM', platform: 'DoorDash', customer: 'Kevin P.', items: 'Krunch Roll, Shrimp Tempura', amount: 27.90, status: 'Done' },
  { id: 9, time: '11:50 AM', platform: 'Walk-in', customer: 'Table 6', items: 'Lunch Combo A, Lunch Combo B', amount: 39.98, status: 'Done' },
  { id: 10, time: '11:30 AM', platform: 'Phone', customer: 'Diana R.', items: 'Miami Vice Roll, Sunshine Roll, Edamame', amount: 41.85, status: 'Done' },
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
  { id: 7, time: '11:30 AM', name: 'Corporate — Acme Inc.', phone: '(714) ***-5501', size: 12, request: 'Lunch meeting, need separate checks', status: 'Confirmed' },
  { id: 8, time: '5:00 PM', name: 'Johnson', phone: '(949) ***-9923', size: 4, request: '', status: 'Pending' },
  { id: 9, time: '6:00 PM', name: 'Tanaka', phone: '(714) ***-4478', size: 2, request: 'Anniversary dinner', status: 'Confirmed' },
  { id: 10, time: '7:00 PM', name: 'Garcia', phone: '(562) ***-8856', size: 6, request: '', status: 'Confirmed' },
]

export const MENU_ITEMS = [
  { category: 'Appetizers', items: [
    { name: 'Edamame', price: 6.95 },
    { name: 'Spicy Garlic Edamame', price: 8.95 },
    { name: 'Gyoza (8pc)', price: 12.95 },
    { name: 'Shrimp Tempura (8pc)', price: 14.95 },
    { name: 'Miso Soup', price: 2.95 },
  ]},
  { category: 'Regular Rolls', items: [
    { name: 'California Roll', price: 8.95 },
    { name: 'Spicy California', price: 9.95 },
    { name: 'Deep Fried California', price: 10.95 },
    { name: 'Salmon Roll', price: 11.95 },
  ]},
  { category: 'Special Rolls', items: [
    { name: 'House Special', price: 18.95, desc: 'Seared albacore & crab meat with spicy tuna and green onion' },
    { name: 'Rainbow Roll', price: 16.95 },
    { name: 'Dragon Roll', price: 16.95 },
    { name: 'Sushi Burrito', price: 19.95, desc: 'Generous portion wrapped in soy paper' },
    { name: 'Tiger Woods', price: 19.95 },
    { name: 'Ninja', price: 16.95 },
    { name: 'Sunshine', price: 16.95 },
    { name: 'Chicago', price: 19.95 },
    { name: 'Krunch', price: 12.95 },
    { name: 'Hot Night', price: 15.95 },
    { name: 'Miami Vice', price: 17.95 },
  ]},
  { category: 'Sushi & Sashimi', items: [
    { name: 'Salmon Sushi (2pc)', price: 7.95 },
    { name: 'Salmon Sashimi', price: 15.95 },
    { name: 'Bento Box', price: 24.95 },
  ]},
]

// Reviews based on real themes from Yelp (468 reviews), Google (4.3★), OpenTable
export const REVIEWS = [
  {
    id: 1, stars: 5, platform: 'Yelp', date: '2025-03-22',
    text: 'Easily the best sushi restaurant I\'ve been to. The Dragon Roll and House Special are incredible — fresh, generous portions, and beautifully presented. Family-owned and you can tell they care about every dish.',
    reply: 'Thank you so much! We put our heart into every roll. Hope to see you again soon! 🙏',
  },
  {
    id: 2, stars: 5, platform: 'Google', date: '2025-03-18',
    text: 'Hidden gem in Orange! The Tiger Woods roll is out of this world. Super friendly owners — husband makes everything fresh to order, wife greets you with a smile. Clean, cozy, affordable. My new go-to sushi spot.',
    reply: null,
  },
  {
    id: 3, stars: 4, platform: 'Yelp', date: '2025-03-10',
    text: 'Great sushi at fair prices. The Rainbow Roll was beautiful and fresh. Only reason for 4 stars is the wait — there\'s just one chef so during peak hours you might wait 20-25 min. Worth it though!',
    reply: null,
    aiSuggestion: 'Thank you for the kind words and your patience! You\'re right that during peak hours it can take a bit longer since everything is made fresh to order by our chef. We\'re looking into ways to reduce wait times. We hope the quality makes up for it! Come back soon 😊',
  },
  {
    id: 4, stars: 5, platform: 'Google', date: '2025-02-28',
    text: 'Brought my parents here for dinner and they loved it. The Shrimp Tempura was perfectly crispy, and the Sushi Burrito is a must-try — huge portion! The owners recommended the House Special and it did not disappoint.',
    reply: 'So happy your family enjoyed everything! The Sushi Burrito is one of our favorites too. Thank you for dining with us! 🍣',
  },
  {
    id: 5, stars: 3, platform: 'Yelp', date: '2025-02-15',
    text: 'Food was good but took a bit long due to one chef available. The California Roll and Edamame were solid. Wish they had more seating — it\'s a small spot.',
    reply: null,
  },
]

export const MESSAGES_SENT = [
  { date: '2025-03-20', type: '🎉 Special', title: 'Spring Special — 10% off all Special Rolls this weekend!', recipients: 312 },
  { date: '2025-03-10', type: '🚫 Closed', title: 'Closed for Easter Sunday (March 30)', recipients: 312 },
  { date: '2025-02-14', type: '🆕 New Item', title: 'NEW — Spicy Garlic Edamame is here!', recipients: 287 },
]

export const MESSAGE_TEMPLATES = [
  { icon: '🎉', label: 'Special / Promo', desc: 'Announce deals, happy hour, seasonal specials' },
  { icon: '🚫', label: 'Closed / Hours', desc: 'Holiday closures and adjusted hours' },
  { icon: '🆕', label: 'New Item', desc: 'Let regulars know about new menu additions' },
  { icon: '📅', label: 'Reservation Reminder', desc: 'Remind guests about upcoming reservations' },
]
