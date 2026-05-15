import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  loading?: boolean;
  icon?: ReactNode;
};

const variantClass: Record<ButtonVariant, string> = {
  primary:
    "border-console-accent bg-console-accent text-console-bg hover:bg-green-400",
  secondary:
    "border-console-border bg-console-muted text-console-text hover:bg-slate-700",
  danger:
    "border-console-danger bg-console-danger/15 text-red-200 hover:bg-console-danger/25",
  ghost:
    "border-transparent bg-transparent text-console-subdued hover:bg-console-muted hover:text-console-text",
};

export function Button({
  children,
  className = "",
  disabled,
  icon,
  loading,
  variant = "secondary",
  ...props
}: ButtonProps) {
  return (
    <button
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${variantClass[variant]} ${className}`}
      disabled={disabled || loading}
      type="button"
      {...props}
    >
      {icon}
      <span>{loading ? "处理中..." : children}</span>
    </button>
  );
}
