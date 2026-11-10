import { useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "./auth";
import { statusLabel, tone } from "./format";

export function Wordmark({ size = "md" }: { size?: "md" | "lg" | "xl" }) {
  return (
    <span className={`wordmark ${size}`} aria-label="CIVIQ.ai">
      <span className="saffron">CIVI</span>
      <span className="band">Q</span>
      <span className="india">.ai</span>
    </span>
  );
}

export function Boot() {
  return (
    <div className="boot">
      <Wordmark size="lg" />
      <p>Opening your rolls</p>
    </div>
  );
}

export function Chrome({ children }: { children: ReactNode }) {
  const auth = useAuth();
  return (
    <div className="app">
      <header className="topbar">
        <NavLink to="/" className="brand" end>
          <span className="brand-lockup">
            <Wordmark />
            <small>Voter rolls</small>
          </span>
        </NavLink>
        <button className="ghost" type="button" onClick={() => auth.signOut()}>
          Sign out
        </button>
      </header>
      <main className="stage">{children}</main>
      <nav className="dock" aria-label="Primary">
        <NavLink to="/" end className={({ isActive }) => (isActive ? "dock-link on" : "dock-link")}>
          <HomeIcon />
          Library
        </NavLink>
        <NavLink to="/voters" className={({ isActive }) => (isActive ? "dock-link on" : "dock-link")}>
          <PeopleIcon />
          Voters
        </NavLink>
        <NavLink to="/add" className={({ isActive }) => (isActive ? "dock-link on" : "dock-link")}>
          <PlusIcon />
          Add
        </NavLink>
      </nav>
    </div>
  );
}

export function StatusPill({ status, pagesReady = 0, pageCount = 0 }: { status: string; pagesReady?: number; pageCount?: number }) {
  const kind = tone(status, pagesReady, pageCount);
  return (
    <span className={`pill ${kind}`}>
      {kind === "reading" && <i className="live" aria-hidden />}
      {statusLabel(status, pagesReady, pageCount)}
    </span>
  );
}

export function Picker({
  label,
  placeholder,
  options,
  value,
  onChange,
  loading,
  empty,
}: {
  label: string;
  placeholder: string;
  options: { id: string; name: string }[];
  value: string;
  onChange: (id: string) => void;
  loading?: boolean;
  empty?: string;
}) {
  const [query, setQuery] = useState("");
  const needle = query.trim().toLowerCase();
  const shown = options.filter((item) => item.name.toLowerCase().includes(needle) || item.name.includes(query.trim()));

  return (
    <div className="picker">
      <label className="field">
        {label}
        <span className="search">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={placeholder}
            autoComplete="off"
          />
          {query && (
            <button type="button" className="clear" onClick={() => setQuery("")} aria-label="Clear search">
              ×
            </button>
          )}
        </span>
      </label>
      <div className="options" role="listbox" aria-label={label}>
        {loading && <p className="muted">Loading…</p>}
        {!loading && shown.length === 0 && <p className="muted">{empty || "Nothing matches."}</p>}
        {shown.map((item) => (
          <button
            key={item.id}
            type="button"
            role="option"
            aria-selected={value === item.id}
            className={value === item.id ? "option on" : "option"}
            onClick={() => onChange(item.id)}
          >
            <span className="hindi">{item.name}</span>
            <span className="tick" aria-hidden>{value === item.id ? "✓" : ""}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function MultiPicker({
  label,
  placeholder,
  options,
  values,
  onChange,
  loading,
  empty,
}: {
  label: string;
  placeholder: string;
  options: { id: string; name: string }[];
  values: string[];
  onChange: (ids: string[]) => void;
  loading?: boolean;
  empty?: string;
}) {
  const [query, setQuery] = useState("");
  const needle = query.trim().toLowerCase();
  const shown = options.filter((item) => item.name.toLowerCase().includes(needle) || item.name.includes(query.trim()));
  const selected = new Set(values);
  const allOn = options.length > 0 && options.every((item) => selected.has(item.id));

  function toggle(id: string) {
    onChange(selected.has(id) ? values.filter((value) => value !== id) : [...values, id]);
  }

  return (
    <div className="picker">
      <label className="field">
        {label}
        <span className="search">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={placeholder}
            autoComplete="off"
          />
          {query && (
            <button type="button" className="clear" onClick={() => setQuery("")} aria-label="Clear search">
              ×
            </button>
          )}
        </span>
      </label>
      <div className="pick-tools">
        <span className="meta">{values.length} selected</span>
        <button type="button" className="text" disabled={loading || options.length === 0} onClick={() => onChange(allOn ? [] : options.map((item) => item.id))}>
          {allOn ? "Clear" : "Select all"}
        </button>
      </div>
      <div className="options" role="listbox" aria-multiselectable="true" aria-label={label}>
        {loading && <p className="muted">Loading…</p>}
        {!loading && shown.length === 0 && <p className="muted">{empty || "Nothing matches."}</p>}
        {shown.map((item) => (
          <button
            key={item.id}
            type="button"
            role="option"
            aria-selected={selected.has(item.id)}
            className={selected.has(item.id) ? "option on" : "option"}
            onClick={() => toggle(item.id)}
          >
            <span className="hindi">{item.name}</span>
            <span className="tick" aria-hidden>{selected.has(item.id) ? "✓" : ""}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function Pager({ page, pages, onPage }: { page: number; pages: number; onPage: (page: number) => void }) {
  if (pages <= 1) return null;
  const numbers = pageWindow(page, pages);
  return (
    <nav className="pager" aria-label="Pages">
      <button type="button" disabled={page === 0} onClick={() => onPage(page - 1)} aria-label="Previous page">
        Prev
      </button>
      <div className="pager-nums">
        {numbers.map((item, index) =>
          item === "…" ? (
            <span key={`gap-${index}`} className="gap">…</span>
          ) : (
            <button
              key={item}
              type="button"
              aria-current={item === page ? "page" : undefined}
              onClick={() => onPage(item)}
            >
              {item + 1}
            </button>
          ),
        )}
      </div>
      <button type="button" disabled={page >= pages - 1} onClick={() => onPage(page + 1)} aria-label="Next page">
        Next
      </button>
    </nav>
  );
}

export function useWide(): boolean {
  const [wide, setWide] = useState(() => window.matchMedia("(min-width: 800px)").matches);
  useEffect(() => {
    const query = window.matchMedia("(min-width: 800px)");
    const onChange = () => setWide(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);
  return wide;
}

export function usePage<T>(items: T[], size: number): { page: number; setPage: (page: number) => void; pages: number; slice: T[] } {
  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(items.length / size));
  const safe = Math.min(page, pages - 1);
  useEffect(() => {
    if (page !== safe) setPage(safe);
  }, [page, safe]);
  return { page: safe, setPage, pages, slice: items.slice(safe * size, safe * size + size) };
}

function pageWindow(page: number, pages: number): Array<number | "…"> {
  const wanted = new Set([0, pages - 1, page - 1, page, page + 1]);
  const indexes = [...wanted].filter((item) => item >= 0 && item < pages).sort((a, b) => a - b);
  const out: Array<number | "…"> = [];
  indexes.forEach((item, index) => {
    if (index > 0 && item - indexes[index - 1] > 1) out.push("…");
    out.push(item);
  });
  return out;
}

function HomeIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden>
      <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1z" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden>
      <path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

function PeopleIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden>
      <path d="M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM16.5 11.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5ZM4.5 19c.4-2.4 2.3-4 4.5-4s4.1 1.6 4.5 4M14 15.2c1.5.2 2.8 1.1 3.4 2.8" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}
