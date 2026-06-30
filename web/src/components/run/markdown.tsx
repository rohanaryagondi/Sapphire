"use client";
import * as React from "react";
import { stripEmoji } from "@/lib/utils";
import { useFirm } from "@/lib/store";

/** Label -> agent id map for citation pills. */
const CITATION_TO_AGENT: Record<string, string> = {
  "EMET": "emet-runner",
  "Internal moat": "internal-science-lead",
  "External Models": "q-models-runner",
  "FDA memory": "fda-institutional-memory",
  "Patent/IP": "patent-ip",
  "Clinical-trial registry": "clinical-trial-registry",
  "Post-market safety": "post-market-safety",
  "Payer": "payer",
  "Manufacturing/CMC": "manufacturing-cmc",
  "Patient advocacy": "patient-advocacy",
  "KOL/social": "kol-social",
  "Policy/legislative": "policy-legislative",
  "DEA": "dea-scheduling",
  "Global regulatory": "global-regulatory-divergence",
};

function CitationPill({ label, turnId }: { label: string; turnId?: string }): React.JSX.Element {
  const select = useFirm((s) => s.select);
  const agentId = CITATION_TO_AGENT[label];
  const clickable = Boolean(agentId && turnId);

  return (
    <span
      role={clickable ? "button" : undefined}
      onClick={
        clickable
          ? () => select({ kind: "agent", agentId: agentId!, turnId: turnId! })
          : undefined
      }
      style={{
        display: "inline-flex",
        alignItems: "center",
        borderRadius: "6px",
        border: "1px solid var(--color-q-bd, var(--color-border))",
        background: "var(--color-q-soft, var(--color-elevated))",
        padding: "0 6px",
        fontSize: "11px",
        fontWeight: 500,
        color: clickable ? "var(--color-q-text, var(--color-accent))" : "var(--color-fg-faint)",
        cursor: clickable ? "pointer" : "default",
        verticalAlign: "baseline",
        lineHeight: "1.6",
        marginLeft: "3px",
        transition: "background 0.15s",
        whiteSpace: "nowrap",
      }}
      title={clickable ? `Open ${label} info` : label}
    >
      {label}
    </span>
  );
}

/**
 * InlineContent -- renders **bold** and [[Label]] citation pills inline.
 * turnId is needed to make pills clickable (opens the agent's Info tab).
 */
function InlineContent({ text, turnId }: { text: string; turnId?: string }): React.JSX.Element {
  // Split on **bold** and [[Citation]] tokens
  const segments: Array<{ type: "text" | "bold" | "citation"; value: string }> = [];

  // Tokenize: find ** and [[ patterns
  const regex = /\*\*(.+?)\*\*|\[\[(.+?)\]\]/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: "text", value: text.slice(lastIndex, match.index) });
    }
    if (match[1] !== undefined) {
      segments.push({ type: "bold", value: match[1] });
    } else if (match[2] !== undefined) {
      segments.push({ type: "citation", value: match[2] });
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    segments.push({ type: "text", value: text.slice(lastIndex) });
  }

  return (
    <>
      {segments.map((seg, i) => {
        if (seg.type === "bold") {
          return <strong key={i} style={{ fontWeight: 600 }}>{seg.value}</strong>;
        }
        if (seg.type === "citation") {
          return <CitationPill key={i} label={seg.value} turnId={turnId} />;
        }
        return <React.Fragment key={i}>{seg.value}</React.Fragment>;
      })}
    </>
  );
}

/**
 * MarkdownDoc -- dependency-free Markdown renderer for Sapphire diligence reports.
 *
 * Handles:
 *   - # / ## / ### headings (violet, sized proportionally)
 *   - paragraphs
 *   - **bold** inline
 *   - [[Label]] citation pills (clickable when turnId is provided)
 *   - - and 1. lists
 *   - blank-line spacing
 *
 * No new npm deps. Pure React + inline styles.
 */
export function MarkdownDoc({ text, turnId }: { text: string; turnId?: string }): React.JSX.Element {
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
        fontSize: "19px",
        fontWeight: 700,
        color: "var(--color-accent)",
        marginTop: "18px",
        marginBottom: "6px",
        lineHeight: 1.3,
      };
    // level === 3
    return {
      fontSize: "16px",
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

    // Blank line -- spacing handled by paragraph margins; skip.
    if (line.trim() === "") {
      i++;
      continue;
    }

    // Headings
    const h3 = line.match(/^###\s+(.*)/);
    if (h3) {
      nodes.push(
        <div key={i} style={headingStyle(3)}>
          <InlineContent text={stripEmoji(h3[1])} turnId={turnId} />
        </div>,
      );
      i++;
      continue;
    }
    const h2 = line.match(/^##\s+(.*)/);
    if (h2) {
      nodes.push(
        <div key={i} style={headingStyle(2)}>
          <InlineContent text={stripEmoji(h2[1])} turnId={turnId} />
        </div>,
      );
      i++;
      continue;
    }
    const h1 = line.match(/^#\s+(.*)/);
    if (h1) {
      nodes.push(
        <div key={i} style={headingStyle(1)}>
          <InlineContent text={stripEmoji(h1[1])} turnId={turnId} />
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
            margin: "6px 0 14px 0",
          }}
        >
          {items.map((item, j) => (
            <li
              key={j}
              style={{
                display: "flex",
                gap: "8px",
                fontSize: "16px",
                lineHeight: 1.7,
                color: "var(--color-fg)",
                marginBottom: "4px",
              }}
            >
              <span style={{ color: "var(--color-fg-faint)", flexShrink: 0, marginTop: "2px" }}>·</span>
              <span>
                <InlineContent text={stripEmoji(item)} turnId={turnId} />
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
            margin: "6px 0 14px 0",
          }}
        >
          {items.map((item, j) => (
            <li
              key={j}
              style={{
                fontSize: "16px",
                lineHeight: 1.7,
                color: "var(--color-fg)",
                marginBottom: "4px",
              }}
            >
              <InlineContent text={stripEmoji(item)} turnId={turnId} />
            </li>
          ))}
        </ol>,
      );
      continue;
    }

    // Paragraph -- collect consecutive non-blank, non-heading, non-list lines
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
            fontSize: "16px",
            lineHeight: 1.7,
            color: "var(--color-fg)",
            margin: "0 0 14px 0",
            maxWidth: "70ch",
          }}
        >
          <InlineContent text={stripEmoji(paraText)} turnId={turnId} />
        </p>,
      );
    }
  }

  return (
    <div style={{ fontFamily: "inherit", maxWidth: "70ch" }}>
      {nodes}
    </div>
  );
}
