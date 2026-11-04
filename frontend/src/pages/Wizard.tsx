import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type Body, type District, type Prakhand } from "../api";
import { useAuth } from "../auth";
import { Picker } from "../ui";

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
  const [bodyId, setBodyId] = useState("");
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
    setBodyId("");
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
  const body = bodies.find((item) => item.id === bodyId);
  const canNext = [Boolean(districtId), Boolean(prakhandId), true, Boolean(bodyId), Boolean(bodyId)][step];

  async function submit() {
    setBusy(true);
    setError("");
    setNote("");
    try {
      const result = await api<{ status: string; job_id: string }>(
        "/ingest",
        {
          method: "POST",
          body: JSON.stringify({
            district_id: districtId,
            prakhand_id: prakhandId,
            body_type: bodyType,
            body_id: bodyId,
          }),
        },
        token,
      );
      if (result.status === "already_downloaded") {
        setNote("This roll is already in the library.");
        return;
      }
      navigate(`/jobs/${result.job_id}`);
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
    body_id: bodyId,
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
        <Picker
          label={bodyType === "nagar_panchayat" ? "Search nagar panchayats" : "Search gram panchayats"}
          placeholder="Type a name"
          options={bodies.map((item) => ({ id: item.id, name: item.name }))}
          value={bodyId}
          onChange={setBodyId}
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
            <div><dt>Panchayat</dt><dd>{body?.name}</dd></div>
          </dl>
          <p className="muted">A panchayat is read once. Opening it again uses the copy already kept.</p>
          {note && (
            <p className="banner ok">
              {note}{" "}
              <Link to={`/voters?${votersQuery}`}>Open in Voters</Link>
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
          <button className="primary" type="button" disabled={busy || !bodyId} onClick={submit}>
            {busy ? "Starting" : "Start reading"}
          </button>
        )}
      </div>
    </>
  );
}
