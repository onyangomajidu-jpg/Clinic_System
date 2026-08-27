#!/usr/bin/env python
"""
Generate PWA icons for Clinic System mobile app.

This script creates placeholder PNG icons in multiple sizes required for
PWA installation on different devices.

To use this script:
1. Install Pillow: pip install Pillow
2. Run: python generate_pwa_icons.py
3. Icons will be created in static/pwa/

For production, replace these with professionally designed icons that match
your clinic's branding.
"""
import os

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow not installed. Installing...")
    os.system("pip install Pillow")
    from PIL import Image, ImageDraw, ImageFont


def create_icon(size, output_path, bg_color="#0f6e5c", text="CS"):
    """
    Create a simple PWA icon.
    
    Args:
        size: Icon size in pixels (square)
        output_path: Path to save the icon
        bg_color: Background color (hex)
        text: Text to display on icon
    """
    # Create image with transparency
    img = Image.new('RGBA', (size, size), bg_color + 'FF')
    draw = ImageDraw.Draw(img)
    
    # Draw a rounded rectangle (simplified - just draw a filled rect)
    padding = size // 10
    draw.rectangle(
        [(padding, padding), (size - padding, size - padding)],
        fill=bg_color
    )
    
    # Try to use a font, fallback to default if not available
    try:
        # Try common system fonts
        font_size = size // 3
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    # Calculate text position (center)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    
    # Draw text
    draw.text((x, y), text, fill="white", font=font)
    
    # Save
    img.save(output_path, 'PNG')
    print(f"Created: {output_path} ({size}x{size})")


def main():
    # Define icon sizes needed for PWA
    sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    
    # Create directory if it doesn't exist
    static_dir = os.path.join(os.path.dirname(__file__), 'static', 'pwa')
    os.makedirs(static_dir, exist_ok=True)
    
    print("Generating PWA icons...")
    print(f"Output directory: {static_dir}\n")
    
    for size in sizes:
        output_path = os.path.join(static_dir, f'icon-{size}.png')
        create_icon(size, output_path)
    
    print("\n✓ All PWA icons generated successfully!")
    print(f"\nIcons created in: {static_dir}")
    print("\nNOTE: For production, replace these placeholder icons with")
    print("professionally designed icons that match your clinic's branding.")
    print("\nRecommended icon design:")
    print("- Use a simple, recognizable medical/clinic symbol")
    print("- Ensure the icon is visible on both light and dark backgrounds")
    print("- Keep text/logo minimal and centered")
    print("- Use your clinic's brand colors")


if __name__ == '__main__':
    main()
