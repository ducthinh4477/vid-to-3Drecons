from __future__ import annotations

import cv2
from skimage.metrics import structural_similarity


def resize_gray(image_bgr, size: tuple[int, int] = (320, 180)):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, size, interpolation=cv2.INTER_AREA)


def ssim_similarity(image_a_bgr, image_b_bgr) -> float:
    gray_a = resize_gray(image_a_bgr)
    gray_b = resize_gray(image_b_bgr)
    score = structural_similarity(gray_a, gray_b, data_range=255)
    return float(score)
