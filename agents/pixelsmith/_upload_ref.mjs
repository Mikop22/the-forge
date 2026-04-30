import fs from "node:fs/promises";
import { fal } from "@fal-ai/client";

const credentials = process.env.FAL_KEY || process.env.FAL_API_KEY;
if (!credentials) throw new Error("Missing FAL_KEY");
fal.config({ credentials });

const path = process.argv[2];
if (!path) throw new Error("Usage: node upload_ref.mjs <path>");

const buf = await fs.readFile(path);
const blob = new Blob([buf], { type: "image/png" });
const url = await fal.storage.upload(blob);
console.log(url);
