"""Brand asset image validation (MIME, size, optional dimensions)."""
from __future__ import annotations

from typing import Dict, Optional, Set, Tuple

from fastapi import HTTPException, UploadFile, status

from app.branding.models import BrandingAssetType

# Asset-specific limits (bytes)
ASSET_MAX_BYTES: Dict[BrandingAssetType, int] = {
    BrandingAssetType.LOGO: 2 * 1024 * 1024,
    BrandingAssetType.DARK_LOGO: 2 * 1024 * 1024,
    BrandingAssetType.FAVICON: 512 * 1024,
    BrandingAssetType.SPLASH: 5 * 1024 * 1024,
    BrandingAssetType.LAUNCHER_ICON: 2 * 1024 * 1024,
    BrandingAssetType.EMAIL_LOGO: 1 * 1024 * 1024,
    BrandingAssetType.LOGIN_BACKGROUND: 5 * 1024 * 1024,
    BrandingAssetType.WIDGET_LAUNCHER: 1 * 1024 * 1024,
    BrandingAssetType.WIDGET_HEADER: 1 * 1024 * 1024,
}

ASSET_MIME: Dict[BrandingAssetType, Set[str]] = {
    BrandingAssetType.LOGO: {"image/png", "image/jpeg", "image/webp", "image/svg+xml"},
    BrandingAssetType.DARK_LOGO: {"image/png", "image/jpeg", "image/webp", "image/svg+xml"},
    BrandingAssetType.FAVICON: {
        "image/png",
        "image/x-icon",
        "image/vnd.microsoft.icon",
        "image/svg+xml",
        "image/webp",
    },
    BrandingAssetType.SPLASH: {"image/png", "image/jpeg", "image/webp"},
    BrandingAssetType.LAUNCHER_ICON: {"image/png", "image/webp"},
    BrandingAssetType.EMAIL_LOGO: {"image/png", "image/jpeg", "image/gif"},
    BrandingAssetType.LOGIN_BACKGROUND: {"image/png", "image/jpeg", "image/webp"},
    BrandingAssetType.WIDGET_LAUNCHER: {"image/png", "image/jpeg", "image/webp", "image/svg+xml"},
    BrandingAssetType.WIDGET_HEADER: {"image/png", "image/jpeg", "image/webp", "image/svg+xml"},
}

# Optional recommended max dimensions (width, height) — soft check
ASSET_MAX_DIM: Dict[BrandingAssetType, Tuple[int, int]] = {
    BrandingAssetType.FAVICON: (512, 512),
    BrandingAssetType.LAUNCHER_ICON: (1024, 1024),
    BrandingAssetType.WIDGET_LAUNCHER: (512, 512),
}


async def validate_brand_upload(
    file: UploadFile,
    asset_type: BrandingAssetType,
) -> Tuple[bytes, int, Optional[int], Optional[int]]:
    """
    Validate MIME + size for a branding asset.
    Returns (content_bytes, size, width, height).
    Width/height are best-effort via Pillow when available.
    """
    mime = file.content_type or "application/octet-stream"
    allowed = ASSET_MIME.get(asset_type, set())
    if mime not in allowed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported MIME for {asset_type.value}: {mime}. Allowed: {sorted(allowed)}",
        )

    data = await file.read()
    size = len(data)
    max_bytes = ASSET_MAX_BYTES.get(asset_type, 2 * 1024 * 1024)
    if size == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {max_bytes // 1024}KB limit for {asset_type.value}",
        )

    width = height = None
    try:
        from io import BytesIO

        from PIL import Image

        with Image.open(BytesIO(data)) as img:
            width, height = img.size
            max_dim = ASSET_MAX_DIM.get(asset_type)
            if max_dim and (width > max_dim[0] or height > max_dim[1]):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Image dimensions {width}x{height} exceed "
                        f"{max_dim[0]}x{max_dim[1]} for {asset_type.value}"
                    ),
                )
    except HTTPException:
        raise
    except Exception:
        # SVG / ICO / missing Pillow — skip dimension validation
        pass

    await file.seek(0)
    return data, size, width, height
