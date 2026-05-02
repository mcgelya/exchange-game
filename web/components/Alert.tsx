"use client";

export function Alert({ message, tone = "danger" }: { message: string | null; tone?: "danger" | "success" | "info" | "warning" }) {
  if (!message) return null;

  return (
    <div className={`alert alert-${tone} mb-3`} role="alert">
      {message}
    </div>
  );
}
