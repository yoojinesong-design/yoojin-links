import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex items-center justify-center px-5">
      <div className="text-center max-w-md">
        <div className="text-6xl font-extrabold text-neutral-800 mb-4">404</div>
        <h1 className="text-xl font-bold mb-2">Page not found</h1>
        <p className="text-sm text-neutral-500 mb-8">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            href="/gage-doumi"
            className="text-sm bg-amber-500 hover:bg-amber-400 text-white px-5 py-2.5 rounded-lg font-medium transition"
          >
            가게도우미
          </Link>
          <Link
            href="/"
            className="text-sm border border-neutral-700 hover:border-neutral-500 text-neutral-300 px-5 py-2.5 rounded-lg font-medium transition"
          >
            DetailBook
          </Link>
          <Link
            href="/persona-hub"
            className="text-sm border border-neutral-700 hover:border-neutral-500 text-neutral-300 px-5 py-2.5 rounded-lg font-medium transition"
          >
            PersonaHub
          </Link>
        </div>
      </div>
    </div>
  )
}
