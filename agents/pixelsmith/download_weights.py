#!/usr/bin/env python3
"""
Download Pixelsmith model weights from Google Drive.
Run once after cloning; weights are not stored in the repo.

  python download_weights.py

Set the Google Drive file IDs below (from the share link) before running.
"""

import pathlib
import sys
import urllib.request

# Replace with your Google Drive file ID.
# Share link format: https://drive.google.com/file/d/FILE_ID/view?usp=sharing
WEIGHTS = {
    "terraria_weights.safetensors": "1NHyfX2AlNxebCByd1jSvMZzLnMCzGqnv",  # from share link
}

DEST_DIR = pathlib.Path(__file__).parent
# Direct download URL for Google Drive (no confirmation page for small files)
BASE_URL = "https://drive.google.com/uc?export=download&id={}"
CHUNK_SIZE = 1024 * 1024  # 1 MiB


def main():
    missing = [k for k, v in WEIGHTS.items() if not v.strip()]
    if missing:
        print("Set Google Drive file IDs in WEIGHTS (this script) for:", ", ".join(missing))
        print("Get IDs from: Share → Copy link → id is the part between /d/ and /view")
        sys.exit(1)

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    for fname, file_id in WEIGHTS.items():
        path = DEST_DIR / fname
        if path.exists():
            print(f"Already present: {fname}")
            continue
        url = BASE_URL.format(file_id.strip())
        print(f"Downloading {fname}...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                size = 0
                with open(path, "wb") as f:
                    while True:
                        chunk = resp.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        size += len(chunk)
                        print(f"\r  {size / (1024*1024):.1f} MiB", end="")
            print()
        except Exception as e:
            print(f"  Failed: {e}")
            if path.exists():
                path.unlink()
            sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()
