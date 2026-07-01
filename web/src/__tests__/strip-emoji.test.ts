import { describe, it, expect } from "vitest";
import { stripEmoji } from "@/lib/utils";

// Build glyph strings via codepoint to keep them out of the source as literals.
// (The emoji-lint test skips __tests__/ but we do this for consistency.)
const NO_ENTRY = String.fromCodePoint(0x26D4);  // ⛔
const SNOWMAN  = String.fromCodePoint(0x2603);  // in U+2600-U+27BF
const ROCKET   = String.fromCodePoint(0x1F680); // in U+1F000-U+1FFFF

describe("stripEmoji", () => {
  it("strips the no-entry veto glyph (U+26D4)", () => {
    expect(stripEmoji(`${NO_ENTRY} Veto`)).toBe("Veto");
  });

  it("leaves normal text unchanged", () => {
    expect(stripEmoji("Normal text")).toBe("Normal text");
  });

  it("strips supplemental emoji (U+1F000-U+1FFFF range)", () => {
    expect(stripEmoji(`${ROCKET} Launch`)).toBe("Launch");
  });

  it("strips misc symbol glyphs in U+2600-U+27BF", () => {
    expect(stripEmoji(`${SNOWMAN} winter`)).toBe("winter");
  });

  it("handles empty string", () => {
    expect(stripEmoji("")).toBe("");
  });

  it("trims surrounding whitespace left after glyph removal", () => {
    expect(stripEmoji(`  ${NO_ENTRY}  text  `)).toBe("text");
  });
});
