"""
Home Cloud Drive - Thumbnail Generation Utility
Generates server-side thumbnails for image files using Pillow.
"""
import os
from PIL import Image

THUMBNAIL_SIZE = (300, 300)
THUMBNAIL_QUALITY = 85

# Preview-optimized image settings (~1080p WebP for fast loading)
PREVIEW_MAX_SIZE = (1920, 1080)  # Max dimensions (maintains aspect ratio)
PREVIEW_QUALITY = 85
PREVIEW_FORMAT = "WebP"

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


def generate_preview(source_path: str, preview_dir: str, file_id: str) -> str | None:
    """
    Generate a preview-optimized image for fast web display.
    
    Generates a ~1080p WebP version (much smaller than original 4K+ images)
    while maintaining high quality for preview modal display.
    
    Args:
        source_path: Path to the original image file
        preview_dir: Directory to store preview images
        file_id: Unique file ID (used as preview filename)
    
    Returns:
        Path to the generated preview image, or None if generation failed
    """
    try:
        os.makedirs(preview_dir, exist_ok=True)
        
        preview_path = os.path.join(preview_dir, f"{file_id}_preview.webp")
        
        with Image.open(source_path) as img:
            # Get original dimensions
            orig_width, orig_height = img.size
            
            # Skip preview generation if image is already small enough
            if orig_width <= PREVIEW_MAX_SIZE[0] and orig_height <= PREVIEW_MAX_SIZE[1]:
                return None  # Use original file in preview endpoint
            
            # Convert to RGB for WebP output (handles RGBA, P, LA, etc.)
            if img.mode in ('RGBA', 'LA'):
                # Preserve transparency by using white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else img.split()[1])
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize maintaining aspect ratio (fit within PREVIEW_MAX_SIZE)
            img.thumbnail(PREVIEW_MAX_SIZE, Image.Resampling.LANCZOS)
            
            # Save as WebP for optimal compression
            img.save(preview_path, PREVIEW_FORMAT, quality=PREVIEW_QUALITY, method=6)
            
            # Check file size - if preview is larger than 500KB, we might need to reduce quality
            preview_size = os.path.getsize(preview_path)
            if preview_size > 500_000:  # 500KB
                # Re-save with lower quality
                img.save(preview_path, PREVIEW_FORMAT, quality=75, method=6)
        
        return preview_path
    except Exception as e:
        print(f"[!] Preview generation failed for {source_path}: {e}")
        return None
