import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { HomePage } from "./pages/Home";
import { JobPage } from "./pages/Job";
import { LoginPage } from "./pages/Login";
import { VotersPage } from "./pages/Voters";
import { WizardPage } from "./pages/Wizard";
import { Boot, Chrome } from "./ui";

export function App() {
  const auth = useAuth();
  if (!auth.ready) return <Boot />;

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Private />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/add" element={<WizardPage />} />
        <Route path="/download" element={<Navigate to="/add" replace />} />
        <Route path="/jobs/:jobId" element={<JobPage />} />
        <Route path="/voters" element={<VotersPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function Private() {
  const auth = useAuth();
  if (!auth.session) return <Navigate to="/login" replace />;
  return (
    <Chrome>
      <Outlet />
    </Chrome>
  );
}
