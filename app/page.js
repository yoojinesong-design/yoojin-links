import ImprintApp from "./components/ImprintApp";
import ErrorBoundary from "./components/ErrorBoundary";

export default function Home() {
  return (
    <ErrorBoundary>
      <ImprintApp />
    </ErrorBoundary>
  );
}
