"""Generate the animated pipeline illustration used in the project README."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT = 960, 480
BACKGROUND = (16, 27, 32)
CARD = (26, 47, 51)
CARD_ACTIVE = (39, 76, 69)
INK = (245, 244, 235)
MUTED = (166, 187, 179)
MINT = (91, 205, 174)
AMBER = (229, 174, 94)
STAGES = [
    ("01", "INGEST", "Paper / notes", "PDF, Markdown, text"),
    ("02", "ANALYZE", "Scientific context", "Graph + simulation"),
    ("03", "DIRECT", "LecturePlan IR", "Timed, tagged scenes"),
    ("04", "NARRATE", "Scene audio", "Voice + captions"),
    ("05", "RENDER", "Teaching pack", "Video + slides + TeX"),
]


def load_font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default(size=size)


FONT_KICKER = load_font(14, True)
FONT_TITLE = load_font(31, True)
FONT_STEP = load_font(15, True)
FONT_BODY = load_font(18, True)
FONT_SMALL = load_font(13)


def centered(draw, xy, text, font, fill):
    draw.text(xy, text, font=font, fill=fill, anchor="mm")


def make_frame(active_stage: int, phase: int) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    draw.text((54, 34), "SCIFORGE  /  SCIENTIFIC TEACHING COMPILER", font=FONT_KICKER, fill=MINT)
    draw.text((54, 72), "From source material to a teachable result", font=FONT_TITLE, fill=INK)
    draw.text((56, 120), "One structured plan keeps every output aligned and reviewable.", font=FONT_SMALL, fill=MUTED)

    left, top, card_width, card_height, gap = 38, 194, 164, 140, 25
    centers = []
    for index, (number, label, title, detail) in enumerate(STAGES):
        x = left + index * (card_width + gap)
        fill = CARD_ACTIVE if index == active_stage else CARD
        outline = AMBER if index == active_stage else (66, 96, 89)
        draw.rounded_rectangle((x, top, x + card_width, top + card_height), radius=13, fill=fill, outline=outline, width=2)
        centered(draw, (x + card_width // 2, top + 28), f"{number}  /  {label}", FONT_STEP, AMBER if index == active_stage else MINT)
        centered(draw, (x + card_width // 2, top + 70), title, FONT_BODY, INK)
        centered(draw, (x + card_width // 2, top + 105), detail, FONT_SMALL, MUTED)
        centers.append(x + card_width // 2)

    for index in range(len(STAGES) - 1):
        x1 = left + index * (card_width + gap) + card_width + 5
        x2 = left + (index + 1) * (card_width + gap) - 6
        y = top + card_height // 2
        draw.line((x1, y, x2, y), fill=MINT, width=3)
        draw.polygon(((x2 - 6, y - 6), (x2 + 1, y), (x2 - 6, y + 6)), fill=MINT)

    # The marker travels along the pipeline while the active stage advances.
    marker_x = int(centers[active_stage] - 8 + (phase % 3 - 1) * 13)
    draw.ellipse((marker_x - 8, 359, marker_x + 8, 375), fill=AMBER)
    draw.line((centers[0], 367, centers[-1], 367), fill=(66, 96, 89), width=2)
    draw.rounded_rectangle((253, 404, 707, 451), radius=23, fill=(33, 51, 53), outline=(123, 104, 72), width=1)
    centered(draw, (480, 428), "Human review  /  Deterministic rendering  /  Local-first workflow", FONT_SMALL, INK)
    return image


def main() -> None:
    output = Path(__file__).with_name("pipeline.gif")
    frames = [make_frame(stage, phase) for stage in range(len(STAGES)) for phase in range(3)]
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=360,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"Generated {output} ({output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()