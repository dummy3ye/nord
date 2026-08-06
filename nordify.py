#!/usr/bin/env python3
"""
nordify v2.0.0 — Nord palette image transformer
================================================

Turn *any* image — photos, selfies, screenshots, logos, wallpapers — into
Nord-themed art without destroying the details that make complex images work.

Why naive approaches fail on selfies and photos
------------------------------------------------
A simple "map each pixel to its nearest Nord color" (16 colours) obliterates
facial gradients, skin texture, and subtle shading.  This tool uses a
multi-stage pipeline that **preserves luminance structure** while shifting the
colour palette:

  1. Content analysis (opt-in ``--auto``) detects skin tones, brightness,
     colour diversity and aspect ratio, then picks the best preset.
  2. Colour-space-aware grading — process in CIE LAB (perceptually uniform),
     sRGB, or HSV depending on the ``--color-space`` flag.
  3. A Nord LUT is applied to the L channel (LAB) or luminance (RGB) so the
     tonal structure is kept while hues shift to Polar Night / Frost / Snow
     Storm stops.
  4. Reinhard colour transfer is available as an alternative mapping method
     (``--map-method reinhard``) — it matches mean + variance in LAB space.
  5. Controlled blend back with the original keeps local hue alive; saturation
     is trimmed toward Nord's muted feel and a gentle S-curve tightens the
     tonal range.
  6. Edge-aware blending (``--edge-preserve``) reduces the grade strength near
     strong edges so boundaries stay crisp — critical for portraits.
  7. Skin-tone protection (``--protect-skin``) further shields face pixels
     from over-grading.
  8. Optional seeded k-means posterization (``--posterize N``) with optional
     Floyd-Steinberg dithering (``--dither``) for a flat graphic look.
  9. Local contrast enhancement, vignette, film grain, and colour temperature.

Commands
--------
  nordify.py convert  INPUT OUTPUT [options]   (default if no subcommand)
  nordify.py batch    INPUT_DIR/ OUTPUT_DIR/ [--glob PATTERN] [options]
  nordify.py presets                           list available presets
  nordify.py colors                            show the Nord palette
  nordify.py version                           show version

Backwards compatible — the old ``python nordify.py input output`` still works.

Dependencies: Pillow + numpy only (stdlib + those two — nothing exotic).

Examples
--------
  python nordify.py selfie.jpg selfie-nord.png
  python nordify.py selfie.jpg out.png --preset selfie
  python nordify.py photo.jpg out.png --preset landscape --edge-preserve
  python nordify.py logo.png  out.png --posterize 12 --dither
  python nordify.py --auto landscape.jpg landscape-nord.png
  python nordify.py batch ./raw/ ./nord/ --glob "*.png" --preset dark
"""

from __future__ import annotations

import argparse
import glob as globmod
import os
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  VERSION                                                                 ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
VERSION = "2.1.0"

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  THE NORD PALETTE                                                        ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

NORD: dict[str, tuple[int, int, int]] = {
    # Polar Night
    "nord0":  (46,  52,  64),
    "nord1":  (59,  66,  82),
    "nord2":  (67,  76,  94),
    "nord3":  (76,  86,  106),
    # Snow Storm
    "nord4":  (216, 222, 233),
    "nord5":  (229, 233, 240),
    "nord6":  (236, 239, 244),
    # Frost
    "nord7":  (143, 188, 187),
    "nord8":  (136, 192, 208),
    "nord9":  (129, 161, 193),
    "nord10": (94,  129, 172),
    # Aurora
    "nord11": (191, 97,  106),
    "nord12": (208, 135, 112),
    "nord13": (235, 203, 139),
    "nord14": (163, 190, 140),
    "nord15": (180, 142, 173),
}

NORD_COLORS: list[tuple[int, int, int]] = list(NORD.values())
_NORD_RGB = np.array(NORD_COLORS, dtype=np.float32)

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  GRADE PRESETS — different luminance → Nord-colour mapping curves        ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

GRADE_STOPS: dict[str, tuple[tuple[float, str], ...]] = {
    "balanced": (
        (0.00, "nord0"), (0.10, "nord1"), (0.22, "nord2"), (0.38, "nord3"),
        (0.55, "nord9"), (0.72, "nord8"), (0.88, "nord5"), (1.00, "nord6"),
    ),
    "dark": (
        (0.00, "nord0"), (0.15, "nord0"), (0.30, "nord1"), (0.45, "nord2"),
        (0.60, "nord3"), (0.75, "nord9"), (0.90, "nord5"), (1.00, "nord6"),
    ),
    "light": (
        (0.00, "nord2"), (0.12, "nord3"), (0.28, "nord9"), (0.45, "nord8"),
        (0.62, "nord7"), (0.78, "nord4"), (0.90, "nord5"), (1.00, "nord6"),
    ),
    "aurora": (
        (0.00, "nord0"), (0.12, "nord1"), (0.25, "nord3"), (0.40, "nord10"),
        (0.55, "nord15"), (0.68, "nord14"), (0.80, "nord13"),
        (0.92, "nord5"), (1.00, "nord6"),
    ),
}

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  PROCESSING PRESETS                                                      ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

_PRESET_DEFAULTS = dict(
    blend=0.65, saturation=0.85, contrast=0.12, posterize=0,
    vignette=0.0, grain=0.0, color_space="lab", map_method="grade",
    edge_preserve=False, protect_skin=False, dither=False,
    local_contrast=0.0, temperature="cool", grade_curve="balanced",
    max_size=4096, quality=95,
)

PRESETS: dict[str, dict] = {
    "default": {**_PRESET_DEFAULTS},
    "selfie": {
        **_PRESET_DEFAULTS,
        "blend": 0.55, "saturation": 0.90, "contrast": 0.08,
        "edge_preserve": True, "protect_skin": True,
        "local_contrast": 0.10, "temperature": "neutral",
        "color_space": "lab",
    },
    "landscape": {
        **_PRESET_DEFAULTS,
        "blend": 0.75, "saturation": 0.80, "contrast": 0.18,
        "vignette": 0.15, "local_contrast": 0.20, "grade_curve": "balanced",
    },
    "dark": {
        **_PRESET_DEFAULTS,
        "blend": 0.85, "saturation": 0.70, "contrast": 0.22,
        "vignette": 0.25, "grain": 2.0, "grade_curve": "dark",
        "color_space": "rgb",
    },
    "aurora": {
        **_PRESET_DEFAULTS,
        "blend": 0.70, "saturation": 1.00, "contrast": 0.15,
        "vignette": 0.10, "map_method": "reinhard",
        "grade_curve": "aurora", "temperature": "neutral",
    },
    "retro": {
        **_PRESET_DEFAULTS,
        "blend": 0.80, "saturation": 0.75, "contrast": 0.20,
        "vignette": 0.30, "grain": 8.0, "posterize": 12, "dither": True,
        "temperature": "warm", "color_space": "rgb",
    },
    "posterized": {
        **_PRESET_DEFAULTS,
        "blend": 0.70, "saturation": 0.90, "contrast": 0.10,
        "posterize": 16, "dither": True, "color_space": "rgb",
    },
    "minimal": {
        **_PRESET_DEFAULTS,
        "blend": 0.30, "saturation": 0.95, "contrast": 0.05,
        "color_space": "lab", "temperature": "neutral",
    },
}

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  COLOUR-SPACE CONVERSIONS  (sRGB ↔ linear ↔ XYZ ↔ CIE LAB)             ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
# All accept and return float32 arrays in 0..255 (RGB) or LAB range.

# D65 reference white
_XN, _YN, _ZN = 0.95047, 1.00000, 1.08883


def srgb_to_linear(c: np.ndarray) -> np.ndarray:
    """sRGB (0..1) → linear (0..1), vectorised."""
    out = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return out.astype(np.float32)


def linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, None)  # Reinhard/histogram can produce negatives
    out = np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1.0 / 2.4) - 0.055)
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def rgb_to_linear(rgb: np.ndarray) -> np.ndarray:
    return srgb_to_linear(rgb / 255.0)


def linear_to_rgb(lin: np.ndarray) -> np.ndarray:
    return np.clip(linear_to_srgb(lin) * 255.0, 0.0, 255.0)


def linear_to_xyz(lin: np.ndarray) -> np.ndarray:
    """Linear RGB (0..1) → XYZ (D65), (…, 3) array."""
    r, g, b = lin[..., 0], lin[..., 1], lin[..., 2]
    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b
    return np.stack([x, y, z], axis=-1).astype(np.float32)


def xyz_to_linear(xyz: np.ndarray) -> np.ndarray:
    """XYZ → linear RGB (0..1), (…, 3) array."""
    x, y, z = xyz[..., 0], xyz[..., 1], xyz[..., 2]
    r =  3.2404542 * x - 1.5371385 * y - 0.4985314 * z
    g = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z
    b =  0.0556434 * x - 0.2040259 * y + 1.0572252 * z
    return np.stack([r, g, b], axis=-1).astype(np.float32)


def _lab_f(t: np.ndarray) -> np.ndarray:
    delta = 6.0 / 29.0
    return np.where(t > delta ** 3, np.cbrt(t), t / (3 * delta ** 2) + 4.0 / 29.0)


def _lab_f_inv(t: np.ndarray) -> np.ndarray:
    delta = 6.0 / 29.0
    return np.where(t > delta, t ** 3, 3 * delta ** 2 * (t - 4.0 / 29.0))


def xyz_to_lab(xyz: np.ndarray) -> np.ndarray:
    fx = _lab_f(xyz[..., 0] / _XN)
    fy = _lab_f(xyz[..., 1] / _YN)
    fz = _lab_f(xyz[..., 2] / _ZN)
    L = 116.0 * fy - 16.0
    a = 500.0 * (fx - fy)
    b = 200.0 * (fy - fz)
    return np.stack([L, a, b], axis=-1).astype(np.float32)


def lab_to_xyz(lab: np.ndarray) -> np.ndarray:
    fy = (lab[..., 0] + 16.0) / 116.0
    fx = lab[..., 1] / 500.0 + fy
    fz = fy - lab[..., 2] / 200.0
    x = _XN * _lab_f_inv(fx)
    y = _YN * _lab_f_inv(fy)
    z = _ZN * _lab_f_inv(fz)
    return np.stack([x, y, z], axis=-1).astype(np.float32)


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB (0..255) → CIE LAB (L 0..100, a ±128, b ±128)."""
    return xyz_to_lab(linear_to_xyz(rgb_to_linear(rgb)))


def lab_to_rgb(lab: np.ndarray) -> np.ndarray:
    return linear_to_rgb(xyz_to_linear(lab_to_xyz(lab)))


def rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    """RGB (0..255) → HSV (H 0..360, S 0..1, V 0..1)."""
    r, g, b = rgb[..., 0] / 255.0, rgb[..., 1] / 255.0, rgb[..., 2] / 255.0
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    diff = mx - mn
    h = np.zeros_like(mx)
    # Hue
    mask = diff > 1e-6
    mr = mask & (mx == r)
    mg = mask & (mx == g) & ~mr
    mb = mask & (mx == b) & ~mr & ~mg
    h[mr] = 60.0 * (((g[mr] - b[mr]) / diff[mr]) % 6.0)
    h[mg] = 60.0 * (((b[mg] - r[mg]) / diff[mg]) + 2.0)
    h[mb] = 60.0 * (((r[mb] - g[mb]) / diff[mb]) + 4.0)
    h = h % 360.0
    s = np.where(mx > 1e-6, diff / mx, 0.0)
    return np.stack([h, s, mx], axis=-1).astype(np.float32)


def hsv_to_rgb(hsv: np.ndarray) -> np.ndarray:
    """HSV (H 0..360, S 0..1, V 0..1) → RGB (0..255)."""
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    c = v * s
    hp = (h / 60.0) % 6.0
    x = c * (1.0 - np.abs(hp - 2 * np.floor(hp / 2.0) - 1.0))
    m = v - c
    r = np.zeros_like(h); g = np.zeros_like(h); b = np.zeros_like(h)
    for i, (rs, gs, bs) in enumerate([
        (1, 2, 0), (2, 1, 0), (0, 1, 2),
        (0, 2, 1), (2, 0, 1), (1, 0, 2),
    ]):
        mask = np.floor(hp) == i
        comps = [c, x, np.zeros_like(c)]
        r[mask] = comps[rs][mask]
        g[mask] = comps[gs][mask]
        b[mask] = comps[bs][mask]
    return (np.stack([r, g, b], axis=-1) + np.stack([m, m, m], axis=-1)) * 255.0

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  LUMINANCE & BASIC MATH                                                   ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def luminance(rgb: np.ndarray) -> np.ndarray:
    """Rec.709 luma, 0..255."""
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def adjust_saturation_rgb(rgb: np.ndarray, factor: float) -> np.ndarray:
    if abs(factor - 1.0) < 1e-6:
        return rgb
    gray = luminance(rgb)[..., None]
    return gray + (rgb - gray) * factor


def contrast_curve(rgb: np.ndarray, amount: float) -> np.ndarray:
    if abs(amount) < 1e-6:
        return rgb
    x = np.clip(rgb / 255.0, 0.0, 1.0)
    s = x * x * (3.0 - 2.0 * x)
    return np.clip(x + amount * (s - x), 0.0, 1.0) * 255.0

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  GRADE LUT                                                               ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def build_grade_lut(curve: str = "balanced") -> np.ndarray:
    """256-entry LUT: grayscale → Nord-graded RGB (interpolated)."""
    stops = [(v, np.array(NORD[n], np.float32)) for v, n in GRADE_STOPS[curve]]
    lut = np.zeros((256, 3), dtype=np.float32)
    for g in range(256):
        x = g / 255.0
        for i in range(len(stops) - 1):
            v0, c0 = stops[i]
            v1, c1 = stops[i + 1]
            if v0 <= x <= v1:
                t = 0.0 if v1 == v0 else (x - v0) / (v1 - v0)
                lut[g] = (1.0 - t) * c0 + t * c1
                break
    return lut

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  REINHARD COLOUR TRANSFER  (mean + std in LAB space)                     ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _nord_reference_lab() -> tuple[np.ndarray, np.ndarray]:
    """Mean and std of the Nord palette in LAB (computed from all 16 colours)."""
    lab = rgb_to_lab(_NORD_RGB)           # (16, 3)
    return lab.mean(axis=0), lab.std(axis=0) + 1e-6


def reinhard_transfer(source_rgb: np.ndarray) -> np.ndarray:
    """Match source image colour statistics to Nord palette in LAB space."""
    src_lab = rgb_to_lab(source_rgb)
    src_mu, src_std = src_lab.mean(axis=(0, 1)), src_lab.std(axis=(0, 1)) + 1e-6
    tgt_mu, tgt_std = _nord_reference_lab()
    transferred = (src_lab - src_mu) * (tgt_std / src_std) + tgt_mu
    return np.clip(lab_to_rgb(transferred), 0, 255)

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  HISTOGRAM MATCHING                                                      ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _nord_channel_histograms() -> list[np.ndarray]:
    """Per-channel histograms (256 bins) from a Nord gradient reference."""
    stops = [
        (0,   NORD["nord0"]),  (32,  NORD["nord1"]),  (64,  NORD["nord2"]),
        (96,  NORD["nord3"]),  (128, NORD["nord9"]),  (160, NORD["nord8"]),
        (192, NORD["nord7"]),  (216, NORD["nord5"]),  (255, NORD["nord6"]),
    ]
    grad = np.zeros((256, 3), dtype=np.float32)
    for c in range(3):
        grad[:, c] = np.interp(range(256), [s[0] for s in stops],
                               [s[1][c] for s in stops])
    hists = []
    for c in range(3):
        h, _ = np.histogram(grad[:, c], bins=256, range=(0, 255))
        hists.append(h.astype(np.float64) + 1.0)     # avoid zero bins
    return hists


_NORD_HISTS: list[np.ndarray] | None = None


def _get_nord_hists() -> list[np.ndarray]:
    global _NORD_HISTS
    if _NORD_HISTS is None:
        _NORD_HISTS = _nord_channel_histograms()
    return _NORD_HISTS


def _match_channel(channel: np.ndarray, target_hist: np.ndarray) -> np.ndarray:
    src_hist, _ = np.histogram(channel, bins=256, range=(0, 255))
    src_cdf = src_hist.cumsum().astype(np.float64)
    src_cdf /= src_cdf[-1] or 1.0
    tgt_cdf = target_hist.cumsum().astype(np.float64)
    tgt_cdf /= tgt_cdf[-1] or 1.0
    lut = np.zeros(256, dtype=np.uint8)
    for v in range(256):
        lut[v] = int(np.searchsorted(tgt_cdf, src_cdf[v], side="left"))
    return lut[np.clip(channel, 0, 255).astype(np.uint8)]


def histogram_match_rgb(rgb: np.ndarray) -> np.ndarray:
    """Match each RGB channel's histogram to the Nord reference."""
    hists = _get_nord_hists()
    out = np.stack([
        _match_channel(rgb[..., c], hists[c]) for c in range(3)
    ], axis=-1).astype(np.float32)
    return out

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  EDGE-AWARE BLENDING                                                     ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def edge_mask(rgb: np.ndarray, sigma: float = 2.0) -> np.ndarray:
    """1.0 in smooth areas, 0.0 at strong edges (for blend suppression)."""
    gray = luminance(rgb) / 255.0
    # Gradient magnitude via differences
    dx = np.abs(np.diff(gray, axis=1))
    dy = np.abs(np.diff(gray, axis=0))
    dx = np.pad(dx, ((0, 0), (0, 1)), mode="edge")
    dy = np.pad(dy, ((0, 1), (0, 0)), mode="edge")
    edge = np.sqrt(dx ** 2 + dy ** 2)
    mx = edge.max()
    if mx > 0:
        edge /= mx
    mask = 1.0 - np.clip(edge, 0, 1)
    # Smooth the mask
    if sigma > 0:
        mask_img = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
        mask_img = mask_img.filter(ImageFilter.GaussianBlur(sigma))
        mask = np.asarray(mask_img, np.float32) / 255.0
    return mask

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  SKIN-TONE DETECTION                                                     ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def skin_mask(rgb: np.ndarray, dilate_px: int = 3) -> np.ndarray:
    """Binary mask (0/1 float) of likely skin-tone pixels."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    skin = ((r > 95) & (g > 40) & (b > 20)
            & (r > g) & (r > b)
            & (np.abs(r.astype(np.float32) - g.astype(np.float32)) > 15))
    mask = skin.astype(np.float32)
    # Dilate to cover edges
    if dilate_px > 0:
        img = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
        for _ in range(dilate_px):
            img = img.filter(ImageFilter.MaxFilter(3))
        mask = np.asarray(img, np.float32) / 255.0
    return mask

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  LOCAL CONTRAST ENHANCEMENT (simplified CLAHE)                           ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def local_contrast_enhance(rgb: np.ndarray, amount: float, radius: int = 20) -> np.ndarray:
    if abs(amount) < 1e-6:
        return rgb
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
    local_mean = np.asarray(
        img.filter(ImageFilter.GaussianBlur(radius)), np.float32
    )
    detail = rgb - local_mean
    return local_mean + detail * (1.0 + amount)

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  COLOUR TEMPERATURE                                                      ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

_TEMP_SHIFT = {
    "warm":   (+8.0, +6.0),    # a↑ (red), b↑ (yellow)
    "neutral": (0.0, 0.0),
    "cool":   (-6.0, -10.0),   # a↓ (cyan), b↓ (blue)
}


def apply_temperature_lab(lab: np.ndarray, temp: str) -> np.ndarray:
    """Shift a/b channels for colour temperature."""
    da, db = _TEMP_SHIFT.get(temp, (0, 0))
    if abs(da) < 0.1 and abs(db) < 0.1:
        return lab
    out = lab.copy()
    out[..., 1] += da
    out[..., 2] += db
    return out

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  FLOYD–STEINBERG DITHERING                                               ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def pick_colors(n: int) -> list[tuple[int, int, int]]:
    """Spread n Nord colours across the full range."""
    if n >= len(NORD_COLORS):
        return NORD_COLORS
    idx = np.linspace(0, len(NORD_COLORS) - 1, n).astype(int)
    return [NORD_COLORS[i] for i in idx]


def seeded_kmeans(rgb: np.ndarray, colors: list, max_iter: int = 24) -> np.ndarray:
    """K-means posterization seeded with given colours (fits on a subsample)."""
    rgb = np.asarray(rgb, dtype=np.float32)
    h, w = rgb.shape[:2]
    step = max(1, int(np.sqrt(h * w / 20000.0)))
    sample = rgb[::step, ::step].reshape(-1, 3)
    centers = np.array(colors, dtype=np.float32)
    for _ in range(max_iter):
        d = np.sum((sample[:, None] - centers[None]) ** 2, axis=2)
        labels = d.argmin(axis=1)
        nc = np.array([
            sample[labels == k].mean(0) if np.any(labels == k) else centers[k]
            for k in range(len(centers))
        ], dtype=np.float32)
        if np.abs(nc - centers).max() < 0.5:
            centers = nc
            break
        centers = nc
    flat = rgb.reshape(-1, 3)
    d = np.sum((flat[:, None] - centers[None]) ** 2, axis=2)
    return centers[d.argmin(axis=1)].reshape(h, w, 3)


def floyd_steinberg_dither(rgb: np.ndarray,
                           palette: list[tuple[int, int, int]]) -> np.ndarray:
    """Floyd–Steinberg dithering to a fixed palette (slow but precise)."""
    pal = np.array(palette, dtype=np.float64)
    h, w, _ = rgb.shape
    img = rgb.astype(np.float64)
    out = np.zeros_like(rgb, dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            old = img[y, x].copy()
            new = pal[np.argmin(np.sum((pal - old) ** 2, axis=1))]
            img[y, x] = new
            out[y, x] = new.astype(np.uint8)
            err = old - new
            if x + 1 < w:       img[y, x + 1] += err * (7 / 16)
            if y + 1 < h:
                if x > 0:       img[y + 1, x - 1] += err * (3 / 16)
                img[y + 1, x] += err * (5 / 16)
                if x + 1 < w:   img[y + 1, x + 1] += err * (1 / 16)
    return out

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  IMAGE ANALYSIS (for --auto content-adaptive mode)                       ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def analyze_image(rgb: np.ndarray) -> dict:
    """Return content features: has_skin, dark, bright, colorful, portrait, etc."""
    h, w = rgb.shape[:2]
    lum = luminance(rgb)
    skin = skin_mask(rgb)
    flat = rgb.reshape(-1, 3)
    idx = np.random.default_rng(42).choice(len(flat), min(5000, len(flat)), replace=False)
    var = flat[idx].astype(np.float32).var(axis=0).mean()
    return {
        "has_skin": float(skin.mean()) > 0.015,
        "dark": lum.mean() < 80,
        "bright": lum.mean() > 180,
        "colorful": var > 2000,
        "low_contrast": var < 500,
        "portrait": h > w * 1.2,
        "landscape": w > h * 1.2,
    }


def pick_auto_preset(info: dict) -> str:
    if info["has_skin"]:
        return "selfie"
    if info["dark"] and info["low_contrast"]:
        return "dark"
    if info["landscape"]:
        return "landscape"
    return "default"

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  SEPIA / NORD WARM TINT  (temperature in RGB space for simple case)      ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _temperature_rgb(rgb: np.ndarray, temp: str) -> np.ndarray:
    """Simple per-channel temperature shift in RGB."""
    if temp == "neutral":
        return rgb
    shift = {"warm": np.array([12, 0, -12], np.float32),
             "cool": np.array([-8, 4, 16],  np.float32)}
    return np.clip(rgb + shift.get(temp, [0, 0, 0]), 0, 255)

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  MAIN PIPELINE                                                           ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def nordify(
    img: Image.Image,
    *,
    blend: float = 0.65,
    saturation: float = 0.85,
    contrast: float = 0.12,
    posterize: int = 0,
    vignette: float = 0.0,
    grain: float = 0.0,
    color_space: str = "lab",
    map_method: str = "grade",
    edge_preserve: bool = False,
    protect_skin: bool = False,
    dither: bool = False,
    local_contrast: float = 0.0,
    temperature: str = "cool",
    grade_curve: str = "balanced",
    max_size: int = 4096,
    quality: int = 95,
    verbose: bool = False,
) -> Image.Image:
    """Full Nord treatment.  Returns a new PIL Image."""

    def _log(msg: str) -> None:
        if verbose:
            print(f"  {msg}", file=sys.stderr)

    # ── transparency ────────────────────────────────────────────────────
    alpha = None
    if img.mode in ("RGBA", "LA") or (
        img.mode == "P" and "transparency" in img.info
    ):
        alpha = img.convert("RGBA").getchannel("A")
    img = img.convert("RGB")

    # ── downscale ───────────────────────────────────────────────────────
    if max_size and max(img.size) > max_size:
        scale = max_size / float(max(img.size))
        img = img.resize(
            (int(img.size[0] * scale), int(img.size[1] * scale)),
            Image.LANCZOS,
        )
        _log(f"downscaled to {img.size[0]}x{img.size[1]}")

    rgb = np.asarray(img, dtype=np.float32)
    _log(f"colour-space: {color_space} | map: {map_method} | curve: {grade_curve}")

    # ── stage 1: colour mapping ─────────────────────────────────────────
    if map_method == "reinhard":
        graded = reinhard_transfer(rgb)
        _log("applied Reinhard colour transfer (LAB)")
    elif map_method == "histogram":
        graded = histogram_match_rgb(rgb)
        _log("applied histogram matching to Nord reference")
    else:
        # grade-based: luminance-preserving Nord LUT
        lut = build_grade_lut(grade_curve)
        if color_space == "lab":
            # Grade the L channel in LAB while keeping a/b
            lab = rgb_to_lab(rgb)
            lum8 = np.clip(lab[..., 0] / 100.0 * 255.0, 0, 255).astype(np.uint8)
            grade_lut_rgb = lut[lum8]  # (H,W,3) as Nord RGB
            grade_lab = rgb_to_lab(grade_lut_rgb)
            # Replace L from grade, blend a/b between original and grade
            lab[..., 0] = grade_lab[..., 0]
            graded_rgb = lab_to_rgb(lab)
        elif color_space == "hsv":
            hsv = rgb_to_hsv(rgb)
            lum8 = np.clip(hsv[..., 2] * 255, 0, 255).astype(np.uint8)
            graded_rgb = lut[lum8]
        else:  # rgb
            lum8 = np.clip(luminance(rgb), 0, 255).astype(np.uint8)
            graded_rgb = lut[lum8]
        graded = graded_rgb
        _log(f"applied grade LUT (curve={grade_curve})")

    # ── stage 2: edge-aware blend factor ────────────────────────────────
    eff_blend = blend
    if edge_preserve:
        emask = edge_mask(rgb, sigma=2.0)
        local_blend = np.clip(blend * emask, 0, 1)  # reduce blend near edges
        out = (1.0 - local_blend[..., None]) * rgb + local_blend[..., None] * graded
        _log(f"edge-preserve blend (mean blend factor: {local_blend.mean():.2f})")
    else:
        out = (1.0 - blend) * rgb + blend * graded

    # ── stage 3: saturation ─────────────────────────────────────────────
    out = adjust_saturation_rgb(out, saturation)

    # ── stage 4: skin protection (post-blend, restore some original hue) ─
    if protect_skin:
        smask = skin_mask(rgb, dilate_px=4)
        restore = 0.35  # restore 35 % of original in skin areas
        out = out * (1.0 - smask[..., None] * restore) + rgb * (smask[..., None] * restore)
        _log(f"skin protection ({smask.mean() * 100:.1f}% of pixels)")

    # ── stage 5: temperature ────────────────────────────────────────────
    if color_space == "lab":
        lab = rgb_to_lab(np.clip(out, 0, 255))
        lab = apply_temperature_lab(lab, temperature)
        out = lab_to_rgb(lab)
    else:
        out = _temperature_rgb(out, temperature)

    # ── stage 6: contrast ───────────────────────────────────────────────
    out = contrast_curve(out, contrast)

    # ── stage 7: local contrast ─────────────────────────────────────────
    if abs(local_contrast) > 1e-6:
        out = local_contrast_enhance(out, local_contrast)
        _log(f"local contrast +{local_contrast:.2f}")

    # ── stage 8: posterize / dither ─────────────────────────────────────
    if posterize > 0:
        colors = pick_colors(posterize)
        if dither:
            _log(f"dithering to {posterize} Nord colours (slow for large images)")
            out = floyd_steinberg_dither(np.clip(out, 0, 255), colors)
        else:
            out = seeded_kmeans(out, colors)
        _log(f"posterized to {posterize} Nord colours")

    # ── stage 9: vignette ───────────────────────────────────────────────
    if vignette and vignette > 0:
        h, w = out.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        r = np.sqrt(((xx - cx) / max(cx, 1)) ** 2 + ((yy - cy) / max(cy, 1)) ** 2)
        out = out * (1.0 - vignette * np.clip(r, 0, 1) ** 2)[..., None]
        _log(f"vignette strength {vignette}")

    # ── stage 10: grain ─────────────────────────────────────────────────
    if grain and grain > 0:
        out = out + np.random.normal(0.0, grain, out.shape)
        _log(f"grain σ={grain}")

    # ── final clip ──────────────────────────────────────────────────────
    out = np.clip(out, 0, 255).astype(np.uint8)
    result = Image.fromarray(out)

    if alpha is not None:
        result.putalpha(alpha)
    return result

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  BATCH PROCESSING                                                        ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def run_batch(args: argparse.Namespace) -> None:
    in_dir = Path(args.input_dir)
    out_dir = Path(args.output_dir)
    if not in_dir.is_dir():
        sys.exit(f"error: {in_dir} is not a directory")
    out_dir.mkdir(parents=True, exist_ok=True)

    pattern = args.glob or "*"
    exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}
    files = sorted(
        p for p in in_dir.glob(pattern)
        if p.suffix.lower() in exts
    )
    if not files:
        sys.exit(f"error: no images found matching {pattern!r} in {in_dir}")

    print(f"nordify batch: {len(files)} files → {out_dir}/")
    ok = 0
    for i, fpath in enumerate(files, 1):
        try:
            img = Image.open(fpath)
        except OSError as e:
            print(f"  [{i}/{len(files)}] SKIP {fpath.name}: {e}")
            continue
        result = nordify(img, **_preset_to_kwargs(args), verbose=args.verbose)
        out_path = out_dir / fpath.name
        if out_path.suffix.lower() in (".jpg", ".jpeg") and result.mode == "RGBA":
            bg = Image.new("RGB", result.size, NORD["nord0"])
            bg.paste(result, mask=result.getchannel("A"))
            result = bg
        result.save(out_path, quality=args.quality)
        ok += 1
        print(f"  [{i}/{len(files)}] {fpath.name} → {out_path.name}")

    print(f"done: {ok}/{len(files)} converted")


def _preset_to_kwargs(args: argparse.Namespace) -> dict:
    """Map argparse namespace to nordify() keyword arguments."""
    return {
        "blend": args.blend,
        "saturation": args.saturation,
        "contrast": args.contrast,
        "posterize": args.posterize,
        "vignette": args.vignette,
        "grain": args.grain,
        "color_space": args.color_space,
        "map_method": args.map_method,
        "edge_preserve": args.edge_preserve,
        "protect_skin": args.protect_skin,
        "dither": args.dither,
        "local_contrast": args.local_contrast,
        "temperature": args.temperature,
        "grade_curve": args.grade_curve,
        "max_size": args.max_size,
        "quality": args.quality,
    }

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CLI — argparse                                                          ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

_USAGE_CONVERT = """\
nordify convert INPUT OUTPUT [options]
  or (backwards-compatible):
nordify INPUT OUTPUT [options]

Apply the Nord theme to a single image."""

_USAGE_BATCH = """\
nordify batch INPUT_DIR/ OUTPUT_DIR/ [--glob "*.png"] [options]

Convert every image in a directory."""

_DESCRIPTION = f"""\
nordify v{VERSION} — Nord palette image transformer

Transform photos, selfies, screenshots, and logos into Nord-themed art.
Processes in CIE LAB space by default for perceptually accurate grading."""

_GRADE_CURVES = list(GRADE_STOPS.keys())
_MAP_METHODS = ["grade", "reinhard", "histogram"]
_COLOR_SPACES = ["rgb", "lab", "hsv"]
_TEMPS = list(_TEMP_SHIFT.keys())
_PRESET_NAMES = list(PRESETS.keys())


def _add_common_args(p: argparse.ArgumentParser) -> None:
    """Add flags shared by convert and batch."""
    p.add_argument("--preset", choices=_PRESET_NAMES, default=None,
                   help="use a named preset (overrides individual flags)")
    p.add_argument("--auto", action="store_true",
                   help="analyse the image and pick the best preset automatically")
    p.add_argument("--blend", type=float, default=0.65,
                   help="grade strength (0-1, default 0.65)")
    p.add_argument("--saturation", type=float, default=0.85,
                   help="saturation multiplier (1 = muted, 0 = grey)")
    p.add_argument("--contrast", type=float, default=0.12,
                   help="S-curve contrast (0 = off)")
    p.add_argument("--posterize", type=int, default=0, metavar="N",
                   help="posterize to N Nord colours (0 = off)")
    p.add_argument("--vignette", type=float, default=0.0,
                   help="edge darkening (0-1, 0 = off)")
    p.add_argument("--grain", type=float, default=0.0,
                   help="film grain σ (0 = off)")
    p.add_argument("--color-space", choices=_COLOR_SPACES, default="lab",
                   help="processing colour space (default: lab)")
    p.add_argument("--map-method", choices=_MAP_METHODS, default="grade",
                   help="colour mapping algorithm (default: grade)")
    p.add_argument("--edge-preserve", action="store_true",
                   help="reduce grade near strong edges (good for portraits)")
    p.add_argument("--protect-skin", action="store_true",
                   help="shield skin-tone pixels from over-grading")
    p.add_argument("--dither", action="store_true",
                   help="Floyd–Steinberg dithering (with --posterize)")
    p.add_argument("--local-contrast", type=float, default=0.0,
                   help="local contrast enhancement (0 = off)")
    p.add_argument("--temperature", choices=_TEMPS, default="cool",
                   help="colour temperature (default: cool)")
    p.add_argument("--grade-curve", choices=_GRADE_CURVES, default="balanced",
                   help="grade mapping curve (default: balanced)")
    p.add_argument("--max-size", type=int, default=4096,
                   help="downscale longest side to this many px")
    p.add_argument("--quality", type=int, default=95,
                   help="JPEG/WebP output quality (1-100)")
    p.add_argument("--force", action="store_true",
                   help="overwrite existing output without asking")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="print processing details")


def _apply_preset_if_needed(args: argparse.Namespace) -> None:
    """Override defaults with preset values (if --preset or --auto set)."""
    preset_name = args.preset
    if preset_name and preset_name in PRESETS:
        for k, v in PRESETS[preset_name].items():
            if hasattr(args, k):
                setattr(args, k, v)


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    # ── handle subcommands / backwards compatibility ─────────────────────
    if not argv or argv[0] in ("-h", "--help"):
        print(_DESCRIPTION)
        print()
        print("commands: convert (default), batch, presets, colors, version")
        print("run 'nordify COMMAND --help' for per-command help")
        return

    cmd = argv[0]

    # version
    if cmd in ("version", "--version", "-V"):
        print(f"nordify {VERSION}")
        return

    # presets listing
    if cmd == "presets":
        print(f"nordify v{VERSION} — available presets:\n")
        for name, vals in PRESETS.items():
            print(f"  {name:14s}  blend={vals['blend']:.2f}  "
                  f"sat={vals['saturation']:.2f}  con={vals['contrast']:.2f}  "
                  f"grade={vals['grade_curve']}  space={vals['color_space']}  "
                  f"map={vals['map_method']}")
        return

    # colors listing
    if cmd == "colors":
        print(f"nordify v{VERSION} — Nord palette (16 colours):\n")
        for name, rgb in NORD.items():
            r, g, b = rgb
            print(f"  {name:8s}  #{r:02x}{g:02x}{b:02x}  ({r:3d}, {g:3d}, {b:3d})")
        return

    # batch
    if cmd == "batch":
        bp = argparse.ArgumentParser(
            prog="nordify batch",
            description="Batch-convert images in a directory.",
        )
        bp.add_argument("input_dir", help="source directory")
        bp.add_argument("output_dir", help="destination directory")
        bp.add_argument("--glob", default=None, metavar="PAT",
                        help="filename pattern (default: *)")
        _add_common_args(bp)
        args = bp.parse_args(argv[1:])
        _apply_preset_if_needed(args)
        run_batch(args)
        return

    # ── convert (default — also handles backwards-compatible "nordify in out") ──
    # If argv[0] is "convert", skip it; otherwise treat all argv as convert args.
    conv_argv = argv[1:] if cmd == "convert" else argv

    cp = argparse.ArgumentParser(
        prog="nordify",
        description=_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  nordify selfie.jpg selfie-nord.png
  nordify photo.jpg out.png --preset dark --verbose
  nordify logo.png out.png --posterize 8 --dither
  nordify --auto landscape.jpg landscape-nord.png
  nordify batch ./raw/ ./nord/ --glob "*.png" --preset aurora
""",
    )
    cp.add_argument("input", help="input image file")
    cp.add_argument("output", help="output image file (ext picks format)")
    _add_common_args(cp)
    args = cp.parse_args(conv_argv)

    # apply preset overrides
    if args.auto:
        try:
            img_probe = Image.open(args.input).convert("RGB")
            rgb_probe = np.asarray(img_probe, dtype=np.float32)
            info = analyze_image(rgb_probe)
            auto_name = pick_auto_preset(info)
            print(f"auto-detected: {info} → preset '{auto_name}'")
            args.preset = auto_name
        except OSError as e:
            sys.exit(f"error: couldn't analyse {args.input!r}: {e}")
    _apply_preset_if_needed(args)

    # open
    try:
        img = Image.open(args.input)
    except OSError as e:
        sys.exit(f"error: couldn't open {args.input!r}: {e}")

    # overwrite guard
    if os.path.exists(args.output) and not args.force:
        sys.exit(f"error: {args.output} already exists (use --force to overwrite)")

    # process
    t0 = time.time()
    result = nordify(img, **_preset_to_kwargs(args), verbose=args.verbose)
    elapsed = time.time() - t0

    # JPEG can't store alpha — flatten onto Nord backdrop
    if result.mode == "RGBA" and args.output.lower().endswith((".jpg", ".jpeg")):
        bg = Image.new("RGB", result.size, NORD["nord0"])
        bg.paste(result, mask=result.getchannel("A"))
        result = bg

    result.save(args.output, quality=args.quality)
    print(f"wrote {args.output}  ({result.size[0]}x{result.size[1]}, "
          f"{result.mode}, {elapsed:.2f}s)")


if __name__ == "__main__":
    main()
