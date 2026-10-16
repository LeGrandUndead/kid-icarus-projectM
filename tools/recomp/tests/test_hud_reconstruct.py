"""HUD reconstruction on synthetic shapes (no game art in the repository)."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hud_reconstruct as hr  # noqa: E402


def canvas(size=48):
    return np.zeros((size, size, 4), np.float32)


def disc(img, cx, cy, r, rgba):
    y, x = np.mgrid[:img.shape[0], :img.shape[1]]
    img[(x - cx) ** 2 + (y - cy) ** 2 <= r * r] = rgba
    return img


class Reconstruction(unittest.TestCase):
    def test_black_ornament_is_traced_and_keeps_its_hole(self):
        img = disc(canvas(), 24, 24, 14, (0, 0, 0, 1))
        img = disc(img, 24, 24, 5, (0, 0, 0, 0))            # a hole
        out, manifest = hr.reconstruct_atlas(img)
        self.assertEqual(out.shape, (48 * hr.FACTOR, 48 * hr.FACTOR, 4))
        self.assertEqual(manifest[0]['method'], 'flat')
        c = 24 * hr.FACTOR
        self.assertLess(out[c, c, 3], 0.01, 'hole stays transparent')
        self.assertGreater(out[c, c + 9 * hr.FACTOR, 3], 0.99, 'ring stays solid')
        self.assertLess(out[0, 0, 3], 0.01, 'corner stays transparent')

    def test_white_digit_with_black_outline_keeps_two_layers(self):
        img = disc(canvas(), 24, 24, 12, (0, 0, 0, 1))
        img = disc(img, 24, 24, 8, (1, 1, 1, 1))
        out, manifest = hr.reconstruct_atlas(img)
        self.assertEqual(manifest[0]['method'], 'flat')
        c = 24 * hr.FACTOR
        self.assertGreater(out[c, c, :3].min(), 0.98, 'white fill')
        self.assertLess(out[c, c + 10 * hr.FACTOR, :3].max(), 0.02, 'black outline')

    def test_semi_transparent_frame_keeps_its_opacity(self):
        img = disc(canvas(), 24, 24, 14, (0, 0, 0, 8 / 15))
        out, _ = hr.reconstruct_atlas(img)
        c = 24 * hr.FACTOR
        self.assertAlmostEqual(float(out[c, c, 3]), 8 / 15, places=2)

    def test_gradient_is_never_flattened(self):
        img = canvas()
        img[8:40, 8:40, 3] = 1
        img[8:40, 8:40, 0] = np.linspace(0, 1, 32)[None, :]
        img[8:40, 8:40, 2] = 0.5
        out, manifest = hr.reconstruct_atlas(img)
        self.assertNotEqual(manifest[0]['method'], 'flat')
        row = out[24 * hr.FACTOR, 12 * hr.FACTOR:36 * hr.FACTOR, 0]
        self.assertTrue(np.all(np.diff(row) > -0.02), 'still a smooth ramp')

    def test_output_is_deterministic(self):
        img = disc(canvas(), 20, 26, 11, (0.9, 0.3, 0.1, 1))
        a = hr.to_image(hr.reconstruct_atlas(img)[0])
        b = hr.to_image(hr.reconstruct_atlas(img)[0])
        self.assertEqual(hr.digest(a), hr.digest(b))


if __name__ == '__main__':
    unittest.main()
