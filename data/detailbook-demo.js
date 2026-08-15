export const BOOKINGS = [
  { id: 1, customer: 'Sarah Chen', phone: '(512) 555-0142', vehicle: '2023 Tesla Model Y', type: 'suv', service: 'Full Detail', price: 170, deposit: 50, time: '8:00 AM', duration: '2.5 hrs', status: 'confirmed', notes: 'White exterior, pet hair in backseat' },
  { id: 2, customer: 'Marcus Johnson', phone: '(512) 555-0198', vehicle: '2022 BMW 3 Series', type: 'sedan', service: 'Ceramic Coating', price: 350, deposit: 50, time: '11:00 AM', duration: '4 hrs', status: 'confirmed', notes: 'Midnight blue. Wants showroom finish.' },
  { id: 3, customer: 'Emily Rodriguez', phone: '(512) 555-0267', vehicle: '2024 Ford F-150', type: 'truck', service: 'Exterior Wash', price: 90, deposit: 50, time: '4:00 PM', duration: '1 hr', status: 'pending', notes: '' },
]

export const TOMORROW_BOOKINGS = [
  { id: 4, customer: 'David Kim', phone: '(512) 555-0311', vehicle: '2023 Honda Civic', type: 'sedan', service: 'Interior Deep Clean', price: 80, deposit: 50, time: '9:00 AM', duration: '1.5 hrs', status: 'confirmed', notes: 'Spilled coffee on passenger seat' },
  { id: 5, customer: 'Amanda Torres', phone: '(512) 555-0389', vehicle: '2022 Chevy Tahoe', type: 'suv', service: 'Full Detail', price: 170, deposit: 50, time: '11:30 AM', duration: '2.5 hrs', status: 'confirmed', notes: '' },
]

export const RECENT_CUSTOMERS = [
  { name: 'Jake Williams', lastService: '12 days ago', service: 'Full Detail', total: 130, visits: 4 },
  { name: 'Lisa Park', lastService: '28 days ago', service: 'Ceramic Coating', total: 350, visits: 2 },
  { name: 'Robert Chen', lastService: '45 days ago', service: 'Exterior Wash', total: 60, visits: 7 },
  { name: 'Maria Santos', lastService: '62 days ago', service: 'Full Detail', total: 170, visits: 3, rebook: true },
  { name: 'Tom Bradley', lastService: '91 days ago', service: 'Interior Clean', total: 100, visits: 1, rebook: true },
]

export const WEEKLY_REVENUE = [
  { day: 'Mon', revenue: 350, jobs: 2 },
  { day: 'Tue', revenue: 170, jobs: 1 },
  { day: 'Wed', revenue: 520, jobs: 3 },
  { day: 'Thu', revenue: 200, jobs: 2 },
  { day: 'Fri', revenue: 0, jobs: 0 },
  { day: 'Sat', revenue: 0, jobs: 0 },
  { day: 'Sun', revenue: 0, jobs: 0 },
]

export const SERVICE_BREAKDOWN = [
  { service: 'Full Detail', count: 14, revenue: 2180, pct: 45 },
  { service: 'Ceramic Coating', count: 4, revenue: 1400, pct: 29 },
  { service: 'Exterior Wash', count: 8, revenue: 640, pct: 13 },
  { service: 'Interior Deep Clean', count: 5, revenue: 450, pct: 9 },
  { service: 'Paint Correction', count: 1, revenue: 600, pct: 4 },
]

export const PAYMENT_HISTORY = [
  { customer: 'Sarah Chen', service: 'Full Detail', amount: 170, deposit: 50, balance: 120, date: 'Aug 1', method: 'card' },
  { customer: 'Marcus Johnson', service: 'Exterior Wash', amount: 80, deposit: 50, balance: 30, date: 'Jul 30', method: 'card' },
  { customer: 'Jake Williams', service: 'Full Detail', amount: 130, deposit: 50, balance: 80, date: 'Jul 28', method: 'card' },
  { customer: 'Lisa Park', service: 'Ceramic Coating', amount: 350, deposit: 50, balance: 300, date: 'Jul 25', method: 'card' },
  { customer: 'Amanda Torres', service: 'Full Detail', amount: 170, deposit: 50, balance: 120, date: 'Jul 22', method: 'card' },
  { customer: 'Robert Chen', service: 'Exterior Wash', amount: 60, deposit: 50, balance: 10, date: 'Jul 20', method: 'cash' },
]
