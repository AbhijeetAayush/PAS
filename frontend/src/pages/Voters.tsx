import { useEffect, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type Body, type District, type Prakhand, type Voter } from "../api";
import { useAuth } from "../auth";
import { count } from "../format";
import { useWide } from "../ui";

const PAGE = 40;

export function VotersPage() {
  const [params] = useSearchParams();
  const auth = useAuth();
  const token = auth.session?.access_token ?? "";
  const wide = useWide();
  const [districts, setDistricts] = useState<District[]>([]);
  const [prakhands, setPrakhands] = useState<Prakhand[]>([]);
  const [bodies, setBodies] = useState<Body[]>([]);
  const [wards, setWards] = useState<number[]>([]);
  const [districtId, setDistrictId] = useState(params.get("district_id") ?? "");
  const [prakhandId, setPrakhandId] = useState(params.get("prakhand_id") ?? "");
  const [bodyType, setBodyType] = useState(params.get("body_type") || "nagar_panchayat");
  const [bodyId, setBodyId] = useState(params.get("body_id") ?? "");
  const [ward, setWard] = useState(params.get("ward_no") ?? "");
  const [query, setQuery] = useState("");
  const [needle, setNeedle] = useState("");
  const [bodyName, setBodyName] = useState("");
  const [voters, setVoters] = useState<Voter[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState<Voter | null>(null);
  const busy = useRef(false);
  const scroller = useRef<HTMLDivElement>(null);
  const sentinel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<{ districts: District[] }>("/catalog/districts")
      .then((payload) => setDistricts(payload.districts))
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!districtId) {
      setPrakhands([]);
      return;
    }
    api<{ prakhands: Prakhand[] }>(`/catalog/prakhands?district_id=${districtId}`)
      .then((payload) => setPrakhands(payload.prakhands))
      .catch((err: Error) => setError(err.message));
  }, [districtId]);

  useEffect(() => {
    if (!districtId || !prakhandId) {
      setBodies([]);
      return;
    }
    const search = new URLSearchParams({ district_id: districtId, prakhand_id: prakhandId, body_type: bodyType });
    api<{ bodies: Body[] }>(`/catalog/bodies?${search}`)
      .then((payload) => setBodies(payload.bodies))
      .catch((err: Error) => setError(err.message));
  }, [bodyType, districtId, prakhandId]);

  useEffect(() => {
    if (!token || !districtId || !prakhandId || !bodyId) {
      setWards([]);
      return;
    }
    const search = new URLSearchParams({ district_id: districtId, prakhand_id: prakhandId, body_type: bodyType, body_id: bodyId });
    api<{ wards: number[] }>(`/wards?${search}`, {}, token)
      .then((payload) => setWards(payload.wards))
      .catch(() => setWards([]));
  }, [bodyId, bodyType, districtId, prakhandId, token]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setNeedle(query.trim());
      setPage(0);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    setOpen(null);
  }, [bodyId, districtId, needle, prakhandId, ward]);

  useEffect(() => {
    if (!token || !districtId || !prakhandId || !bodyId) {
      busy.current = false;
      setVoters([]);
      setTotal(0);
      setBodyName("");
      return;
    }
    let cancel = false;
    busy.current = true;
    setLoading(true);
    setError("");
    const offset = page * PAGE;
    if (offset === 0) setVoters([]);
    const search = new URLSearchParams({
      district_id: districtId,
      prakhand_id: prakhandId,
      body_type: bodyType,
      body_id: bodyId,
      limit: String(PAGE),
      offset: String(offset),
    });
    if (ward) search.set("ward_no", ward);
    if (needle) search.set("q", needle);
    api<{ body_name?: string; total: number; voters: Voter[] }>(`/voters?${search}`, {}, token)
      .then((payload) => {
        if (cancel) return;
        setBodyName(payload.body_name ?? "");
        setTotal(payload.total);
        setVoters((current) => (offset === 0 ? payload.voters : [...current, ...payload.voters]));
      })
      .catch((err: Error) => {
        if (!cancel) setError(err.message);
      })
      .finally(() => {
        if (cancel) return;
        busy.current = false;
        setLoading(false);
      });
    return () => {
      cancel = true;
    };
  }, [bodyId, bodyType, districtId, needle, page, prakhandId, token, ward]);

  useEffect(() => {
    const node = sentinel.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        if (busy.current || voters.length === 0 || voters.length >= total) return;
        busy.current = true;
        setPage((current) => current + 1);
      },
      { root: wide ? scroller.current : null, rootMargin: "280px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [total, voters.length, wide]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const ready = Boolean(districtId && prakhandId && bodyId);
  const more = voters.length > 0 && voters.length < total;

  function resetPlace(apply: () => void) {
    apply();
    setPage(0);
    setOpen(null);
  }

  return (
    <>
      <div className="stack">
        <p className="eyebrow">Lookup</p>
        <h1 className="display">Voters</h1>
        {!ready && <p className="muted">Choose the place. The roll opens for the whole panchayat. A ward is optional.</p>}
        {ready && (
          <p className="meta" aria-live="polite">
            {bodyName ? <span className="hindi">{bodyName}</span> : "This roll"}
            {loading && voters.length === 0
              ? " · Looking up voters…"
              : ` · ${count(voters.length)} of ${count(total)}${ward ? ` in ward ${ward}` : ""}`}
          </p>
        )}
      </div>
      <section className="panel choice-grid">
        <Select label="District" value={districtId} onChange={(value) => resetPlace(() => { setDistrictId(value); setPrakhandId(""); setBodyId(""); setWard(""); })}>
          <option value="">Select a district</option>
          {districts.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </Select>
        <Select label="Prakhand" value={prakhandId} disabled={!districtId} onChange={(value) => resetPlace(() => { setPrakhandId(value); setBodyId(""); setWard(""); })}>
          <option value="">Select a prakhand</option>
          {prakhands.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </Select>
        <Select label="Body" value={bodyType} onChange={(value) => resetPlace(() => { setBodyType(value); setBodyId(""); setWard(""); })}>
          <option value="nagar_panchayat">Nagar panchayat</option>
          <option value="gram_panchayat">Gram panchayat</option>
        </Select>
        <Select label={bodyType === "nagar_panchayat" ? "Nagar panchayat" : "Gram panchayat"} value={bodyId} disabled={!prakhandId} onChange={(value) => resetPlace(() => { setBodyId(value); setWard(""); })}>
          <option value="">Select</option>
          {bodies.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </Select>
        <Select label="Ward" value={ward} disabled={!bodyId} onChange={(value) => resetPlace(() => setWard(value))}>
          <option value="">All wards</option>
          {wards.map((item) => <option key={item} value={item}>Ward {item}</option>)}
        </Select>
        <label className="field">
          Search within this roll
          <span className="search">
            <input
              value={query}
              disabled={!bodyId}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Name in Hindi or English, EPIC, house, or serial"
            />
            {query && <button type="button" className="clear" aria-label="Clear search" onClick={() => setQuery("")}>×</button>}
          </span>
        </label>
      </section>
      {error && <p className="banner">{error}</p>}
      {ready && !loading && total === 0 && <p className="muted">No voters are saved for this selection yet.</p>}
      {voters.length > 0 && (wide ? (
        <div className="roll-scroll" ref={scroller}>
          <table className="roll-table">
            <thead>
              <tr>
                <th className="pin">Name</th>
                <th>Ward</th>
                <th>Serial</th>
                <th>EPIC</th>
                <th>Relation</th>
                <th>Relative</th>
                <th>House</th>
                <th>Age</th>
                <th>Gender</th>
                <th>Part</th>
              </tr>
            </thead>
            <tbody>
              {voters.map((voter, index) => (
                <tr key={rowKey(voter, index)}>
                  <td className="pin hindi">{voter.name}</td>
                  <td>{blank(voter.ward_no)}</td>
                  <td>{voter.serial}</td>
                  <td>{blank(voter.epic)}</td>
                  <td className="hindi">{blank(voter.relation)}</td>
                  <td className="hindi">{blank(voter.relation_name)}</td>
                  <td>{blank(voter.house_no)}</td>
                  <td>{blank(voter.age)}</td>
                  <td className="hindi">{blank(voter.gender)}</td>
                  <td>{blank(voter.part_no)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div ref={sentinel} className="more">{more && loading ? "Loading more names…" : more ? "Scroll for more" : `${count(total)} names`}</div>
        </div>
      ) : (
        <div className="people">
          {voters.map((voter, index) => (
            <button key={rowKey(voter, index)} type="button" className="person" onClick={() => setOpen(voter)}>
              <strong>{voter.name}</strong>
              <span>Ward {blank(voter.ward_no)} · House {blank(voter.house_no)}</span>
            </button>
          ))}
          <div ref={sentinel} className="more">{more && loading ? "Loading more names…" : more ? "Scroll for more" : `${count(total)} names`}</div>
        </div>
      ))}
      {open && (
        <div className="sheet-back" onClick={() => setOpen(null)}>
          <section
            className="sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby="voter-name"
            onClick={(event) => event.stopPropagation()}
          >
            <span className="sheet-bar" aria-hidden />
            <div className="row">
              <h2 id="voter-name">{open.name}</h2>
              <button type="button" className="ghost" onClick={() => setOpen(null)}>Close</button>
            </div>
            <p className="meta">Ward {blank(open.ward_no)} · House {blank(open.house_no)}</p>
            <dl className="details">
              <Detail label="Serial" value={open.serial} />
              <Detail label="EPIC" value={open.epic} />
              <Detail label="Relation" value={[open.relation, open.relation_name].filter(Boolean).join(" ")} hindi />
              <Detail label="Age" value={open.age} />
              <Detail label="Gender" value={open.gender} hindi />
              <Detail label="Part" value={open.part_no} />
            </dl>
          </section>
        </div>
      )}
    </>
  );
}

function Detail({ label, value, hindi }: { label: string; value: string | number | null | undefined; hindi?: boolean }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={hindi ? "hindi" : undefined}>{blank(value)}</dd>
    </div>
  );
}

function Select({
  label,
  value,
  disabled,
  onChange,
  children,
}: {
  label: string;
  value: string;
  disabled?: boolean;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <label className="field">
      {label}
      <select value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
        {children}
      </select>
    </label>
  );
}

function blank(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

function rowKey(voter: Voter, index: number): string {
  return `${voter.ward_no}-${voter.part_no}-${voter.serial}-${voter.epic ?? ""}-${index}`;
}
