export function formatDate(value: string | null | undefined) {
  if (!value) {
    return "—";
  }
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

export function statusLabel(status: string) {
  if (status === "active") return "Идет";
  if (status === "created") return "Создана";
  if (status === "stopped") return "Остановлена";
  return status;
}

export function statusClass(status: string) {
  if (status === "active") return "text-bg-success";
  if (status === "created") return "text-bg-warning";
  if (status === "stopped") return "text-bg-secondary";
  return "text-bg-light";
}
