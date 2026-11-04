export function bodyKind(type: string): string {
  if (type === "nagar_panchayat") return "Nagar panchayat";
  if (type === "gram_panchayat") return "Gram panchayat";
  return type;
}

export function tone(status: string, pagesReady = 0, pageCount = 0): "ready" | "failed" | "reading" | "wait" {
  if (status === "ready") return "ready";
  if (status === "failed") return "failed";
  if (status === "reading") return "reading";
  if (status === "stored" && pageCount > 0 && pagesReady > 0 && pagesReady < pageCount) return "reading";
  return "wait";
}

export function statusLabel(status: string, pagesReady = 0, pageCount = 0): string {
  const kind = tone(status, pagesReady, pageCount);
  if (kind === "ready") return "Available";
  if (kind === "failed") return "Incomplete";
  if (kind === "reading") return "Reading";
  if (status === "queued") return "Queued";
  return "Waiting";
}

export function when(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const minutes = Math.round((Date.now() - date.getTime()) / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.round(hours / 24);
  if (days < 14) return `${days} day${days === 1 ? "" : "s"} ago`;
  return date.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export function count(value: number): string {
  return value.toLocaleString("en-IN");
}
