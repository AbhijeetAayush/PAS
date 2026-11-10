import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type Body, type District, type Prakhand, type Voter, type VoterFields, type VoterMark } from "../api";
import { useAuth } from "../auth";
import { count } from "../format";
import { Choice, KindEditor, NoteInput, categoryFor, leaderFor } from "../marks";
import { useWide } from "../ui";

const PAGE = 40;

type Filters = {
  name: string;
  epic: string;
  relation: string;
  relation_name: string;
  house_no: string;
  age: string;
  gender: string;
  serial: string;
  part_no: string;
  booth_no: string;
  religion: string;
  caste: string;
  category: string;
  occupation: string;
  farmer: string;
  shop: string;
  farmer_other: string;
  shop_other: string;
  occupation_other: string;
  ideology: string;
  leader: string;
};

type Column = {
  id: keyof Filters | "ward_no";
  label: string;
  filter: "text" | "choice";
  options?: (fields: VoterFields) => string[];
};

const EMPTY: Filters = {
  name: "",
  epic: "",
  relation: "",
  relation_name: "",
  house_no: "",
  age: "",
  gender: "",
  serial: "",
  part_no: "",
  booth_no: "",
  religion: "",
  caste: "",
  category: "",
  occupation: "",
  farmer: "",
  shop: "",
  farmer_other: "",
  shop_other: "",
  occupation_other: "",
  ideology: "",
  leader: "",
};

const COLUMNS: Column[] = [
  { id: "name", label: "Name", filter: "text" },
  { id: "ward_no", label: "Ward", filter: "text" },
  { id: "booth_no", label: "Booth", filter: "text" },
  { id: "serial", label: "Serial", filter: "text" },
  { id: "epic", label: "EPIC", filter: "text" },
  { id: "relation", label: "Relation", filter: "text" },
  { id: "relation_name", label: "Relative", filter: "text" },
  { id: "house_no", label: "House", filter: "text" },
  { id: "age", label: "Age", filter: "choice", options: (fields) => fields.age_bands ?? [] },
  { id: "gender", label: "Gender", filter: "text" },
  { id: "part_no", label: "Part", filter: "text" },
  { id: "religion", label: "Religion", filter: "choice", options: (fields) => fields.religions },
  { id: "caste", label: "Caste", filter: "choice", options: (fields) => fields.castes.map((item) => item.name) },
  { id: "category", label: "Category", filter: "choice", options: (fields) => fields.categories },
  { id: "occupation", label: "Occupation", filter: "choice", options: (fields) => fields.occupations },
  { id: "farmer", label: "Farming", filter: "choice", options: (fields) => fields.farmer_kinds },
  { id: "farmer_other", label: "Other farming", filter: "text" },
  { id: "shop", label: "Shop", filter: "choice", options: (fields) => fields.shop_kinds },
  { id: "shop_other", label: "Other shop", filter: "text" },
  { id: "occupation_other", label: "Other work", filter: "text" },
  { id: "ideology", label: "Ideology", filter: "choice", options: (fields) => fields.ideologies.map((item) => item.name) },
  { id: "leader", label: "Leader", filter: "choice", options: (fields) => fields.leaders },
];

export function VotersPage() {
  const [params] = useSearchParams();
  const auth = useAuth();
  const token = auth.session?.access_token ?? "";
  const wide = useWide();
  const [districts, setDistricts] = useState<District[]>([]);
  const [prakhands, setPrakhands] = useState<Prakhand[]>([]);
  const [bodies, setBodies] = useState<Body[]>([]);
  const [wards, setWards] = useState<number[]>([]);
  const [fields, setFields] = useState<VoterFields | null>(null);
  const [districtId, setDistrictId] = useState(params.get("district_id") ?? "");
  const [prakhandId, setPrakhandId] = useState(params.get("prakhand_id") ?? "");
  const [bodyType, setBodyType] = useState(params.get("body_type") || "nagar_panchayat");
  const [bodyId, setBodyId] = useState(params.get("body_id") ?? "");
  const [ward, setWard] = useState(params.get("ward_no") ?? "");
  const [needle, setNeedle] = useState("");
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [sort, setSort] = useState("");
  const [dir, setDir] = useState<"asc" | "desc">("asc");
  const [bodyName, setBodyName] = useState("");
  const [voters, setVoters] = useState<Voter[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [saving, setSaving] = useState<Set<string>>(new Set());
  const busy = useRef(false);
  const tickets = useRef<Record<string, number>>({});
  const scroller = useRef<HTMLDivElement>(null);
  const sentinel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<{ districts: District[] }>("/catalog/districts")
      .then((payload) => setDistricts(payload.districts))
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!token) return;
    api<VoterFields>("/voter-fields", {}, token)
      .then(setFields)
      .catch((err: Error) => setError(err.message));
  }, [token]);

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

  const onSearch = useCallback((value: string) => {
    setNeedle((current) => (current === value ? current : value));
    setPage(0);
  }, []);

  useEffect(() => {
    setOpenKey(null);
  }, [bodyId, districtId, needle, prakhandId, ward, filters, sort, dir]);

  const scope = `${districtId}|${prakhandId}|${bodyType}|${bodyId}|${ward}`;
  const scopeRef = useRef(scope);

  useEffect(() => {
    if (!token || !districtId || !prakhandId || !bodyId) {
      busy.current = false;
      scopeRef.current = scope;
      setVoters([]);
      setTotal(0);
      setBodyName("");
      setLoading(false);
      return;
    }
    const moved = scopeRef.current !== scope;
    scopeRef.current = scope;
    let cancel = false;
    const controller = new AbortController();
    busy.current = true;
    setLoading(true);
    setError("");
    if (moved) {
      setVoters([]);
      setTotal(0);
      setBodyName("");
    }
    const offset = page * PAGE;
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
    if (sort) {
      search.set("sort", sort);
      search.set("direction", dir);
    }
    for (const [key, value] of Object.entries(filters)) {
      if (value) search.set(key, value);
    }
    api<{ body_name?: string; total: number; voters: Voter[] }>(`/voters?${search}`, { signal: controller.signal }, token)
      .then((payload) => {
        if (cancel) return;
        setBodyName(payload.body_name ?? "");
        setTotal(payload.total);
        setVoters((current) => (offset === 0 ? payload.voters : [...current, ...payload.voters]));
        if (offset === 0) scroller.current?.scrollTo({ top: 0 });
      })
      .catch((err: unknown) => {
        if (cancel || isAbort(err)) return;
        setError(err instanceof Error ? err.message : "Could not load voters");
      })
      .finally(() => {
        if (cancel) return;
        busy.current = false;
        setLoading(false);
      });
    return () => {
      cancel = true;
      controller.abort();
    };
  }, [bodyId, bodyType, dir, districtId, filters, needle, page, prakhandId, scope, sort, token, ward]);

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

  const open = voters.find((voter) => voter.voter_key === openKey) ?? null;

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpenKey(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const ready = Boolean(districtId && prakhandId && bodyId);
  const more = voters.length > 0 && voters.length < total;
  const filtering = Boolean(needle || ward || Object.values(filters).some(Boolean));
  const emptyCopy = filtering ? "No voters match this search." : "No voters are saved for this selection yet.";
  const refreshing = loading && voters.length > 0;

  function resetPlace(apply: () => void, keepSearch = false) {
    apply();
    setPage(0);
    setOpenKey(null);
    if (!keepSearch) {
      setNeedle("");
      setFilters(EMPTY);
    }
  }

  function setFilter(key: keyof Filters, value: string) {
    setFilters((current) => (current[key] === value ? current : { ...current, [key]: value }));
    setPage(0);
  }

  function toggleSort(id: string) {
    if (sort === id) {
      setDir((current) => (current === "asc" ? "desc" : "asc"));
    } else {
      setSort(id);
      setDir("asc");
    }
    setPage(0);
  }

  function save(voter: Voter, patch: Partial<VoterMark>) {
    if (!voter.voter_key) {
      setError("This row cannot be marked yet.");
      return;
    }
    const next = applyPatch(voter, patch, fields);
    const id = (tickets.current[voter.voter_key] ?? 0) + 1;
    tickets.current[voter.voter_key] = id;
    setVoters((current) => current.map((item) => (item.voter_key === voter.voter_key ? { ...item, ...next } : item)));
    setSaving((current) => new Set(current).add(voter.voter_key));
    api<VoterMark>("/voters/mark", { method: "POST", body: JSON.stringify(markBody(next)) }, token)
      .then((saved) => {
        if (tickets.current[voter.voter_key] !== id) return;
        setVoters((current) => {
          const merged = current.map((item) => (item.voter_key === saved.voter_key ? { ...item, ...saved } : item));
          return stillVisible(saved, filters) ? merged : merged.filter((item) => item.voter_key !== saved.voter_key);
        });
        if (!stillVisible(saved, filters)) {
          setTotal((current) => Math.max(0, current - 1));
          if (openKey === saved.voter_key) setOpenKey(null);
        }
      })
      .catch((err: Error) => {
        if (tickets.current[voter.voter_key] !== id) return;
        setVoters((current) => current.map((item) => (item.voter_key === voter.voter_key ? voter : item)));
        setError(err.message);
      })
      .finally(() => {
        if (tickets.current[voter.voter_key] !== id) return;
        setSaving((current) => {
          const copy = new Set(current);
          copy.delete(voter.voter_key);
          return copy;
        });
      });
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
              : ` · ${count(voters.length)} of ${count(total)}${ward ? ` in ward ${ward}` : ""} · ages as of this year`}
            {refreshing ? " · Updating…" : ""}
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
        <Select label="Ward" value={ward} disabled={!bodyId} onChange={(value) => resetPlace(() => setWard(value), true)}>
          <option value="">All wards</option>
          {wards.map((item) => <option key={item} value={item}>Ward {item}</option>)}
        </Select>
        <RollSearch key={`${districtId}|${prakhandId}|${bodyType}|${bodyId}`} disabled={!bodyId} onSearch={onSearch} />
      </section>
      {ready && !wide && (
        <details className="tool-box">
          <summary>Filter and sort</summary>
          <div className="tool-grid">
            <label className="field">
              Sort by
              <select
                value={sort}
                onChange={(event) => {
                  setSort(event.target.value);
                  setDir("asc");
                  setPage(0);
                }}
              >
                <option value="">Roll order</option>
                {COLUMNS.map((column) => (
                  <option key={column.id} value={column.id}>{column.label}</option>
                ))}
              </select>
            </label>
            <label className="field">
              Direction
              <select value={dir} onChange={(event) => { setDir(event.target.value as "asc" | "desc"); setPage(0); }}>
                <option value="asc">Ascending</option>
                <option value="desc">Descending</option>
              </select>
            </label>
            {COLUMNS.map((column) => (
              <FilterControl
                key={column.id}
                column={column}
                fields={fields}
                value={column.id === "ward_no" ? ward : filters[column.id]}
                labeled
                onChange={(value) => {
                  if (column.id === "ward_no") resetPlace(() => setWard(value.replace(/\D/g, "")), true);
                  else setFilter(column.id, value);
                }}
              />
            ))}
          </div>
        </details>
      )}
      {error && <p className="banner">{error}</p>}
      {ready && wide && (
        <div className={refreshing ? "roll-scroll is-refreshing" : "roll-scroll"} ref={scroller} aria-busy={loading}>
          <table className="roll-table">
            <thead>
              <tr>
                {COLUMNS.map((column) => (
                  <th key={column.id} className={headerClass(column.id)} aria-sort={ariaSort(sort, dir, column.id)}>
                    <button type="button" className="sort-btn" aria-pressed={sort === column.id} onClick={() => toggleSort(column.id)}>
                      <span>{column.label}</span>
                      <span aria-hidden>{sort === column.id ? (dir === "asc" ? "↑" : "↓") : ""}</span>
                    </button>
                    <FilterControl
                      column={column}
                      fields={fields}
                      value={column.id === "ward_no" ? ward : filters[column.id]}
                      onChange={(value) => {
                        if (column.id === "ward_no") resetPlace(() => setWard(value.replace(/\D/g, "")), true);
                        else setFilter(column.id, value);
                      }}
                    />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {voters.map((voter, index) => (
                <tr key={voter.voter_key || rowKey(voter, index)}>
                  {COLUMNS.map((column) => (
                    <td key={column.id} className={cellClass(column.id, voter)}>
                      {renderCell(column.id, voter, fields, saving.has(voter.voter_key), (patch) => save(voter, patch))}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {voters.length === 0 && <p className="roll-empty">{loading ? "Looking up voters…" : emptyCopy}</p>}
          <div ref={sentinel} className="more">{more && loading ? "Loading more names…" : more ? "Scroll for more" : voters.length ? `${count(total)} names` : ""}</div>
        </div>
      )}
      {ready && !wide && voters.length > 0 && (
        <div className={refreshing ? "people is-refreshing" : "people"}>
          {voters.map((voter, index) => (
            <button key={voter.voter_key || rowKey(voter, index)} type="button" className="person" onClick={() => setOpenKey(voter.voter_key)}>
              <strong>{voter.name}</strong>
              <span>Ward {blank(voter.ward_no)} · House {blank(voter.house_no)}</span>
              {markLine(voter) && <span>{markLine(voter)}</span>}
            </button>
          ))}
          <div ref={sentinel} className="more">{more && loading ? "Loading more names…" : more ? "Scroll for more" : `${count(total)} names`}</div>
        </div>
      )}
      {ready && !wide && voters.length === 0 && <p className="muted">{loading ? "Looking up voters…" : emptyCopy}</p>}
      {open && (
        <div className="sheet-back" onClick={() => setOpenKey(null)}>
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
              <button type="button" className="ghost" onClick={() => setOpenKey(null)}>Close</button>
            </div>
            <p className="meta">Ward {blank(open.ward_no)} · House {blank(open.house_no)}</p>
            <dl className="details">
              <Detail label="Serial" value={open.serial} />
              <Detail label="EPIC" value={open.epic} />
              <Detail label="Relation" value={[open.relation, open.relation_name].filter(Boolean).join(" ")} hindi />
              <Detail label="Age" value={open.age} />
              <Detail label="Gender" value={open.gender} hindi />
              <Detail label="Part" value={open.part_no} />
              <Detail label="Category" value={open.category} />
              <Detail label="Leader" value={open.leader} />
            </dl>
            <MarkFields voter={open} fields={fields} disabled={saving.has(open.voter_key)} onSave={(patch) => save(open, patch)} />
          </section>
        </div>
      )}
    </>
  );
}

function MarkFields({
  voter,
  fields,
  disabled,
  onSave,
}: {
  voter: Voter;
  fields: VoterFields | null;
  disabled: boolean;
  onSave: (patch: Partial<VoterMark>) => void;
}) {
  return (
    <div className="stack">
      <Choice label="Religion" value={voter.religion} options={fields?.religions ?? []} empty="Select religion" disabled={disabled || !fields} onChange={(religion) => onSave({ religion })} />
      <Choice
        label="Caste"
        value={voter.caste}
        options={fields?.castes.map((item) => item.name) ?? []}
        empty="Select caste"
        disabled={disabled || !fields}
        onChange={(caste) => onSave({ caste, category: categoryFor(fields, caste) })}
      />
      <p className="meta">Category follows the caste{voter.category ? `: ${voter.category}` : "."}</p>
      <Choice
        label="Ideology"
        value={voter.ideology}
        options={fields?.ideologies.map((item) => item.name) ?? []}
        empty="Select ideology"
        disabled={disabled || !fields}
        onChange={(ideology) => onSave({ ideology, leader: leaderFor(fields, ideology) })}
      />
      <p className="meta">Leader follows the party{voter.leader ? `: ${voter.leader}` : "."}</p>
      <Choice
        label="Occupation"
        value={voter.occupation}
        options={fields?.occupations ?? []}
        empty="Select occupation"
        disabled={disabled || !fields}
        onChange={(occupation) => onSave(occupationPatch(voter, occupation))}
      />
      {voter.occupation === "Farmer" && (
        <>
          <p className="meta">Kind of farming. More than one can be selected.</p>
          <KindEditor
            options={fields?.farmer_kinds ?? []}
            selected={voter.farmer_kinds}
            disabled={disabled}
            onChange={(farmer_kinds) => onSave({ farmer_kinds, farmer_other: farmer_kinds.includes("Other") ? voter.farmer_other : "" })}
          />
          {voter.farmer_kinds.includes("Other") && (
            <NoteInput label="Other farming" value={voter.farmer_other} disabled={disabled} onSave={(farmer_other) => onSave({ farmer_other })} />
          )}
        </>
      )}
      {voter.occupation === "Shopkeeper" && (
        <>
          <p className="meta">Kind of shop. More than one can be selected.</p>
          <KindEditor
            options={fields?.shop_kinds ?? []}
            selected={voter.shop_kinds}
            disabled={disabled}
            onChange={(shop_kinds) => onSave({ shop_kinds, shop_other: shop_kinds.includes("Other") ? voter.shop_other : "" })}
          />
          {voter.shop_kinds.includes("Other") && (
            <NoteInput label="Other shop" value={voter.shop_other} disabled={disabled} onSave={(shop_other) => onSave({ shop_other })} />
          )}
        </>
      )}
      {voter.occupation === "Other" && (
        <NoteInput label="Occupation" value={voter.occupation_other} disabled={disabled} onSave={(occupation_other) => onSave({ occupation_other })} />
      )}
    </div>
  );
}

function RollSearch({ disabled, onSearch }: { disabled: boolean; onSearch: (value: string) => void }) {
  const [query, setQuery] = useState("");
  const onSearchRef = useRef(onSearch);
  const skip = useRef(true);
  onSearchRef.current = onSearch;
  useEffect(() => {
    if (skip.current) {
      skip.current = false;
      return;
    }
    const timer = window.setTimeout(() => onSearchRef.current(query.trim()), 320);
    return () => window.clearTimeout(timer);
  }, [query]);
  return (
    <label className="field">
      Search within this roll
      <span className="search">
        <input
          value={query}
          disabled={disabled}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Any column, Hindi or English"
        />
        {query && (
          <button type="button" className="clear" aria-label="Clear search" onClick={() => setQuery("")}>
            ×
          </button>
        )}
      </span>
    </label>
  );
}

function isAbort(err: unknown): boolean {
  return err instanceof Error && err.name === "AbortError";
}

function FilterControl({
  column,
  fields,
  value,
  onChange,
  labeled,
}: {
  column: Column;
  fields: VoterFields | null;
  value: string;
  onChange: (value: string) => void;
  labeled?: boolean;
}) {
  const text = column.filter === "text";
  const [local, setLocal] = useState(value);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  useEffect(() => {
    setLocal(value);
  }, [value]);
  useEffect(() => {
    if (!text || local === value) return;
    const timer = window.setTimeout(() => onChangeRef.current(local), 280);
    return () => window.clearTimeout(timer);
  }, [local, text, value]);
  if (column.filter === "choice") {
    const options = fields && column.options ? column.options(fields) : [];
    const select = (
      <select className={labeled ? undefined : "col-filter"} aria-label={`Filter ${column.label}`} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Any</option>
        {options.map((item) => <option key={item} value={item}>{item}</option>)}
      </select>
    );
    if (!labeled) return select;
    return <label className="field">{column.label}{select}</label>;
  }
  const input = (
    <input
      className={labeled ? undefined : "col-filter"}
      aria-label={`Filter ${column.label}`}
      value={local}
      placeholder={column.id === "ward_no" ? "Ward" : "Filter"}
      inputMode={column.id === "ward_no" || column.id === "serial" || column.id === "age" || column.id === "part_no" ? "numeric" : "text"}
      onChange={(event) => setLocal(event.target.value)}
    />
  );
  if (!labeled) return input;
  return <label className="field">{column.label}{input}</label>;
}

function renderCell(
  id: Column["id"],
  voter: Voter,
  fields: VoterFields | null,
  disabled: boolean,
  onSave: (patch: Partial<VoterMark>) => void,
): ReactNode {
  if (id === "name") return voter.name;
  if (id === "ward_no") return blank(voter.ward_no);
  if (id === "booth_no") return blank(voter.booth_no);
  if (id === "serial") return voter.serial;
  if (id === "epic") return blank(voter.epic);
  if (id === "relation") return blank(voter.relation);
  if (id === "relation_name") return blank(voter.relation_name);
  if (id === "house_no") return blank(voter.house_no);
  if (id === "age") return blank(voter.age);
  if (id === "gender") return blank(voter.gender);
  if (id === "part_no") return blank(voter.part_no);
  if (id === "religion") {
    return (
      <Choice compact label={`Religion for ${voter.name}`} value={voter.religion} options={fields?.religions ?? []} empty="Select" disabled={disabled || !fields} onChange={(religion) => onSave({ religion })} />
    );
  }
  if (id === "caste") {
    return (
      <Choice
        compact
        label={`Caste for ${voter.name}`}
        value={voter.caste}
        options={fields?.castes.map((item) => item.name) ?? []}
        empty="Select"
        disabled={disabled || !fields}
        onChange={(caste) => onSave({ caste, category: categoryFor(fields, caste) })}
      />
    );
  }
  if (id === "category") return <strong className="category">{blank(voter.category)}</strong>;
  if (id === "ideology") {
    return (
      <Choice
        compact
        label={`Ideology for ${voter.name}`}
        value={voter.ideology}
        options={fields?.ideologies.map((item) => item.name) ?? []}
        empty="Select"
        disabled={disabled || !fields}
        onChange={(ideology) => onSave({ ideology, leader: leaderFor(fields, ideology) })}
      />
    );
  }
  if (id === "leader") return <strong className="category">{blank(voter.leader)}</strong>;
  if (id === "occupation") {
    return (
      <Choice
        compact
        label={`Occupation for ${voter.name}`}
        value={voter.occupation}
        options={fields?.occupations ?? []}
        empty="Select"
        disabled={disabled || !fields}
        onChange={(occupation) => onSave(occupationPatch(voter, occupation))}
      />
    );
  }
  if (id === "farmer") {
    if (voter.occupation !== "Farmer") return "—";
    return (
      <KindEditor
        options={fields?.farmer_kinds ?? []}
        selected={voter.farmer_kinds}
        disabled={disabled}
        onChange={(farmer_kinds) => onSave({ farmer_kinds, farmer_other: farmer_kinds.includes("Other") ? voter.farmer_other : "" })}
      />
    );
  }
  if (id === "farmer_other") {
    if (voter.occupation !== "Farmer" || !voter.farmer_kinds.includes("Other")) return blank(voter.farmer_other);
    return <NoteInput compact label={`Other farming for ${voter.name}`} value={voter.farmer_other} disabled={disabled} onSave={(farmer_other) => onSave({ farmer_other })} />;
  }
  if (id === "shop") {
    if (voter.occupation !== "Shopkeeper") return "—";
    return (
      <KindEditor
        options={fields?.shop_kinds ?? []}
        selected={voter.shop_kinds}
        disabled={disabled}
        onChange={(shop_kinds) => onSave({ shop_kinds, shop_other: shop_kinds.includes("Other") ? voter.shop_other : "" })}
      />
    );
  }
  if (id === "shop_other") {
    if (voter.occupation !== "Shopkeeper" || !voter.shop_kinds.includes("Other")) return blank(voter.shop_other);
    return <NoteInput compact label={`Other shop for ${voter.name}`} value={voter.shop_other} disabled={disabled} onSave={(shop_other) => onSave({ shop_other })} />;
  }
  if (voter.occupation !== "Other") return blank(voter.occupation_other);
  return <NoteInput compact label={`Other work for ${voter.name}`} value={voter.occupation_other} disabled={disabled} onSave={(occupation_other) => onSave({ occupation_other })} />;
}

function occupationPatch(voter: Voter, occupation: string): Partial<VoterMark> {
  return {
    occupation,
    farmer_kinds: occupation === "Farmer" ? voter.farmer_kinds : [],
    farmer_other: occupation === "Farmer" ? voter.farmer_other : "",
    shop_kinds: occupation === "Shopkeeper" ? voter.shop_kinds : [],
    shop_other: occupation === "Shopkeeper" ? voter.shop_other : "",
    occupation_other: occupation === "Other" ? voter.occupation_other : "",
  };
}

function applyPatch(voter: Voter, patch: Partial<VoterMark>, fields: VoterFields | null): Voter {
  const next = { ...voter, ...patch };
  if ("caste" in patch) next.category = categoryFor(fields, next.caste ?? "") ?? (patch.category ?? null);
  if ("ideology" in patch) next.leader = leaderFor(fields, next.ideology ?? "") ?? (patch.leader ?? null);
  if (next.occupation !== "Farmer") {
    next.farmer_kinds = [];
    next.farmer_other = "";
  } else if (!next.farmer_kinds.includes("Other")) {
    next.farmer_other = "";
  }
  if (next.occupation !== "Shopkeeper") {
    next.shop_kinds = [];
    next.shop_other = "";
  } else if (!next.shop_kinds.includes("Other")) {
    next.shop_other = "";
  }
  if (next.occupation !== "Other") next.occupation_other = "";
  return next;
}

function markBody(voter: Voter) {
  return {
    voter_key: voter.voter_key,
    religion: voter.religion ?? "",
    caste: voter.caste ?? "",
    occupation: voter.occupation ?? "",
    farmer_kinds: voter.farmer_kinds,
    farmer_other: voter.farmer_other,
    shop_kinds: voter.shop_kinds,
    shop_other: voter.shop_other,
    occupation_other: voter.occupation_other,
    ideology: voter.ideology ?? "",
  };
}

function stillVisible(mark: VoterMark, filters: Filters): boolean {
  if (filters.religion && mark.religion !== filters.religion) return false;
  if (filters.caste && mark.caste !== filters.caste) return false;
  if (filters.category && mark.category !== filters.category) return false;
  if (filters.occupation && mark.occupation !== filters.occupation) return false;
  if (filters.ideology && mark.ideology !== filters.ideology) return false;
  if (filters.leader && mark.leader !== filters.leader) return false;
  if (filters.farmer && !mark.farmer_kinds.includes(filters.farmer)) return false;
  if (filters.shop && !mark.shop_kinds.includes(filters.shop)) return false;
  return true;
}

function markLine(voter: Voter): string {
  const bits = [voter.religion, voter.caste, voter.category, voter.occupation, voter.ideology, voter.leader].filter(Boolean) as string[];
  if (voter.occupation === "Farmer" && voter.farmer_kinds.length) bits.push(voter.farmer_kinds.join(", "));
  if (voter.farmer_other) bits.push(voter.farmer_other);
  if (voter.occupation === "Shopkeeper" && voter.shop_kinds.length) bits.push(voter.shop_kinds.join(", "));
  if (voter.shop_other) bits.push(voter.shop_other);
  if (voter.occupation_other) bits.push(voter.occupation_other);
  return bits.join(" · ");
}

function cellClass(id: Column["id"], voter: Voter): string | undefined {
  if (id === "name") return "pin hindi";
  if (id === "relation" || id === "relation_name" || id === "gender") return "hindi";
  if (id === "ideology") return "mark wide";
  if (id === "farmer" || id === "shop" || id === "caste" || id === "occupation") return "mark";
  if ((id === "farmer_other" && voter.occupation === "Farmer") || (id === "shop_other" && voter.occupation === "Shopkeeper") || (id === "occupation_other" && voter.occupation === "Other")) {
    return "mark";
  }
  return undefined;
}

function headerClass(id: Column["id"]): string | undefined {
  if (id === "name") return "pin";
  if (id === "ideology") return "wide";
  return undefined;
}

function ariaSort(sort: string, dir: "asc" | "desc", id: string): "ascending" | "descending" | "none" {
  if (sort !== id) return "none";
  return dir === "asc" ? "ascending" : "descending";
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
