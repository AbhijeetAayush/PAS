import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type Body, type District, type Prakhand } from "../api";
import { useAuth } from "../auth";
import { MultiPicker, Picker } from "../ui";

const STEPS = ["District", "Prakhand", "Type", "Panchayat", "Confirm"];

export function WizardPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const token = auth.session?.access_token ?? "";
  const [step, setStep] = useState(0);
  const [districts, setDistricts] = useState<District[]>([]);
  const [prakhands, setPrakhands] = useState<Prakhand[]>([]);
  const [bodies, setBodies] = useState<Body[]>([]);
  const [loadingDistricts, setLoadingDistricts] = useState(true);
  const [loadingPrakhands, setLoadingPrakhands] = useState(false);
  const [loadingBodies, setLoadingBodies] = useState(false);
  const [districtId, setDistrictId] = useState("");
  const [prakhandId, setPrakhandId] = useState("");
  const [bodyType, setBodyType] = useState<"gram_panchayat" | "nagar_panchayat">("nagar_panchayat");
  const [bodyIds, setBodyIds] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<{ districts: District[] }>("/catalog/districts")
      .then((payload) => setDistricts(payload.districts))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoadingDistricts(false));
  }, []);

  useEffect(() => {
    setPrakhandId("");
    setPrakhands([]);
    if (!districtId) return;
    setLoadingPrakhands(true);
    api<{ prakhands: Prakhand[] }>(`/catalog/prakhands?district_id=${districtId}`)
      .then((payload) => setPrakhands(payload.prakhands))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoadingPrakhands(false));
  }, [districtId]);

  useEffect(() => {
    setBodyIds([]);
    setBodies([]);
    if (!districtId || !prakhandId) return;
    setLoadingBodies(true);
    const query = new URLSearchParams({ district_id: districtId, prakhand_id: prakhandId, body_type: bodyType });
    api<{ bodies: Body[] }>(`/catalog/bodies?${query}`)
      .then((payload) => setBodies(payload.bodies))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoadingBodies(false));
  }, [bodyType, districtId, prakhandId]);

  const district = districts.find((item) => item.id === districtId);
  const prakhand = prakhands.find((item) => item.id === prakhandId);
  const chosen = bodies.filter((item) => bodyIds.includes(item.id));
  const canNext = [Boolean(districtId), Boolean(prakhandId), true, chosen.length > 0, chosen.length > 0][step];

  async function submit() {
    setBusy(true);
    setError("");
    setNote("");
    try {
      const result = await api<{ results: { status: string; job_id: string }[] }>(
        "/ingest",
        {
          method: "POST",
          body: JSON.stringify({
            district_id: districtId,
            prakhand_id: prakhandId,
            body_type: bodyType,
            body_ids: chosen.map((item) => item.id),
          }),
        },
        token,
      );
      const started = result.results.filter((item) => item.status !== "already_downloaded");
      if (started.length === 0) {
        setNote(result.results.length === 1 ? "This roll is already in the library." : "These rolls are already in the library.");
        return;
      }
      if (started.length === 1) {
        navigate(`/jobs/${started[0].job_id}`);
        return;
      }
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start");
    } finally {
      setBusy(false);
    }
  }

  const votersQuery = new URLSearchParams({
    district_id: districtId,
    prakhand_id: prakhandId,
    body_type: bodyType,
    body_id: chosen[0]?.id ?? "",
  });

  return (
    <>
      <div className="stack">
        <p className="eyebrow">Add a roll</p>
        <p className="meta">Step {step + 1} of {STEPS.length}</p>
        <h1 className="display">{STEPS[step]}</h1>
        <div className="steps" aria-hidden>
          {STEPS.map((label, index) => <span key={label} className={index <= step ? "on" : ""} />)}
        </div>
      </div>

      {step === 0 && (
        <Picker
          label="Search districts"
          placeholder="Type a district"
          options={districts}
          value={districtId}
          onChange={setDistrictId}
          loading={loadingDistricts}
          empty="No district matches."
        />
      )}
      {step === 1 && (
        <Picker
          label="Search prakhands"
          placeholder="Type a prakhand"
          options={prakhands}
          value={prakhandId}
          onChange={setPrakhandId}
          loading={loadingPrakhands}
          empty="No prakhand matches."
        />
      )}
      {step === 2 && (
        <div className="kinds">
          <button type="button" className={bodyType === "nagar_panchayat" ? "kind on" : "kind"} aria-pressed={bodyType === "nagar_panchayat"} onClick={() => setBodyType("nagar_panchayat")}>
            <strong>Nagar panchayat</strong>
            <small>Town wards from the published roll</small>
          </button>
          <button type="button" className={bodyType === "gram_panchayat" ? "kind on" : "kind"} aria-pressed={bodyType === "gram_panchayat"} onClick={() => setBodyType("gram_panchayat")}>
            <strong>Gram panchayat</strong>
            <small>Village wards from the SEC roll</small>
          </button>
        </div>
      )}
      {step === 3 && (
        <MultiPicker
          label={bodyType === "nagar_panchayat" ? "Search nagar panchayats" : "Search gram panchayats"}
          placeholder="Type a name"
          options={bodies.map((item) => ({ id: item.id, name: item.name }))}
          values={bodyIds}
          onChange={setBodyIds}
          loading={loadingBodies}
          empty={districtId && prakhandId ? "None are listed for this prakhand." : "Choose a prakhand first."}
        />
      )}
      {step === 4 && (
        <section className="panel">
          <dl className="summary">
            <div><dt>District</dt><dd>{district?.name}</dd></div>
            <div><dt>Prakhand</dt><dd>{prakhand?.name}</dd></div>
            <div><dt>Type</dt><dd>{bodyType === "nagar_panchayat" ? "Nagar panchayat" : "Gram panchayat"}</dd></div>
            <div><dt>{chosen.length === 1 ? "Panchayat" : "Panchayats"}</dt><dd>{chosen.length === 1 ? chosen[0].name : chosen.length}</dd></div>
          </dl>
          {chosen.length > 1 && (
            <ul className="options chosen">
              {chosen.map((item) => (
                <li key={item.id} className="option"><span className="hindi">{item.name}</span></li>
              ))}
            </ul>
          )}
          <p className="muted">Each selected panchayat is read once. Ones already in the library are left as they are, and the rest start together.</p>
          {note && (
            <p className="banner ok">
              {note}{" "}
              {chosen.length === 1 ? <Link to={`/voters?${votersQuery}`}>Open in Voters</Link> : <Link to="/">Open the library</Link>}
            </p>
          )}
        </section>
      )}

      {error && <p className="banner">{error}</p>}
      <div className={step === 0 ? "step-actions solo" : "step-actions"}>
        {step > 0 && <button className="ghost" type="button" onClick={() => setStep((value) => value - 1)}>Back</button>}
        {step < 4 && (
          <button className="primary" type="button" disabled={!canNext} onClick={() => setStep((value) => value + 1)}>
            Continue
          </button>
        )}
        {step === 4 && (
          <button className="primary" type="button" disabled={busy || chosen.length === 0} onClick={submit}>
            {busy ? "Starting" : chosen.length > 1 ? `Start reading ${chosen.length}` : "Start reading"}
          </button>
        )}
      </div>
    </>
  );
}
