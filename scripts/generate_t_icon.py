from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUTPUT = Path(__file__).resolve().parent.parent / "assets" / "talkagent.ico"
SIZES = (256, 128, 64, 48, 32, 16)
FONT_PATHS = (
    Path(r"C:\Windows\Fonts\segoeuib.ttf"),
    Path(r"C:\Windows\Fonts\arialbd.ttf"),
)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_PATHS:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _canvas(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), "#0F766E")
    draw = ImageDraw.Draw(image)
    border = max(1, size // 24)
    draw.rounded_rectangle(
        (border, border, size - border, size - border),
        radius=max(3, size // 6),
        outline="#5EEAD4",
        width=border,
    )
    font = _font(int(size * 0.66))
    bbox = draw.textbbox((0, 0), "T", font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text(
        ((size - text_width) / 2 - bbox[0], (size - text_height) / 2 - bbox[1] - size * 0.02),
        "T",
        fill="#F8FAFC",
        font=font,
    )
    return image


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image = _canvas(max(SIZES))
    image.save(OUTPUT, format="ICO", sizes=[(size, size) for size in SIZES])


if __name__ == "__main__":
    main()
