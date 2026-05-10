import { describe, expect, it } from "vitest";
import { parseUuidTokens } from "./uuid";

describe("parseUuidTokens", () => {
  it("lowercases UUIDs, preserves first-seen order, and reports duplicates", () => {
    const a = "ABCDEF0123456789ABCDEF0123456789";
    const b = "11111111111111111111111111111111";
    const parsed = parseUuidTokens(`${a}\n${b}\n${a}`);
    expect(parsed.uuids).toEqual([a.toLowerCase(), b]);
    expect(parsed.duplicates).toEqual([a.toLowerCase()]);
  });

  it("reports invalid long tokens without altering valid UUIDs", () => {
    const parsed = parseUuidTokens("bad-token-12345 abcdef0123456789abcdef0123456789");
    expect(parsed.invalidTokens).toContain("bad-token-12345");
    expect(parsed.uuids).toEqual(["abcdef0123456789abcdef0123456789"]);
  });
});
