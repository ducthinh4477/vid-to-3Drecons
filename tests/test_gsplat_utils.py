from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from plyfile import PlyData, PlyElement

from src.reconstruction.gsplat_utils import CleanConfig, clean_ply


class CleanGsplatPlyTest(unittest.TestCase):
    def test_clean_ply_removes_noisy_points_and_writes_scene_json(self) -> None:
        dtype = [
            ("x", "f4"),
            ("y", "f4"),
            ("z", "f4"),
            ("opacity", "f4"),
            ("scale_0", "f4"),
            ("scale_1", "f4"),
            ("scale_2", "f4"),
            ("custom", "f4"),
        ]
        vertices = np.array(
            [
                (0.0, 0.0, 0.0, 0.9, 0.1, 0.1, 0.1, 1.0),
                (0.2, 0.0, 0.0, 0.8, 0.1, 0.1, 0.1, 2.0),
                (0.0, 0.2, 0.0, 0.7, 0.1, 0.1, 0.1, 3.0),
                (0.0, 0.0, 0.2, 0.01, 0.1, 0.1, 0.1, 4.0),
                (8.0, 8.0, 8.0, 0.8, 0.1, 0.1, 0.1, 5.0),
            ],
            dtype=dtype,
        )

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.ply"
            output_path = tmp_path / "cleaned.ply"
            scene_path = tmp_path / "viewer_scene.json"
            PlyData([PlyElement.describe(vertices, "vertex")], text=True).write(str(input_path))

            scene = clean_ply(
                input_path,
                output_path,
                scene_path,
                CleanConfig(opacity_min=0.03, position_quantile=(0.0, 0.8)),
            )

            cleaned = PlyData.read(str(output_path))["vertex"].data
            self.assertEqual(len(cleaned), 3)
            self.assertIn("custom", cleaned.dtype.names)
            self.assertTrue(scene_path.exists())
            self.assertEqual(scene["cleaning"]["count_before"], 5)
            self.assertEqual(scene["cleaning"]["count_after"], 3)
            self.assertEqual(scene["controls"]["mode"], "fps_locked")
            self.assertEqual(len(scene["bounds"]["min"]), 3)


if __name__ == "__main__":
    unittest.main()
