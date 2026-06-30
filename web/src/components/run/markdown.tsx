"use client";
import * as React from "react";
import { stripEmoji } from "@/lib/utils";

/** Render inline bold — splits on ** and alternates plain/bold spans. */
function InlineBold({ text }: { text: string }): React.JSX.Element {
  const parts = text.split("**");
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <strong key={i} style={{ fontWeight: 600 }}>
            {part}
          </strong>
        ) : (
          <React.Fragment key={i}>{part}</React.Fragment>
        ),
      )}
    </>
  );
}

/**
 * MarkdownDoc — dependency-free Markdown renderer for Sapphire diligence reports.
 *
 * Handles:
 *   - # / ## / ### headings (violet, sized proportionally)
 *   - paragraphs
 *   - **bold** inline
 *   - - and 1. lists
 *   - blank-line spacing
 *
 * No new npm deps. Pure React + inline styles.
 */
export function MarkdownDoc({ text }: { text: string }): React.JSX.Element {
  const lines = text.split("\n");

  // Heading style map
  const headingStyle = (level: number): React.CSSProperties => {
    if (level === 1)
      return {
        fontSize: "18px",
        fontWeight: 700,
        color: "var(--color-accent)",
        marginTop: "20px",
        marginBottom: "8px",
        lineHeight: 1.3,
      };
    if (level === 2)
      return {
        fontSize: "16px",
        fontWeight: 700,
        color: "var(--color-accent)",
        marginTop: "18px",
        marginBottom: "6px",
        lineHeight: 1.3,
      };
    // level === 3
    return {
      fontSize: "14.5px",
      fontWeight: 700,
      color: "var(--color-accent)",
      marginTop: "14px",
      marginBottom: "4px",
      lineHeight: 1.3,
    };
  };

  const nodes: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Blank line — spacing handled by paragraph margins; skip.
    if (line.trim() === "") {
      i++;
      continue;
    }

    // Headings
    const h3 = line.match(/^###\s+(.*)/);
    if (h3) {
      nodes.push(
        <div key={i} style={headingStyle(3)}>
          <InlineBold text={stripEmoji(h3[1])} />
        </div>,
      );
      i++;
      continue;
    }
    const h2 = line.match(/^##\s+(.*)/);
    if (h2) {
      nodes.push(
        <div key={i} style={headingStyle(2)}>
          <InlineBold text={stripEmoji(h2[1])} />
        </div>,
      );
      i++;
      continue;
    }
    const h1 = line.match(/^#\s+(.*)/);
    if (h1) {
      nodes.push(
        <div key={i} style={headingStyle(1)}>
          <InlineBold text={stripEmoji(h1[1])} />
        </div>,
      );
      i++;
      continue;
    }

    // Horizontal rule
    if (/^---+$/.test(line.trim())) {
      nodes.push(
        <hr
          key={i}
          style={{
            border: "none",
            borderTop: "1px solid var(--color-border)",
            margin: "16px 0",
          }}
        />,
      );
      i++;
      continue;
    }

    // Unordered list item: starts with "- "
    if (/^-\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^-\s/.test(lines[i])) {
        items.push(lines[i].replace(/^-\s/, ""));
        i++;
      }
      nodes.push(
        <ul
          key={`ul-${i}`}
          style={{
            listStyleType: "none",
            paddingLeft: 0,
            margin: "6px 0 10px 0",
          }}
        >
          {items.map((item, j) => (
            <li
              key={j}
              style={{
                display: "flex",
                gap: "8px",
                fontSize: "15px",
                lineHeight: 1.6,
                color: "var(--color-fg-muted)",
                marginBottom: "4px",
              }}
            >
              <span style={{ color: "var(--color-fg-faint)", flexShrink: 0, marginTop: "2px" }}>·</span>
              <span>
                <InlineBold text={stripEmoji(item)} />
              </span>
            </li>
          ))}
        </ul>,
      );
      continue;
    }

    // Ordered list item: starts with "1. " or "N. "
    if (/^\d+\.\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s/, ""));
        i++;
      }
      nodes.push(
        <ol
          key={`ol-${i}`}
          style={{
            paddingLeft: "20px",
            margin: "6px 0 10px 0",
          }}
        >
          {items.map((item, j) => (
            <li
              key={j}
              style={{
                fontSize: "15px",
                lineHeight: 1.6,
                color: "var(--color-fg-muted)",
                marginBottom: "4px",
              }}
            >
              <InlineBold text={stripEmoji(item)} />
            </li>
          ))}
        </ol>,
      );
      continue;
    }

    // Paragraph — collect consecutive non-blank, non-heading, non-list lines
    const paraLines: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !/^#+\s/.test(lines[i]) &&
      !/^-\s/.test(lines[i]) &&
      !/^\d+\.\s/.test(lines[i]) &&
      !/^---+$/.test(lines[i].trim())
    ) {
      paraLines.push(lines[i]);
      i++;
    }
    if (paraLines.length > 0) {
      const paraText = paraLines.join(" ");
      nodes.push(
        <p
          key={`p-${i}`}
          style={{
            fontSize: "15px",
            lineHeight: 1.65,
            color: "var(--color-fg-muted)",
            margin: "0 0 10px 0",
            maxWidth: "72ch",
          }}
        >
          <InlineBold text={stripEmoji(paraText)} />
        </p>,
      );
    }
  }

  return (
    <div style={{ fontFamily: "inherit" }}>
      {nodes}
    </div>
  );
}
