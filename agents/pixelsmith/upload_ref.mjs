import { fal } from "@fal-ai/client";
import fs from "node:fs";
fal.config({ credentials: process.env.FAL_KEY });
const data = fs.readFileSync(process.argv[2]);
const blob = new Blob([data], { type: "image/png" });
const url = await fal.storage.upload(blob);
console.log(url);
