from __future__ import annotations

import cv2


def orb_keypoint_count(image_bgr, max_features: int = 5000) -> int:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=max_features)
    keypoints = orb.detect(gray, None)
    return int(len(keypoints))
