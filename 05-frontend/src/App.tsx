import { AnimatePresence } from "motion/react";
import { lazy, Suspense, useEffect } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { BottomNav, Footer, Header } from "./components/layout";
import { AuthDialog } from "./components/AuthDialog";
import { CompareTray, TraceDrawer } from "./components/overlays";
import { Skeleton } from "./components/feedback";
import Home from "./pages/Home";
import Search from "./pages/Search";
import Hotel from "./pages/Hotel";
import Checkout from "./pages/Checkout";
import Confirmation from "./pages/Confirmation";
import Trips from "./pages/Trips";
import NotFound from "./pages/NotFound";

// the database lab is big and only some visitors open it: load it on demand
const Lab = lazy(() => import("./pages/Lab"));

export default function App() {
  const location = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  return (
    <>
      <Header />
      <AnimatePresence mode="wait">
        <ErrorBoundary key={location.pathname}>
        <Routes location={location}>
          <Route path="/" element={<Home />} />
          <Route path="/stays" element={<Search />} />
          <Route path="/stay/:id" element={<Hotel />} />
          <Route path="/checkout" element={<Checkout />} />
          <Route path="/booked/:ref" element={<Confirmation />} />
          <Route path="/trips" element={<Trips />} />
          <Route path="/lab" element={
            <Suspense fallback={<div className="mx-auto max-w-7xl p-6"><Skeleton className="h-96" /></div>}><Lab /></Suspense>
          } />
          <Route path="*" element={<NotFound />} />
        </Routes>
        </ErrorBoundary>
      </AnimatePresence>
      <Footer />
      <AuthDialog />
      <TraceDrawer />
      <BottomNav />
      <CompareTray />
    </>
  );
}
