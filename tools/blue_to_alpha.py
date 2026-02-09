from __future__ import annotations

from pathlib import Path
from PIL import Image
import math

# Tuning knobs:
THRESH = 35   # distance below this becomes fully transparent
SOFT = 40     # feather range above THRESH (bigger = softer edges)


def dist(rgb: tuple[int, int, int], key: tuple[int, int, int]) -> float:
    return math.sqrt(
        (rgb[0] - key[0]) ** 2 +
        (rgb[1] - key[1]) ** 2 +
        (rgb[2] - key[2]) ** 2
    )


def auto_key(img: Image.Image) -> tuple[int, int, int]:
    """
    Guess the background color by sampling pixels near the corners.
    Returns an (R,G,B) tuple.

    Safe for tiny images (clamps sample coords).
    """
    rgb = img.convert("RGB")
    w, h = rgb.size

    # Candidate corner-near sample points (will be clamped)
    raw_points = [
        (0, 0), (1, 0), (0, 1),
        (w - 1, 0), (w - 2, 0), (w - 1, 1),
        (0, h - 1), (1, h - 1), (0, h - 2),
        (w - 1, h - 1), (w - 2, h - 1), (w - 1, h - 2),
    ]

    samples: list[tuple[int, int]] = []
    for x, y in raw_points:
        x = max(0, min(w - 1, x))
        y = max(0, min(h - 1, y))
        samples.append((x, y))

    colors = [rgb.getpixel((x, y)) for (x, y) in samples]

    # Pick the most common sampled color
    return max(set(colors), key=colors.count)


def blue_to_alpha(img: Image.Image, key_rgb: tuple[int, int, int]) -> Image.Image:
    """
    Convert pixels close to key_rgb into transparency (alpha),
    with a feathered edge controlled by THRESH and SOFT.
    """
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            d = dist((r, g, b), key_rgb)

            if d <= THRESH:
                px[x, y] = (r, g, b, 0)
            elif d < THRESH + SOFT:
                # feathered alpha
                t = (d - THRESH) / SOFT  # 0..1
                new_a = int(255 * t)
                px[x, y] = (r, g, b, min(a, new_a))
            # else keep as-is

    return img


def process_folder(in_dir: Path, out_dir: Path, verbose: bool = True) -> None:
    """
    Recursively process all PNGs in in_dir, write results to out_dir
    while preserving subfolder structure.
    """
    if not in_dir.exists():
        raise FileNotFoundError(f"Input folder does not exist: {in_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)

    pngs = list(in_dir.rglob("*.png"))
    if verbose:
        print(f"Found {len(pngs)} PNG(s) under {in_dir}")

    for p in pngs:
        img = Image.open(p)
        key = auto_key(img)

        if verbose:
            rel = p.relative_to(in_dir)
            print(f"{rel}  key={key}")

        out = blue_to_alpha(img, key)

        # Preserve relative structure
        rel = p.relative_to(in_dir)
        out_path = out_dir / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out.save(out_path)


if __name__ == "__main__":
    raw = Path("assets/sprites_raw")
    clean = Path("assets/sprites_clean")

    process_folder(raw, clean, verbose=True)
    print("done")
