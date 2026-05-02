"use client";

import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  loading?: boolean;
};

export function LoadingButton({ loading, children, disabled, ...props }: Props) {
  return (
    <button {...props} disabled={disabled || loading}>
      {loading ? <span className="spinner-border spinner-border-sm me-2" aria-hidden="true" /> : null}
      {children}
    </button>
  );
}
