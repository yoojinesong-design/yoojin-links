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
            href="/"
            className="text-sm bg-sky-500 hover:bg-sky-400 text-white px-5 py-2.5 rounded-lg font-medium transition"
          >
            DetailBook Home
          </Link>
          <Link
            href="/persona-hub"
            className="text-sm border border-neutral-700 hover:border-neutral-500 text-neutral-300 px-5 py-2.5 rounded-lg font-medium transition"
          >
            PersonaHub Home
          </Link>
        </div>
      </div>
    </div>
  )
}
