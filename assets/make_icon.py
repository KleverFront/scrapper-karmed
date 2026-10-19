"""Generate the app icon (PNG) used to build .icns (macOS) and .ico (Windows)."""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
OUT = Path(__file__).parent / "icon.png"

# UI gradient: #2f81f7 (blue) -> #8957e5 (purple)
C1 = (47, 129, 247)
C2 = (137, 87, 229)


def diagonal_gradient(size: int) -> Image.Image:
    base = Image.new("RGB", (size, size))
    px = base.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            px[x, y] = (
                int(C1[0] + (C2[0] - C1[0]) * t),
                int(C1[1] + (C2[1] - C1[1]) * t),
                int(C1[2] + (C2[2] - C1[2]) * t),
            )
    return base


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def heart(draw: ImageDraw.ImageDraw, cx: int, cy: int, w: int, fill) -> None:
    r = w // 4
    # two top lobes
    draw.ellipse([cx - w // 2, cy - r, cx - w // 2 + 2 * r, cy + r], fill=fill)
    draw.ellipse([cx + w // 2 - 2 * r, cy - r, cx + w // 2, cy + r], fill=fill)
    # bottom point
    draw.polygon([(cx - w // 2, cy), (cx + w // 2, cy), (cx, cy + int(w * 0.62))], fill=fill)


def main() -> None:
    img = diagonal_gradient(SIZE).convert("RGBA")
    img.putalpha(rounded_mask(SIZE, radius=int(SIZE * 0.22)))

    draw = ImageDraw.Draw(img)
    heart(draw, cx=SIZE // 2, cy=int(SIZE * 0.44), w=int(SIZE * 0.44), fill=(255, 255, 255, 255))

    img.save(OUT)
    print("wrote", OUT, img.size)


if __name__ == "__main__":
    main()
