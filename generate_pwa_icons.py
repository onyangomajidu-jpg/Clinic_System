#!/usr/bin/env python
"""
Generate PWA icons for Clinic System mobile app.

Creates the PNG app icons in multiple sizes required for PWA installation,
sourcing the artwork from the clinic's own logo (static/logo.png) so the
app icon matches the clinic branding instead of a "CS" text placeholder.

To use this script:
1. Install Pillow: pip install Pillow
2. Run: python generate_pwa_icons.py
3. Icons will be created in static/pwa/
"""
import os

try:
    from PIL import Image, ImageDraw, ImageOps
except ImportError:
    print("Pillow not installed. Installing...")
    os.system("pip install Pillow")
    from PIL import Image, ImageDraw, ImageOps


def create_icon(size, output_path, source_logo):
    """
    Create a PWA icon from the clinic logo.

    Args:
        size: Icon size in pixels (square)
        output_path: Path to save the icon
        source_logo: PIL Image (RGBA) of the clinic logo
    """
    # Opaque white square so the icon works as a "maskable" app icon too.
    canvas = Image.new("RGB", (size, size), (255, 255, 255))
    # Keep the logo inside the central ~72% -> within the safe zone that
    # maskable icons require (avoid clipping by OS masks).
    inner = int(round(size * 0.72))
    fitted = ImageOps.contain(source_logo, (inner, inner)).convert("RGBA")
    pos = ((size - fitted.width) // 2, (size - fitted.height) // 2)
    canvas.paste(fitted, pos, fitted)

    # Rounded corners for a clean app-tile look.
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=int(round(size * 0.18)), fill=255
    )
    final = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    final.paste(canvas, (0, 0), mask)
    final.save(output_path, "PNG")
    print(f"Created: {output_path} ({size}x{size})")


def main():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(project_dir, "static", "logo.png")
    if not os.path.exists(logo_path):
        print(f"ERROR: logo not found at {logo_path}")
        raise SystemExit(1)
    logo = Image.open(logo_path).convert("RGBA")

    sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    static_dir = os.path.join(project_dir, "static", "pwa")
    os.makedirs(static_dir, exist_ok=True)

    print("Generating PWA icons from logo.png ...")
    print(f"Output directory: {static_dir}\n")

    for size in sizes:
        output_path = os.path.join(static_dir, f"icon-{size}.png")
        create_icon(size, output_path, logo)

    print("\n✓ All PWA icons generated from the clinic logo!")


if __name__ == "__main__":
    main()
