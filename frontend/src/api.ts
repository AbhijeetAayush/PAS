export type District = { id: string; name: string };
export type Prakhand = { id: string; name: string };
export type Body = { id: string; name: string; body_type: string; publication: string };
export type IngestResult = { status: string; job_id: string };
export type JobFile = {
  ward_no: number | null;
  status: string;
  page_count: number;
  pages_ready: number;
  voter_count: number;
  error: string | null;
};
export type JobSummary = {
  id: string;
  body_name: string;
  body_type: string;
  body_id: string;
  district_id: string;
  district_name: string;
  prakhand_id: string;
  prakhand_name: string;
  status: string;
  created_at: string;
};
export type JobCounts = { all: number; reading: number; ready: number; failed: number };
export type Job = {
  id: string;
  status: string;
  error: string | null;
  district_id: string;
  district_name: string;
  prakhand_id: string;
  prakhand_name: string;
  body_type: string;
  body_id: string;
  body_name: string;
  publication: string;
  voter_count: number;
  files: JobFile[];
};
export type CasteOption = { name: string; category: string };
export type PartyOption = { name: string; leader: string };
export type VoterFields = {
  religions: string[];
  castes: CasteOption[];
  categories: string[];
  occupations: string[];
  farmer_kinds: string[];
  shop_kinds: string[];
  ideologies: PartyOption[];
  leaders: string[];
  age_bands: string[];
};
export type VoterMark = {
  voter_key: string;
  religion: string | null;
  caste: string | null;
  category: string | null;
  occupation: string | null;
  farmer_kinds: string[];
  farmer_other: string;
  shop_kinds: string[];
  shop_other: string;
  occupation_other: string;
  ideology: string | null;
  leader: string | null;
};
export type Voter = {
  serial: string;
  epic: string | null;
  name: string;
  relation: string | null;
  relation_name: string | null;
  house_no: string | null;
  age: string | null;
  gender: string | null;
  assembly_ref: string | null;
  part_no: string | null;
  ward_no?: string | number | null;
  booth_no?: string | null;
} & VoterMark;

const base = () => {
  const url = import.meta.env.VITE_API_URL;
  if (!url) {
    throw new Error("Set VITE_API_URL in frontend/.env");
  }
  return url.replace(/\/$/, "");
};

export async function api<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${base()}${path}`, { ...options, headers });
  const text = await response.text();
  let payload: { detail?: string } = {};
  if (text) {
    try {
      payload = JSON.parse(text) as { detail?: string };
    } catch {
      throw new Error(text.slice(0, 180));
    }
  }
  if (!response.ok) {
    throw new Error(payload.detail || `Request failed (${response.status})`);
  }
  return payload as T;
}
