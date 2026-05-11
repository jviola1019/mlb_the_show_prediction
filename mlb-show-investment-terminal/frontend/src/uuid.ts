export const UUID_RE = /(?<![a-fA-F0-9])([a-fA-F0-9]{32})(?![a-fA-F0-9])/g;

export type ParsedUUIDs = {
  uuids: string[];
  duplicates: string[];
  invalidTokens: string[];
  rawCount: number;
};

export function parseUuidTokens(text: string): ParsedUUIDs {
  const rawTokens = text.split(/[\s,;|"'<>()[\]{}]+/).filter(Boolean);
  const seen = new Set<string>();
  const duplicateSeen = new Set<string>();
  const uuids: string[] = [];
  const duplicates: string[] = [];
  for (const match of text.matchAll(UUID_RE)) {
    const uuid = match[1].toLowerCase();
    if (seen.has(uuid)) {
      if (!duplicateSeen.has(uuid)) {
        duplicates.push(uuid);
        duplicateSeen.add(uuid);
      }
      continue;
    }
    seen.add(uuid);
    uuids.push(uuid);
  }
  const invalidTokens = rawTokens.filter((token) => !/^[a-fA-F0-9]{32}$/.test(token) && token.length >= 8 && /[A-Za-z0-9]/.test(token));
  return { uuids, duplicates, invalidTokens, rawCount: rawTokens.length };
}
