import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const sourceUrl = new URL("../public/test-fixtures/synthetic-receipt-source.svg", import.meta.url);
const outputUrl = new URL("../public/test-fixtures/synthetic-receipt.png", import.meta.url);
const source = await readFile(sourceUrl);

await sharp(source, { density: 144 })
  .resize({ width: 900, withoutEnlargement: true })
  .png({ compressionLevel: 9 })
  .toFile(fileURLToPath(outputUrl));

console.log(`Generated ${fileURLToPath(outputUrl)}`);
