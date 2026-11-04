import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth";
import { Wordmark } from "../ui";

export function LoginPage() {
  const auth = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [mode, setMode] = useState<"in" | "up">("in");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (auth.session) return <Navigate to="/" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (mode === "in") {
        await auth.signIn(email, password);
      } else {
        setMessage(await auth.signUp(email, password));
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Login failed";
      setError(message === "Failed to fetch" ? "The server didn't respond. Check the connection and refresh." : message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="gate">
      <section className="gate-hero">
        <Wordmark size="xl" />
        <h1 className="display">Voter rolls, kept once.</h1>
        <p className="lead">Open a panchayat roll once, follow each ward as it is read, then find any voter.</p>
      </section>
      <form className="gate-form" onSubmit={submit}>
        <div className="segment" role="tablist" aria-label="Account">
          <button type="button" aria-pressed={mode === "in"} onClick={() => setMode("in")}>Sign in</button>
          <button type="button" aria-pressed={mode === "up"} onClick={() => setMode("up")}>Create account</button>
        </div>
        {auth.error && <p className="banner">{auth.error === "Failed to fetch" ? "The server didn't respond. Check the connection and refresh." : auth.error}</p>}
        <label className="field">
          Email
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            inputMode="email"
            required
          />
        </label>
        <label className="field">
          Password
          <span className="password">
            <input
              type={show ? "text" : "password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={mode === "in" ? "current-password" : "new-password"}
              minLength={6}
              required
            />
            <button type="button" className="reveal" aria-pressed={show} onClick={() => setShow((value) => !value)}>
              {show ? "Hide" : "Show"}
            </button>
          </span>
        </label>
        {message && <p className="banner note">{message}</p>}
        {error && <p className="banner">{error}</p>}
        <button className="primary" disabled={busy || !auth.ready} type="submit">
          {busy ? "Please wait" : mode === "in" ? "Sign in" : "Create account"}
        </button>
      </form>
    </div>
  );
}
