"""Build the 2x2 photo panel for the dermatologist info pack."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "data" / "images"
OUT = ROOT / "docs" / "reports" / "photo-panel.png"

PHOTOS = [
    {
        "file": "97_fdcc3d89.jpg",
        "label": "A. Torso — Mar 31 (severity 9/10)",
        "caption": "Peak. Widespread erythema, chest and abdomen.",
    },
    {
        "file": "2_a0ed8c20.jpg",
        "label": "B. Lower leg — Mar 23 (severity 8/10)",
        "caption": "Chronic eczematous patches with excoriations and scaling.",
    },
    {
        "file": "355_9fc88ffb.jpg",
        "label": "C. Face — Apr 17 (severity 6/10)",
        "caption": "Forehead xerosis and flaking. Periorbital dryness.",
    },
    {
        "file": "344_4fef8e2d.jpg",
        "label": "D. Knee — Apr 16 (severity 7/10)",
        "caption": "Discrete papular lesions. Heavy back-burning smoke day.",
    },
]

CELL_W = 1200
CELL_H = 1200
LABEL_H = 60
CAPTION_H = 80
PHOTO_H = CELL_H - LABEL_H - CAPTION_H
PAD = 24
TITLE_H = 90
COLS = 2
ROWS = 2

CANVAS_W = COLS * CELL_W + (COLS + 1) * PAD
CANVAS_H = TITLE_H + ROWS * CELL_H + (ROWS + 1) * PAD


def load_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def fit_photo(img, box_w, box_h):
    img = ImageOps.exif_transpose(img)
    iw, ih = img.size
    scale = min(box_w / iw, box_h / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    return img.resize((nw, nh), Image.LANCZOS)


def main():
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
    draw = ImageDraw.Draw(canvas)

    title_font = load_font(36, bold=True)
    subtitle_font = load_font(20)
    label_font = load_font(28, bold=True)
    caption_font = load_font(22)

    title = "Clinical Photo Documentation — Selected from 32 Photos"
    subtitle = "Full photo set (multiple body areas) available on device · Mar 23 – Apr 19, 2026"
    tw = draw.textlength(title, font=title_font)
    draw.text(((CANVAS_W - tw) / 2, 18), title, fill="black", font=title_font)
    sw = draw.textlength(subtitle, font=subtitle_font)
    draw.text(((CANVAS_W - sw) / 2, 60), subtitle, fill="#555", font=subtitle_font)

    for idx, p in enumerate(PHOTOS):
        row, col = idx // COLS, idx % COLS
        x0 = PAD + col * (CELL_W + PAD)
        y0 = TITLE_H + PAD + row * (CELL_H + PAD)

        draw.text((x0, y0), p["label"], fill="black", font=label_font)

        photo_box_y = y0 + LABEL_H
        img = Image.open(IMG_DIR / p["file"])
        fitted = fit_photo(img, CELL_W, PHOTO_H)
        fw, fh = fitted.size
        px = x0 + (CELL_W - fw) // 2
        py = photo_box_y + (PHOTO_H - fh) // 2
        canvas.paste(fitted, (px, py))
        draw.rectangle([px, py, px + fw, py + fh], outline="#ccc", width=2)

        cap_y = y0 + LABEL_H + PHOTO_H + 10
        for line in wrap(p["caption"], caption_font, CELL_W, draw):
            draw.text((x0, cap_y), line, fill="#333", font=caption_font)
            cap_y += 30

    canvas.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} ({CANVAS_W}x{CANVAS_H})")


def wrap(text, font, max_w, draw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


if __name__ == "__main__":
    main()
