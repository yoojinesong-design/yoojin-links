'use client'
import { useState } from 'react'
import Link from 'next/link'

const DEMO_DETAILER = {
  name: 'Mike\'s Mobile Detailing',
  slug: 'demo-detailer',
  location: 'Austin, TX',
  avatar: 'M',
  deposit: 50,
  services: [
    { id: 'ext-wash', name: 'Exterior Wash', prices: { sedan: 60, suv: 80, truck: 90 }, duration: 60 },
    { id: 'int-clean', name: 'Interior Deep Clean', prices: { sedan: 80, suv: 100, truck: 120 }, duration: 90 },
    { id: 'full-detail', name: 'Full Detail (Ext + Int)', prices: { sedan: 130, suv: 170, truck: 200 }, duration: 150 },
    { id: 'ceramic', name: 'Ceramic Coating', prices: { sedan: 350, suv: 450, truck: 500 }, duration: 240 },
    { id: 'paint-correct', name: 'Paint Correction + Ceramic', prices: { sedan: 600, suv: 750, truck: 850 }, duration: 480 },
  ],
  hours: { start: 8, end: 18 },
  unavailable: ['Sunday'],
}

const VEHICLE_TYPES = [
  { id: 'sedan', label: 'Sedan / Coupe', icon: '🚗' },
  { id: 'suv', label: 'SUV / Crossover', icon: '🚙' },
  { id: 'truck', label: 'Truck / Van', icon: '🛻' },
]

function generateDates() {
  const dates = []
  const now = new Date()
  for (let i = 1; i <= 14; i++) {
    const d = new Date(now)
    d.setDate(d.getDate() + i)
    const dayName = d.toLocaleDateString('en-US', { weekday: 'long' })
    if (!DEMO_DETAILER.unavailable.includes(dayName)) {
      dates.push({
        date: d,
        label: d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }),
        dayName,
      })
    }
  }
  return dates
}

function generateSlots(service) {
  if (!service) return []
  const slots = []
  const { start, end } = DEMO_DETAILER.hours
  const durationHrs = service.duration / 60
  for (let h = start; h + durationHrs <= end; h++) {
    const ampm = h >= 12 ? 'PM' : 'AM'
    const hr = h > 12 ? h - 12 : h
    slots.push({ time: `${hr}:00 ${ampm}`, hour: h })
  }
  return slots
}

export default function BookingPage() {
  const [step, setStep] = useState(1)
  const [vehicle, setVehicle] = useState(null)
  const [serviceId, setServiceId] = useState(null)
  const [selectedDate, setSelectedDate] = useState(null)
  const [selectedSlot, setSelectedSlot] = useState(null)
  const [form, setForm] = useState({ name: '', phone: '', email: '', notes: '' })
  const [confirmed, setConfirmed] = useState(false)

  const d = DEMO_DETAILER
  const service = d.services.find(s => s.id === serviceId)
  const price = service && vehicle ? service.prices[vehicle] : 0
  const dates = generateDates()
  const slots = generateSlots(service)

  const canProceed = () => {
    if (step === 1) return vehicle
    if (step === 2) return serviceId
    if (step === 3) return selectedDate && selectedSlot
    if (step === 4) return form.name && form.phone
    return false
  }

  const handleConfirm = () => {
    setConfirmed(true)
  }

  if (confirmed) {
    return (
      <div className="min-h-screen flex items-center justify-center p-5">
        <div className="max-w-md w-full text-center">
          <div className="w-16 h-16 bg-emerald-500/15 border border-emerald-500/30 rounded-full flex items-center justify-center text-3xl mx-auto mb-6">✓</div>
          <h1 className="text-2xl font-bold mb-3">Booking Confirmed!</h1>
          <p className="text-neutral-400 text-sm mb-6">
            {d.name} has your appointment.
            You'll get a reminder 24hrs before and 2hrs before.
          </p>
          <div className="bg-neutral-900/60 border border-neutral-800/60 rounded-xl p-5 text-left space-y-3 mb-6">
            <div className="flex justify-between text-sm">
              <span className="text-neutral-500">Service</span>
              <span className="font-medium">{service?.name}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-neutral-500">Vehicle</span>
              <span className="font-medium">{VEHICLE_TYPES.find(v => v.id === vehicle)?.label}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-neutral-500">Date</span>
              <span className="font-medium">{selectedDate?.label}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-neutral-500">Time</span>
              <span className="font-medium">{selectedSlot?.time}</span>
            </div>
            <div className="border-t border-neutral-800/60 pt-3 flex justify-between text-sm">
              <span className="text-neutral-500">Total</span>
              <span className="font-bold text-sky-400">${price}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-neutral-500">Deposit paid</span>
              <span className="font-medium text-emerald-400">${d.deposit}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-neutral-500">Due at completion</span>
              <span className="font-medium">${price - d.deposit}</span>
            </div>
          </div>
          <p className="text-xs text-neutral-600">
            This is a demo booking — no real charges.
            <Link href="/" className="text-sky-400 ml-1 hover:underline">Back to DetailBook</Link>
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <div className="border-b border-neutral-800/60 bg-neutral-900/40">
        <div className="max-w-lg mx-auto px-5 py-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-sky-500/15 border border-sky-500/30 rounded-full flex items-center justify-center font-bold text-sky-400">{d.avatar}</div>
            <div>
              <div className="font-bold text-sm">{d.name}</div>
              <div className="text-xs text-neutral-500">{d.location}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Progress */}
      <div className="max-w-lg mx-auto px-5 pt-5">
        <div className="flex gap-1 mb-6">
          {[1,2,3,4].map(s => (
            <div key={s} className={`h-1 flex-1 rounded-full transition-colors ${s <= step ? 'bg-sky-500' : 'bg-neutral-800'}`} />
          ))}
        </div>
      </div>

      <div className="max-w-lg mx-auto px-5 pb-20">
        {/* Step 1: Vehicle */}
        {step === 1 && (
          <div>
            <h2 className="text-xl font-bold mb-1">What's your vehicle?</h2>
            <p className="text-sm text-neutral-500 mb-6">Pricing adjusts by vehicle size.</p>
            <div className="space-y-2">
              {VEHICLE_TYPES.map(v => (
                <button
                  key={v.id}
                  onClick={() => setVehicle(v.id)}
                  className={`w-full flex items-center gap-4 p-4 rounded-xl border transition text-left ${
                    vehicle === v.id
                      ? 'border-sky-500 bg-sky-500/10'
                      : 'border-neutral-800/60 bg-neutral-900/40 hover:border-neutral-700'
                  }`}
                >
                  <span className="text-2xl">{v.icon}</span>
                  <span className="font-medium text-sm">{v.label}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 2: Service */}
        {step === 2 && (
          <div>
            <h2 className="text-xl font-bold mb-1">Choose a service</h2>
            <p className="text-sm text-neutral-500 mb-6">Prices for {VEHICLE_TYPES.find(v => v.id === vehicle)?.label}.</p>
            <div className="space-y-2">
              {d.services.map(s => (
                <button
                  key={s.id}
                  onClick={() => setServiceId(s.id)}
                  className={`w-full flex items-center justify-between p-4 rounded-xl border transition text-left ${
                    serviceId === s.id
                      ? 'border-sky-500 bg-sky-500/10'
                      : 'border-neutral-800/60 bg-neutral-900/40 hover:border-neutral-700'
                  }`}
                >
                  <div>
                    <div className="font-medium text-sm">{s.name}</div>
                    <div className="text-xs text-neutral-500 mt-0.5">~{s.duration} min</div>
                  </div>
                  <div className="text-lg font-bold text-sky-400">${s.prices[vehicle]}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 3: Date & Time */}
        {step === 3 && (
          <div>
            <h2 className="text-xl font-bold mb-1">Pick a date & time</h2>
            <p className="text-sm text-neutral-500 mb-6">{service?.name} — ~{service?.duration} min</p>

            <div className="mb-6">
              <div className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-3">Date</div>
              <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                {dates.map((dt, i) => (
                  <button
                    key={i}
                    onClick={() => setSelectedDate(dt)}
                    className={`p-2.5 rounded-lg border text-center transition text-sm ${
                      selectedDate === dt
                        ? 'border-sky-500 bg-sky-500/10 text-sky-400'
                        : 'border-neutral-800/60 bg-neutral-900/40 hover:border-neutral-700 text-neutral-300'
                    }`}
                  >
                    {dt.label}
                  </button>
                ))}
              </div>
            </div>

            {selectedDate && (
              <div>
                <div className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-3">Time</div>
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                  {slots.map((slot, i) => (
                    <button
                      key={i}
                      onClick={() => setSelectedSlot(slot)}
                      className={`p-2.5 rounded-lg border text-center transition text-sm ${
                        selectedSlot === slot
                          ? 'border-sky-500 bg-sky-500/10 text-sky-400'
                          : 'border-neutral-800/60 bg-neutral-900/40 hover:border-neutral-700 text-neutral-300'
                      }`}
                    >
                      {slot.time}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Step 4: Contact + Deposit */}
        {step === 4 && (
          <div>
            <h2 className="text-xl font-bold mb-1">Your info & deposit</h2>
            <p className="text-sm text-neutral-500 mb-6">
              A ${d.deposit} deposit secures your appointment.
            </p>

            <div className="space-y-3 mb-6">
              <div>
                <label className="text-xs font-medium text-neutral-400 mb-1 block">Name *</label>
                <input
                  type="text" value={form.name}
                  onChange={e => setForm({...form, name: e.target.value})}
                  className="w-full bg-neutral-900/60 border border-neutral-800/60 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-sky-500 transition"
                  placeholder="John Doe"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-neutral-400 mb-1 block">Phone *</label>
                <input
                  type="tel" value={form.phone}
                  onChange={e => setForm({...form, phone: e.target.value})}
                  className="w-full bg-neutral-900/60 border border-neutral-800/60 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-sky-500 transition"
                  placeholder="(512) 555-0123"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-neutral-400 mb-1 block">Email</label>
                <input
                  type="email" value={form.email}
                  onChange={e => setForm({...form, email: e.target.value})}
                  className="w-full bg-neutral-900/60 border border-neutral-800/60 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-sky-500 transition"
                  placeholder="john@email.com"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-neutral-400 mb-1 block">Notes (optional)</label>
                <textarea
                  value={form.notes}
                  onChange={e => setForm({...form, notes: e.target.value})}
                  rows={2}
                  className="w-full bg-neutral-900/60 border border-neutral-800/60 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-sky-500 transition resize-none"
                  placeholder="Black Tesla Model 3, parked in driveway"
                />
              </div>
            </div>

            {/* Summary */}
            <div className="bg-neutral-900/60 border border-neutral-800/60 rounded-xl p-4 space-y-2 mb-4">
              <div className="flex justify-between text-sm">
                <span className="text-neutral-500">{service?.name}</span>
                <span>${price}</span>
              </div>
              <div className="flex justify-between text-sm border-t border-neutral-800/60 pt-2">
                <span className="text-neutral-500">Deposit (due now)</span>
                <span className="font-bold text-sky-400">${d.deposit}</span>
              </div>
              <div className="flex justify-between text-xs text-neutral-600">
                <span>Remaining balance (due at completion)</span>
                <span>${price - d.deposit}</span>
              </div>
            </div>

            <p className="text-xs text-neutral-600 mb-4">
              By booking, you agree to the cancellation policy. Deposits are non-refundable for no-shows.
              Cancellations 24+ hours before are fully refundable.
            </p>
          </div>
        )}

        {/* Navigation */}
        <div className="flex gap-3 mt-8">
          {step > 1 && (
            <button
              onClick={() => setStep(step - 1)}
              className="px-5 py-3 rounded-lg border border-neutral-700 text-neutral-300 font-medium text-sm hover:border-neutral-500 transition"
            >
              Back
            </button>
          )}
          <button
            onClick={() => {
              if (step < 4) setStep(step + 1)
              else handleConfirm()
            }}
            disabled={!canProceed()}
            className={`flex-1 py-3 rounded-lg font-semibold text-sm transition ${
              canProceed()
                ? 'bg-sky-500 hover:bg-sky-400 text-white shadow-lg shadow-sky-500/20'
                : 'bg-neutral-800 text-neutral-600 cursor-not-allowed'
            }`}
          >
            {step === 4 ? `Pay $${d.deposit} Deposit & Book` : 'Continue'}
          </button>
        </div>
      </div>
    </div>
  )
}
