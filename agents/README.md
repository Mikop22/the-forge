# Agents Runtime Notes

## Reference-aware generation configuration

Architect reference lookup uses Bing Images via Playwright (no API key needed).
Requires `playwright install chromium` to be run once.

Pixelsmith generation mode configuration:

- `FAL_KEY` or `FAL_API_KEY`: required for all generations.
- `FAL_IMAGE_TO_IMAGE_ENABLED`: set `true` to allow `image_to_image` requests.
- `FAL_IMAGE_TO_IMAGE_ENDPOINT`: optional endpoint override for image-to-image mode.

Fallback behavior:

- Any reference lookup or approval failure falls back to `text_to_image`.
- `image_to_image` requests without a reference URL or with capability disabled fall back to `text_to_image`.
