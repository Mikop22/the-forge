import fs from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";

import { fal } from "@fal-ai/client";

// Cache uploaded LoRA URLs to avoid re-uploading every call.
// Key: absolute local path → Value: fal storage URL
const LORA_CACHE_FILE = path.join(
  path.dirname(new URL(import.meta.url).pathname),
  ".lora_url_cache.json",
);

async function loadLoraCache() {
  try {
    const raw = await fs.readFile(LORA_CACHE_FILE, "utf8");
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

async function saveLoraCache(cache) {
  await fs.writeFile(LORA_CACHE_FILE, JSON.stringify(cache, null, 2));
}

/**
 * If a LoRA entry has a local `path` (not a URL), upload it to fal storage
 * and replace the path with the returned URL. Caches the result.
 */
async function resolveLoraUrls(loras) {
  if (!Array.isArray(loras) || loras.length === 0) return loras;

  const cache = await loadLoraCache();
  const resolved = [];

  for (const lora of loras) {
    const loraPath = lora.path || "";

    // Already a URL — pass through
    if (loraPath.startsWith("http://") || loraPath.startsWith("https://")) {
      resolved.push(lora);
      continue;
    }

    // Local file — upload to fal storage (with cache)
    if (existsSync(loraPath)) {
      const absPath = path.resolve(loraPath);

      if (cache[absPath]) {
        console.log(`LoRA cache hit: ${path.basename(absPath)}`);
        resolved.push({ ...lora, path: cache[absPath] });
        continue;
      }

      console.log(`Uploading LoRA: ${path.basename(absPath)} ...`);
      const fileBuffer = await fs.readFile(absPath);
      const blob = new Blob([fileBuffer], {
        type: "application/octet-stream",
      });
      const url = await fal.storage.upload(blob);
      console.log(`LoRA uploaded → ${url}`);

      cache[absPath] = url;
      await saveLoraCache(cache);

      resolved.push({ ...lora, path: url });
    } else {
      console.warn(`LoRA file not found, skipping: ${loraPath}`);
    }
  }

  return resolved;
}

async function main() {
  const payloadPath = process.argv[2];
  if (!payloadPath) {
    throw new Error("Usage: node fal_flux2_runner.mjs <payload.json>");
  }

  const raw = await fs.readFile(payloadPath, "utf8");
  const payload = JSON.parse(raw);
  const endpoint = payload.endpoint || "fal-ai/flux-2/klein/9b/base/lora";
  const outputPath = payload.output_path;
  const credentials = process.env.FAL_KEY || process.env.FAL_API_KEY;

  if (!credentials) {
    throw new Error("Missing FAL_KEY (or FAL_API_KEY).");
  }
  if (!outputPath) {
    throw new Error("payload.output_path is required.");
  }

  fal.config({ credentials });

  // Resolve any local LoRA paths to fal storage URLs
  if (payload.input?.loras) {
    payload.input.loras = await resolveLoraUrls(payload.input.loras);
  }

  const result = await fal.subscribe(endpoint, {
    input: payload.input,
    logs: true,
    onQueueUpdate: (update) => {
      if (update.status === "IN_PROGRESS") {
        for (const log of update.logs ?? []) {
          if (log?.message) console.log(log.message);
        }
      }
    },
  });

  const data = result?.data ?? {};
  const imageEntry = Array.isArray(data.images) ? data.images[0] : null;
  const imageUrl = imageEntry?.url;
  if (!imageUrl) {
    throw new Error(
      `Missing image URL in fal response: ${JSON.stringify(data)}`,
    );
  }

  const response = await fetch(imageUrl);
  if (!response.ok) {
    throw new Error(
      `Failed downloading image: ${response.status} ${response.statusText}`,
    );
  }
  const bytes = Buffer.from(await response.arrayBuffer());
  await fs.writeFile(outputPath, bytes);

  const summary = {
    requestId: result?.requestId ?? null,
    output_path: outputPath,
  };
  console.log(JSON.stringify(summary));
}

main().catch((err) => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
