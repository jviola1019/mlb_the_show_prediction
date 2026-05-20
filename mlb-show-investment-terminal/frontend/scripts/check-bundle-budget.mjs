import { readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const assetDir = join(process.cwd(), "dist", "assets");
const maxChunkBytes = Number(process.env.BUNDLE_MAX_CHUNK_BYTES || 900_000);
const maxTotalBytes = Number(process.env.BUNDLE_MAX_TOTAL_BYTES || 5_500_000);

let files;
try {
  files = readdirSync(assetDir).filter((name) => name.endsWith(".js"));
} catch {
  console.error("dist/assets was not found. Run npm run build before bundle:budget.");
  process.exit(1);
}

const chunks = files.map((name) => {
  const bytes = statSync(join(assetDir, name)).size;
  return { name, bytes };
});
const total = chunks.reduce((sum, chunk) => sum + chunk.bytes, 0);
const over = chunks.filter((chunk) => chunk.bytes > maxChunkBytes);

console.log(JSON.stringify({ maxChunkBytes, maxTotalBytes, total, chunks }, null, 2));
if (over.length || total > maxTotalBytes) {
  console.error("Bundle budget exceeded.");
  process.exit(1);
}
