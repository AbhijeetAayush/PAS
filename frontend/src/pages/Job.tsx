import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Job } from "../api";
import { useAuth } from "../auth";
import { bodyKind, count } from "../format";
import { Pager, StatusPill, usePage, useWide, Wordmark } from "../ui";

export function JobPage() {
  const { jobId = "" } = useParams();
  const auth = useAuth();
  const token = auth.session?.access_token ?? "";
  const wide = useWide();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [updated, setUpdated] = useState("");

  useEffect(() => {
    if (!token) return;
    let stop = false;
    let timer = 0;
    const load = () => {
      api<Job>(`/jobs/${jobId}`, {}, token)
        .then((payload) => {
          if (stop) return;
          setJob(payload);
          setUpdated(new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }));
          if (payload.status === "ready" || payload.status === "failed") window.clearInterval(timer);
        })
        .catch((err: Error) => {
          if (!stop) setError(err.message);
        });
    };
    load();
    timer = window.setInterval(load, 3000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [jobId, token]);

  const files = useMemo(
    () => [...(job?.files ?? [])].sort((a, b) => (a.ward_no ?? 999) - (b.ward_no ?? 999)),
    [job],
  );
  const pager = usePage(files, wide ? 12 : 6);
  const totalPages = files.reduce((sum, file) => sum + (file.page_count || 0), 0);
  const readyPages = files.reduce((sum, file) => sum + file.pages_ready, 0);
  const ratio = totalPages ? Math.min(100, Math.round((readyPages / totalPages) * 100)) : 0;

  if (error) return <p className="banner">{error}</p>;
  if (!job) {
    return (
      <section className="empty">
        <Wordmark />
        <p>Loading this roll…</p>
      </section>
    );
  }

  const query = new URLSearchParams({
    district_id: job.district_id,
    prakhand_id: job.prakhand_id,
    body_type: job.body_type,
    body_id: job.body_id,
  });
  const live = job.status === "reading" || job.status === "queued";

  return (
    <>
      <div className="stack">
        <p className="eyebrow">{bodyKind(job.body_type)}</p>
        <h1 className="place">{job.body_name}</h1>
        <p className="muted hindi">{job.district_name} · {job.prakhand_name}</p>
        <span className="row">
          <StatusPill status={job.status} />
          <span className="meta" aria-live="polite">{live && updated ? `Updated ${updated}` : job.publication}</span>
        </span>
      </div>
      <section className="panel">
        <span className="row">
          <strong>{count(job.voter_count)} voters</strong>
          <span className="meta">{totalPages ? `${readyPages}/${totalPages} pages` : "Finding wards"}</span>
        </span>
        <div className={job.status === "failed" ? "bar failed" : "bar"} aria-hidden>
          <span style={{ width: `${ratio}%` }} />
        </div>
      </section>
      {job.error && <p className="banner">{job.error}</p>}
      <div className={wide ? "ward-grid" : "list"}>
        {pager.slice.map((file) => {
          const pages = file.page_count || 0;
          const width = pages ? Math.min(100, Math.round((file.pages_ready / pages) * 100)) : 0;
          return (
            <article key={`${file.ward_no}-${file.status}`} className="ward">
              <span className="row">
                <span className="ward-no">{file.ward_no ?? "—"}</span>
                <StatusPill status={file.status} pagesReady={file.pages_ready} pageCount={file.page_count} />
              </span>
              <div className={file.status === "failed" ? "bar failed" : "bar"} aria-hidden>
                <span style={{ width: `${width}%` }} />
              </div>
              <span className="meta">{pages ? `${file.pages_ready}/${pages} pages` : "Pages not counted yet"} · {count(file.voter_count)} voters</span>
              {file.error && <p className="banner">{file.error}</p>}
            </article>
          );
        })}
      </div>
      <Pager page={pager.page} pages={pager.pages} onPage={pager.setPage} />
      {job.voter_count > 0 && (
        <Link className="primary sticky-go" to={`/voters?${query}`}>
          View {count(job.voter_count)} voters
        </Link>
      )}
    </>
  );
}
