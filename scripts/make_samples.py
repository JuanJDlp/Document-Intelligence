"""Generate synthetic inputs only. Expected results are hand-authored separately."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parents[1]
LINES = [
    "SYNTHETIC MARKET",
    "FACTURA No INV-001",
    "NIT 900123456-8",
    "FECHA: 15/01/2026",
    "SUBTOTAL: COP 100.000",
    "IVA: COP 19.000",
    "TOTAL: COP 119.000",
    "EFECTIVO",
]


def generate():
    folder = ROOT / "samples/receipts"
    folder.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1600, 1400), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 42)
    except OSError:
        font = ImageFont.load_default(size=42)
    for index, line in enumerate(LINES):
        draw.text((100, 100 + index * 130), line, fill="black", font=font)
    image.save(folder / "receipt.png")
    image.save(folder / "receipt.jpeg")
    for name, lines in [
        ("receipt.pdf", LINES),
        ("invoice-items.pdf", [*LINES, "Synthetic notebooks: 2 x COP 50.000 = COP 100.000"]),
        ("missing-total.pdf", LINES[:-2]),
        ("negative-total.pdf", [*LINES[:-2], "TOTAL: COP -119.000"]),
        (
            "comma-decimal.pdf",
            ["SYNTHETIC MARKET", "RECIBO", "FECHA: 15/01/2026", "TOTAL: COP 119,50"],
        ),
    ]:
        canvas = Canvas(str(folder / name))
        for index, line in enumerate(lines):
            canvas.setFont("Helvetica", 18)
            canvas.drawString(50, 760 - index * 65, line)
        canvas.save()
    Image.new("RGB", (600, 600), "white").save(folder / "blank.png")
    writer = PdfWriter()
    writer.add_page(PdfReader(folder / "receipt.pdf").pages[0])
    writer.add_blank_page(width=600, height=800)
    with (folder / "multipage.pdf").open("wb") as stream:
        writer.write(stream)
    encrypted = PdfWriter()
    encrypted.add_page(PdfReader(folder / "receipt.pdf").pages[0])
    encrypted.encrypt("synthetic-test-only")
    with (folder / "encrypted.pdf").open("wb") as stream:
        encrypted.write(stream)
    (folder / "renamed.pdf").write_text("Synthetic text; not a PDF.")


if __name__ == "__main__":
    generate()
