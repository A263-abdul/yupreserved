import { Link } from "react-router-dom";
import { Poster } from "../art/Poster";
import { Page } from "../components/motion";

export default function NotFound() {
  return (
    <Page className="mx-auto grid max-w-5xl items-center gap-10 px-4 py-16 sm:px-6 md:grid-cols-2">
      <Poster city="Jaisalmer" seed={404} className="aspect-[4/5] rounded-[2rem]" />
      <div>
        <p className="eyebrow">404 · lost in the dunes</p>
        <h1 className="display mt-3 text-5xl">This page took a wrong turn at Jaisalmer.</h1>
        <p className="mt-4 text-ink-2">The link may be old, or the stay may have moved. Everything else is right where you left it.</p>
        <Link to="/" className="mt-8 inline-block rounded-full bg-sindoor px-6 py-3 font-semibold text-sindoor-ink">Back home</Link>
      </div>
    </Page>
  );
}
