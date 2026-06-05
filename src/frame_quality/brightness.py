from __future__ import annotations

import cv2
import numpy as np


def brightness_metrics(image_bgr) -> dict[str, float]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    gray_float = gray.astype(np.float32)

    brightness = float(gray_float.mean() / 255.0)
    dark_clip = float(np.mean(gray <= 5))
    bright_clip = float(np.mean(gray >= 250))
    clipping = float(dark_clip + bright_clip)
    dynamic_range = float((np.percentile(gray_float, 95) - np.percentile(gray_float, 5)) / 255.0)

    return {
        "brightness": brightness,
        "dark_clip": dark_clip,
        "bright_clip": bright_clip,
        "clipping": clipping,
        "dynamic_range": dynamic_range,
    }
