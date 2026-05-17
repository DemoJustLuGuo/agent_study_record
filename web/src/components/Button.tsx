import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  loading?: boolean;
  icon?: ReactNode;
};

const variantClass: Record<ButtonVariant, string> = {
  primary:
    "border-transparent bg-console-accent text-console-bg hover:bg-green-400 shadow-md shadow-console-accent/20",
  secondary:
    "border-white/10 bg-white/5 text-console-text hover:bg-white/10 backdrop-blur-sm",
  danger:
    "border-console-danger/20 bg-console-danger/10 text-red-300 hover:bg-console-danger/20 hover:text-red-200",
  ghost:
    "border-transparent bg-transparent text-console-subdued hover:bg-white/5 hover:text-console-text",
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
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border px-4 py-2 text-sm font-semibold transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-50 active:scale-[0.98] ${variantClass[variant]} ${className}`}
      disabled={disabled || loading}
      type="button"
      {...props}
    >
      {icon}
      <span>{loading ? "处理中..." : children}</span>
    </button>
  );
}
