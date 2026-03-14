import { forwardRef, type ButtonHTMLAttributes } from "react";

/**
 * Strategic Gears Button component.
 *
 * Variants:
 * - primary:   SG blue background, white text (default)
 * - secondary: SG navy outline, navy text
 * - ghost:     Transparent with hover state
 * - danger:    SG orange background, white text
 *
 * Sizes: sm, md (default), lg
 */

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-sg-blue text-white hover:bg-sg-teal focus-visible:ring-sg-blue active:bg-sg-navy",
  secondary:
    "border border-sg-navy text-sg-navy hover:bg-sg-navy hover:text-white focus-visible:ring-sg-navy active:bg-sg-navy/90",
  ghost:
    "text-sg-slate hover:bg-sg-mist focus-visible:ring-sg-blue active:bg-sg-border/50",
  danger:
    "bg-sg-orange text-white hover:bg-sg-orange/90 focus-visible:ring-sg-orange active:bg-sg-orange/80",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-4 py-2 text-sm",
  lg: "px-6 py-2.5 text-base",
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      size = "md",
      loading = false,
      disabled,
      className = "",
      children,
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || loading;

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        className={[
          // Base styles
          "inline-flex items-center justify-center gap-2 rounded-lg font-semibold",
          "transition-colors duration-150 ease-in-out",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
          // Variant
          variantClasses[variant],
          // Size
          sizeClasses[size],
          // Disabled state
          isDisabled && "cursor-not-allowed opacity-50",
          // Custom classes
          className,
        ]
          .filter(Boolean)
          .join(" ")}
        {...props}
      >
        {loading && <Spinner />}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";

export { Button };

/** Inline spinner for loading state */
function Spinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}
