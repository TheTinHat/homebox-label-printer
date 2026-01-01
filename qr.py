"""
Generate QR code labels for assets.

This script creates a strip of labels, each containing a QR code and a human-readable
asset ID. The script is configurable via command-line arguments for the start and
end asset IDs, and the base URL for the QR codes.

Dependencies:
- qrcode
- Pillow

Usage:
python qr.py --start 1 --end 10
"""

import argparse
import qrcode
from PIL import Image, ImageDraw, ImageFont
import subprocess
import os

# --- Constants ---
TAPE_HEIGHT = 76
ELEMENT_GAP = 6
LABEL_GAP = 1
QR_VERSION = 1
QR_ERROR_CORRECTION = qrcode.constants.ERROR_CORRECT_M
QR_BOX_SIZE = 2
QR_BORDER = 4
FONT_SIZE = 32
TEXT_LINE_SPACING = 28
TEXT_START_Y = 38
TEMP_CANVAS_WIDTH = 90



def get_font(size):
    """
    Finds a bold font on the system for better thermal printer clarity.

    Args:
        size (int): The desired font size.

    Returns:
        ImageFont: A Pillow ImageFont object. Defaults to a built-in font if a
                   suitable bold font is not found.
    """
    try:
        # Search specifically for Heavy, Black, or ExtraBold styles
        cmd = ["fc-match", "-f", "%{file}", "sans:style=ExtraBold:weight=200:bold"]
        font_path = subprocess.check_output(cmd).decode().strip()
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return ImageFont.load_default()


def asset_id_to_int(asset_id_str):
    """
    Converts a string asset ID (e.g., "001-086") into a single integer.

    Args:
        asset_id_str (str): The asset ID string in "XXX-YYY" format.

    Returns:
        int: The integer representation of the asset ID.

    Raises:
        ValueError: If the asset ID string is not in the correct format.
    """
    try:
        parts = asset_id_str.split('-')
        if len(parts) != 2:
            raise ValueError("Asset ID must be in 'XXX-YYY' format.")
        
        major = int(parts[0])
        minor = int(parts[1])
        
        return major * 1000 + minor
    except ValueError as e:
        raise ValueError(f"Invalid asset ID format: {asset_id_str}. {e}")

def create_label(number, url):
    """
    Creates a single asset label image.

    The label consists of a QR code and the asset ID split into two lines.

    Args:
        number (int): The asset number.
        url (str): The base URL for the QR code.

    Returns:
        Image: A Pillow Image object representing the label.
    """
    asset_id = f"{number // 1000:03d}-{number % 1000:03d}"

    qr = qrcode.QRCode(
        version=QR_VERSION,
        error_correction=QR_ERROR_CORRECTION,
        box_size=QR_BOX_SIZE,
        border=QR_BORDER,
    )
    qr.add_data(f"{url}{asset_id}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('1')

    font = get_font(FONT_SIZE)
    parts = asset_id.split("-")

    # Render text vertically on a tall temporary canvas
    temp_txt = Image.new("RGB", (TEMP_CANVAS_WIDTH, TAPE_HEIGHT * 2), "white")
    temp_draw = ImageDraw.Draw(temp_txt)
    temp_draw.text((0, TEXT_START_Y), parts[0], fill="black", font=font, anchor="la")
    temp_draw.text((0, TEXT_START_Y + TEXT_LINE_SPACING), parts[1], fill="black", font=font, anchor="la")

    # Crop the text image to its content
    temp_txt = temp_txt.convert("1").convert("RGB")
    text_img = temp_txt.crop(temp_txt.getbbox())

    # Assemble the QR code and text side-by-side
    unit_w = qr_img.width + ELEMENT_GAP + text_img.width
    unit = Image.new("RGB", (unit_w, TAPE_HEIGHT), "white")
    unit.paste(qr_img, (0, (TAPE_HEIGHT - qr_img.height) // 2))
    unit.paste(text_img, (qr_img.width + ELEMENT_GAP, (TAPE_HEIGHT - text_img.height) // 2))

    return unit


def generate_label_strip(start_id, end_id, url, print_label, output_filename=None):
    """
    Generates a strip of labels and saves it to a file.

    Args:
        start_id (int): The starting asset ID.
        end_id (int): The ending asset ID.
        url (str): The base URL for the QR codes.
        print_label (bool): Whether to print the label strip after generating it.
        output_filename (str, optional): The desired output filename. If None,
                                        a default filename "asset_labels.png" is used.
    """
    labels = [create_label(i, url) for i in range(start_id, end_id + 1)]
    total_w = sum(l.width for l in labels) + (len(labels) * LABEL_GAP)

    strip = Image.new("RGB", (total_w, TAPE_HEIGHT), "white")
    x_cursor = 0
    for l in labels:
        strip.paste(l, (x_cursor, 0))
        x_cursor += l.width + LABEL_GAP

    if output_filename:
        image_filename = output_filename
    else:
        image_filename = "asset_labels.png"
    
    strip.save(image_filename)
    print(f"Successfully created {image_filename}")

    if print_label:
        try:
            subprocess.run(["ptouch-print", "--image", image_filename], check=True)
            print(f"Successfully printed {image_filename}")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Error printing {image_filename}: {e}")


def parse_args():
    """
    Parses command-line arguments.

    Returns:
        tuple: A tuple containing the ArgumentParser object and the parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Generate asset labels with QR codes.")
    parser.add_argument("--start", type=str, required=True, help="Starting asset ID (e.g., '001-086').")
    parser.add_argument("--end", type=str, required=True, help="Ending asset ID (e.g., '001-086').")
    parser.add_argument("--domain", type=str, default=os.getenv("HOMEBOX_DOMAIN"),
                        help="The domain for the QR code URL (e.g., 'box.example.com'). Overrides HOMEBOX_DOMAIN environment variable.")
    parser.add_argument("--print", action="store_true", help="Automatically print the generated label strip.")
    parser.add_argument("--output", type=str, default=None, help="Specify the output filename (e.g., 'my_labels.png'). If not specified, a default filename will be used.")
    args = parser.parse_args()
    return parser, args


def main():
    """
    Main function to run the script.
    """
    parser, args = parse_args()

    if not args.domain:
        parser.error("The --domain argument or HOMEBOX_DOMAIN environment variable is required.")

    try:
        start_int = asset_id_to_int(args.start)
        end_int = asset_id_to_int(args.end)
    except ValueError as e:
        parser.error(e)

    if start_int > end_int:
        parser.error(f"Starting asset ID ({args.start}) cannot be greater than ending asset ID ({args.end}).")

    full_url = f"https://{args.domain}/a/"
    generate_label_strip(start_int, end_int, full_url, args.print, args.output)


if __name__ == "__main__":
    main()
