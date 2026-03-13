import type { HTMLAttributes } from "react";

/**
 * Strategic Gears Badge component.
 *
 * Small label for status indicators, tags, and counts.
 *
 * Variants:
 * - default:  SG mist background, slate text
 * - success:  Green tint
 * - warning:  Orange tint
 * - error:    Red tint
 * - info:     Blue tint
 * - navy:     Navy background, white text
 */

export type BadgeVariant =
  | "default"
  | "success"
  | "warning"
  | "error"
  | "info"
  | "navy";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-sg-mist text-sg-slate",
  success: "bg-emerald-50 text-emerald-700",
  warning: "bg-amber-50 text-amber-700",
  error: "bg-red-50 text-red-700",
  info: "bg-sky-50 text-sg-blue",
  navy: "bg-sg-navy text-white",
};

export function Badge({
  variant = "default",
  className = "",
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={[
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        variantClasses[variant],
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      {...props}
    >
      {children}
    </span>
  );
}
