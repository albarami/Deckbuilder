/**
 * MarkdownViewer — Renders markdown content with SG brand styling.
 *
 * Simple parser supporting headings, bold, italic, lists, and paragraphs.
 * No external markdown library dependency — keeps bundle small.
 */

"use client";

export interface MarkdownViewerProps {
  /** Raw markdown string */
  content: string;
  /** Optional CSS class */
  className?: string;
}

/**
 * Parse basic markdown into React elements.
 *
 * Supports:
 * - # / ## / ### headings
 * - **bold** and *italic*
 * - - unordered list items
 * - 1. ordered list items
 * - Paragraphs separated by blank lines
 */
export function MarkdownViewer({ content, className = "" }: MarkdownViewerProps) {
  const blocks = parseBlocks(content);

  return (
    <div
      className={`prose prose-sm max-w-none text-sg-slate ${className}`}
      data-testid="markdown-viewer"
    >
      {blocks.map((block, i) => (
        <MarkdownBlock key={i} block={block} />
      ))}
    </div>
  );
}

// ── Types ───────────────────────────────────────────────────────────────

interface Block {
  type: "h1" | "h2" | "h3" | "paragraph" | "ul" | "ol";
  content: string;
  items?: string[];
}

// ── Block Parser ────────────────────────────────────────────────────────

function parseBlocks(raw: string): Block[] {
  const lines = raw.split("\n");
  const blocks: Block[] = [];
  let currentList: { type: "ul" | "ol"; items: string[] } | null = null;

  function flushList() {
    if (currentList) {
      blocks.push({
        type: currentList.type,
        content: "",
        items: currentList.items,
      });
      currentList = null;
    }
  }

  for (const line of lines) {
    const trimmed = line.trim();

    // Empty line — flush list, skip
    if (!trimmed) {
      flushList();
      continue;
    }

    // Headings
    if (trimmed.startsWith("### ")) {
      flushList();
      blocks.push({ type: "h3", content: trimmed.slice(4) });
      continue;
    }
    if (trimmed.startsWith("## ")) {
      flushList();
      blocks.push({ type: "h2", content: trimmed.slice(3) });
      continue;
    }
    if (trimmed.startsWith("# ")) {
      flushList();
      blocks.push({ type: "h1", content: trimmed.slice(2) });
      continue;
    }

    // Unordered list
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      if (!currentList || currentList.type !== "ul") {
        flushList();
        currentList = { type: "ul", items: [] };
      }
      currentList.items.push(trimmed.slice(2));
      continue;
    }

    // Ordered list
    const olMatch = trimmed.match(/^\d+\.\s+(.+)/);
    if (olMatch) {
      if (!currentList || currentList.type !== "ol") {
        flushList();
        currentList = { type: "ol", items: [] };
      }
      currentList.items.push(olMatch[1]);
      continue;
    }

    // Paragraph
    flushList();
    blocks.push({ type: "paragraph", content: trimmed });
  }

  flushList();
  return blocks;
}

// ── Inline Formatter ────────────────────────────────────────────────────

function formatInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  // Match **bold** or *italic*
  const regex = /(\*\*(.+?)\*\*|\*(.+?)\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    // Text before match
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    if (match[2]) {
      // **bold**
      parts.push(
        <strong key={match.index} className="font-semibold text-sg-navy">
          {match[2]}
        </strong>
      );
    } else if (match[3]) {
      // *italic*
      parts.push(
        <em key={match.index}>{match[3]}</em>
      );
    }

    lastIndex = match.index + match[0].length;
  }

  // Remaining text
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : [text];
}

// ── Block Renderer ──────────────────────────────────────────────────────

function MarkdownBlock({ block }: { block: Block }) {
  switch (block.type) {
    case "h1":
      return (
        <h1 className="mb-3 text-xl font-bold text-sg-navy">
          {formatInline(block.content)}
        </h1>
      );
    case "h2":
      return (
        <h2 className="mb-2 mt-4 text-lg font-semibold text-sg-navy">
          {formatInline(block.content)}
        </h2>
      );
    case "h3":
      return (
        <h3 className="mb-2 mt-3 text-base font-semibold text-sg-navy">
          {formatInline(block.content)}
        </h3>
      );
    case "paragraph":
      return (
        <p className="mb-2 text-sm leading-relaxed">
          {formatInline(block.content)}
        </p>
      );
    case "ul":
      return (
        <ul className="mb-3 list-disc space-y-1 ps-5 text-sm">
          {block.items?.map((item, i) => (
            <li key={i}>{formatInline(item)}</li>
          ))}
        </ul>
      );
    case "ol":
      return (
        <ol className="mb-3 list-decimal space-y-1 ps-5 text-sm">
          {block.items?.map((item, i) => (
            <li key={i}>{formatInline(item)}</li>
          ))}
        </ol>
      );
  }
}
