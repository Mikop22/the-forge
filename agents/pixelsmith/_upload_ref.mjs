import fs from "node:fs/promises";
import { createRequire } from "node:module";
import pathModule from "node:path";
import { pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);

async function loadFalClient() {
  const depsDir = process.env.TFORGE_NODE_DEPS_DIR;
  const modulePath = depsDir
    ? require.resolve("@fal-ai/client", { paths: [depsDir] })
    : "@fal-ai/client";
  const specifier = pathModule.isAbsolute(modulePath)
    ? pathToFileURL(modulePath).href
    : modulePath;
  return import(specifier);
}

const { fal } = await loadFalClient();

const credentials = process.env.FAL_KEY || process.env.FAL_API_KEY;
if (!credentials) throw new Error("Missing FAL_KEY");
fal.config({ credentials });

const imagePath = process.argv[2];
if (!imagePath) throw new Error("Usage: node upload_ref.mjs <path>");

const buf = await fs.readFile(imagePath);
const blob = new Blob([buf], { type: "image/png" });
const url = await fal.storage.upload(blob);
console.log(url);
