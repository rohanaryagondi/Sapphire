import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "fs";
import { join } from "path";

// Emoji Unicode ranges: emoticons, dingbats, misc symbols (U+2600-U+27BF).
// Deliberately excludes U+2300-U+23FF (Miscellaneous Technical) which includes
// typographic keyboard symbols like U+2318 (command sign) used in shortcut labels.
const EMOJI_RANGES = /[\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}]/u;

// The specific decorative glyphs banned by the design spec.
// Stored as codepoints to avoid the test file scanning itself.
const BANNED_CODEPOINTS = [
  0x2697, // lab flask (⚗)
  0x25C6, // black diamond (◆)
  0x1F512, // lock emoji (lock)
  0x1F310, // globe emoji (globe)
  0x26D4, // no entry (⛔)
  0x2691, // black flag (⚑)
  0x2726, // black four pointed star (✦)
  0x25CC, // dotted circle (◌)
  0x2713, // check mark (✓)
  0x25CF, // black circle (●)
  0x1F9EA, // test tube emoji (beaker)
];
const BANNED_GLYPHS = new RegExp(
  "[" + BANNED_CODEPOINTS.map((cp) => String.fromCodePoint(cp)).join("") + "]"
);

function collectTsx(dir: string, skip: string[] = []): string[] {
  const results: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (skip.includes(full)) continue;
    if (statSync(full).isDirectory()) {
      results.push(...collectTsx(full, skip));
    } else if (entry.endsWith(".tsx") || entry.endsWith(".ts")) {
      results.push(full);
    }
  }
  return results;
}

describe("emoji lint — web/src/**/*.tsx", () => {
  const srcDir = join(__dirname, "..");
  // Exclude the __tests__ directory itself (the regex definition would self-trigger).
  const testsDir = join(srcDir, "__tests__");
  const files = collectTsx(srcDir, [testsDir]);

  it("has tsx/ts files to check", () => {
    expect(files.length).toBeGreaterThan(0);
  });

  for (const file of files) {
    it(`no emoji in ${file.replace(srcDir + "/", "")}`, () => {
      const content = readFileSync(file, "utf-8");
      const lines = content.split("\n");
      const violations: string[] = [];
      lines.forEach((line, i) => {
        if (EMOJI_RANGES.test(line) || BANNED_GLYPHS.test(line)) {
          violations.push(`  line ${i + 1}: ${line.trim()}`);
        }
      });
      expect(violations, `Found emoji/glyphs:\n${violations.join("\n")}`).toHaveLength(0);
    });
  }
});
