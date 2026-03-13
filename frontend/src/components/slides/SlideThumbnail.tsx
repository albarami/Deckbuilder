/**
 * SlideThumbnail — Image thumbnail for rendered slide mode.
 *
 * Uses intersection observer for lazy loading.
 * Shows a placeholder skeleton until the image loads.
 */

"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import type { SlideInfo } from "@/lib/types/slides";

export interface SlideThumbnailProps {
  slide: SlideInfo;
  /** Full thumbnail URL */
  thumbnailUrl: string;
  /** Whether this slide is currently selected */
  isSelected?: boolean;
  /** Click handler */
  onClick?: (slide: SlideInfo) => void;
}

export function SlideThumbnail({
  slide,
  thumbnailUrl,
  isSelected = false,
  onClick,
}: SlideThumbnailProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);
  const [hasError, setHasError] = useState(false);

  // Intersection observer for lazy loading
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.unobserve(el);
        }
      },
      { rootMargin: "100px" },
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const handleClick = useCallback(() => {
    onClick?.(slide);
  }, [onClick, slide]);

  return (
    <div
      ref={containerRef}
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleClick();
        }
      }}
      className={[
        "group cursor-pointer rounded-lg border-2 transition-all",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sg-blue focus-visible:ring-offset-2",
        isSelected
          ? "border-sg-blue shadow-md"
          : "border-sg-border hover:border-sg-teal hover:shadow-sm",
      ].join(" ")}
      data-testid={`slide-thumbnail-${slide.slide_number}`}
      aria-label={`Slide ${slide.slide_number}: ${slide.text_preview}`}
    >
      {/* Thumbnail image area - 16:9 aspect ratio */}
      <div className="relative aspect-video overflow-hidden rounded-t-md bg-sg-mist">
        {isVisible && !hasError && (
          <img
            src={thumbnailUrl}
            alt={`Slide ${slide.slide_number}`}
            loading="lazy"
            onLoad={() => setIsLoaded(true)}
            onError={() => setHasError(true)}
            className={[
              "h-full w-full object-cover transition-opacity duration-300",
              isLoaded ? "opacity-100" : "opacity-0",
            ].join(" ")}
          />
        )}

        {/* Loading skeleton */}
        {isVisible && !isLoaded && !hasError && (
          <div className="absolute inset-0 animate-pulse bg-sg-mist" />
        )}

        {/* Error fallback */}
        {hasError && (
          <div className="absolute inset-0 flex items-center justify-center">
            <SlideIconFallback />
          </div>
        )}

        {/* Slide number badge */}
        <div className="absolute bottom-1.5 end-1.5 rounded bg-sg-navy/70 px-1.5 py-0.5 text-[10px] font-medium text-white">
          {slide.slide_number}
        </div>
      </div>

      {/* Caption */}
      <div className="px-2.5 py-2">
        <p className="truncate text-xs text-sg-slate/70">
          {slide.text_preview || slide.section_id}
        </p>
      </div>
    </div>
  );
}

function SlideIconFallback() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      className="h-8 w-8 text-sg-slate/30"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 01-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0112 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25m-17.25 0h7.5c.621 0 1.125.504 1.125 1.125M3.375 8.25c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125m17.25-3.75h-7.5c-.621 0-1.125.504-1.125 1.125m8.625-1.125c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125"
      />
    </svg>
  );
}
