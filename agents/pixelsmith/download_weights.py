#!/usr/bin/env python3
"""
Download Pixelsmith model weights from Google Drive.
Run once after cloning; weights are not stored in the repo.

  python download_weights.py

Set the Google Drive file IDs below (from the share link) before running.
"""

import pathlib
import sys

# Replace these with your Google Drive file IDs.
# Share link format: https://drive.google.com/file/d/FILE_ID/view?usp=sharing
WEIGHTS = {
    "pixel-art-xl.safetensors": "",      # FILE_ID for pixel-art-xl
    "terraria_weights.safetensors": "",  # FILE_ID for terraria_weights
    "aziib_pixel_style_zit.safetensors": "",  # FILE_ID for aziib_pixel_style_zit
}

DEST_DIR = pathlib.Path(__file__).parent
# Direct download URL for Google Drive (no confirmation page for small files)
BASE_URL = "https://drive.google.com/uc?export=download&id={}"


def main():
    missing = [k for k, v in WEIGHTS.items() if not v.strip()]
    if missing:
        print("Set Google Drive file IDs in WEIGHTS (this script) for:", ", ".join(missing))
        print("Get IDs from: Share → Copy link → id is the part between /d/ and /view")
        sys.exit(1)

    try:
        import requests
    except ImportError:
        print("Install requests: pip install requests")
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
            resp = requests.get(url, stream=True, timeout=60)
            resp.raise_for_status()
            size = 0
            with open(path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
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
