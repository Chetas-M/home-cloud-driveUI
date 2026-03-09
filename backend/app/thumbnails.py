"""
Home Cloud Drive - Thumbnail Generation Utility
Generates server-side thumbnails for image files using Pillow.
"""
import os
from PIL import Image

THUMBNAIL_SIZE = (300, 300)
THUMBNAIL_QUALITY = 85
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp'}


def can_generate_thumbnail(filename: str) -> bool:
    """Check if a thumbnail can be generated for this file type"""
    ext = os.path.splitext(filename)[1].lower()
    return ext in SUPPORTED_FORMATS


def generate_thumbnail(source_path: str, thumbnail_dir: str, file_id: str) -> str | None:
    """
    Generate a thumbnail for an image file.
    
    Args:
        source_path: Path to the original image file
        thumbnail_dir: Directory to store thumbnails
        file_id: Unique file ID (used as thumbnail filename)
    
    Returns:
        Path to the generated thumbnail, or None if generation failed
    """
    try:
        os.makedirs(thumbnail_dir, exist_ok=True)
        
        thumbnail_path = os.path.join(thumbnail_dir, f"{file_id}_thumb.jpg")
        
        with Image.open(source_path) as img:
            # Convert RGBA/P to RGB for JPEG output
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize maintaining aspect ratio
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            
            # Save as JPEG
            img.save(thumbnail_path, 'JPEG', quality=THUMBNAIL_QUALITY, optimize=True)
        
        return thumbnail_path
    except Exception as e:
        print(f"[!] Thumbnail generation failed for {source_path}: {e}")
        return None
