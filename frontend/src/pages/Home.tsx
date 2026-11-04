import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type JobCounts, type JobSummary } from "../api";
import { useAuth } from "../auth";
import { bodyKind, count, when } from "../format";
import { Pager, StatusPill, useWide, Wordmark } from "../ui";

type Filter = "all" | "reading" | "ready" | "failed";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "reading", label: "Reading" },
  { id: "ready", label: "Available" },
  { id: "failed", label: "Incomplete" },
];

export function HomePage() {
  const auth = useAuth();
  const token = auth.session?.access_token ?? "";
  const wide = useWide();
  const pageSize = wide ? 12 : 8;
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [counts, setCounts] = useState<JobCounts>({ all: 0, reading: 0, ready: 0, failed: 0 });
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [needle, setNeedle] = useState("");
  const [page, setPage] = useState(0);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setNeedle(query.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    if (!token) return;
    let stop = false;
    let timer = 0;
    const load = () => {
      const search = new URLSearchParams({
        limit: String(pageSize),
        offset: String(page * pageSize),
      });
      if (needle) search.set("q", needle);
      if (filter !== "all") search.set("status", filter);
      api<{ jobs: JobSummary[]; total: number; counts: JobCounts }>(`/jobs?${search}`, {}, token)
        .then((payload) => {
          if (stop) return;
          setJobs(payload.jobs);
          setTotal(payload.total);
          setCounts(payload.counts);
          setError("");
          if (payload.counts.reading < 1) window.clearInterval(timer);
        })
        .catch((err: Error) => {
          if (!stop) setError(err.message);
        })
        .finally(() => {
          if (!stop) setReady(true);
        });
    };
    load();
    timer = window.setInterval(load, 6000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [filter, needle, page, pageSize, token]);

  const pages = Math.max(1, Math.ceil(total / pageSize));

  function choose(next: Filter) {
    setFilter(next);
    setPage(0);
  }

  return (
    <>
      <div className="row">
        <div className="stack">
          <p className="eyebrow">Library</p>
          <h1 className="display">Rolls</h1>
        </div>
        <Link className="ghost" to="/add">Add a roll</Link>
      </div>
      <p className="muted">Panchayats kept for this account. Search by place as the library grows.</p>
      <label className="field">
        Search the library
        <span className="search">
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(0);
            }}
            placeholder="Panchayat, district, or prakhand"
          />
          {query && (
            <button type="button" className="clear" aria-label="Clear search" onClick={() => { setQuery(""); setPage(0); }}>×</button>
          )}
        </span>
      </label>
      <div className="filters" role="tablist" aria-label="Roll status">
        {FILTERS.map((item) => (
          <button key={item.id} type="button" aria-pressed={filter === item.id} onClick={() => choose(item.id)}>
            {item.label} {count(counts[item.id])}
          </button>
        ))}
      </div>
      {error && <p className="banner">{error}</p>}
      {!ready && <p className="muted">Loading the library…</p>}
      {ready && counts.all === 0 && !needle && (
        <section className="empty">
          <Wordmark size="lg" />
          <h2 className="display">No rolls yet</h2>
          <p>Add a panchayat and it will be kept here for lookup.</p>
          <Link className="primary" to="/add">Add a roll</Link>
        </section>
      )}
      {ready && total === 0 && (needle || filter !== "all") && <p className="muted">Nothing matches this view.</p>}
      {total > 0 && (
        <p className="meta">{count(page * pageSize + 1)}–{count(Math.min(total, page * pageSize + jobs.length))} of {count(total)}</p>
      )}
      {jobs.length > 0 && (
        <div className="ledger">
          {jobs.map((job) => {
            const voters = new URLSearchParams({
              district_id: job.district_id,
              prakhand_id: job.prakhand_id,
              body_type: job.body_type,
              body_id: job.body_id,
            });
            return (
              <article key={job.id} className="entry">
                <div className="entry-main">
                  <Link className="entry-name" to={`/jobs/${job.id}`}>{job.body_name}</Link>
                  <span className="meta hindi" title={`${job.district_name} · ${job.prakhand_name} · ${bodyKind(job.body_type)}`}>{job.district_name} · {job.prakhand_name} · {bodyKind(job.body_type)}</span>
                </div>
                <div className="entry-side">
                  <StatusPill status={job.status} />
                  <span className="meta">{when(job.created_at)}</span>
                  <Link to={`/voters?${voters}`}>View roll</Link>
                </div>
              </article>
            );
          })}
        </div>
      )}
      <Pager page={page} pages={total ? pages : 0} onPage={setPage} />
    </>
  );
}
