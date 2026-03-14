import type { HTMLAttributes } from "react";

/**
 * Strategic Gears Card component.
 *
 * A branded container surface with consistent border, shadow, and padding.
 *
 * Variants:
 * - default:  Standard card with subtle shadow
 * - elevated: Higher elevation for modals/popovers
 * - flat:     No shadow, border only
 */

export type CardVariant = "default" | "elevated" | "flat";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: CardVariant;
  noPadding?: boolean;
}

const variantClasses: Record<CardVariant, string> = {
  default: "sg-card",
  elevated: "sg-card-elevated",
  flat: "bg-sg-white rounded-lg border border-sg-border",
};

export function Card({
  variant = "default",
  noPadding = false,
  className = "",
  children,
  ...props
}: CardProps) {
  return (
    <div
      className={[
        variantClasses[variant],
        !noPadding && "p-card",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      {...props}
    >
      {children}
    </div>
  );
}
