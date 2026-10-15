import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_original_art_pack import reconstruct


class OriginalArtTests(unittest.TestCase):
    def test_hidden_transparent_color_cannot_contaminate_visible_art(self):
        pixels = np.zeros((8, 8, 4), dtype=np.uint8)
        pixels[:, :, 2] = 255  # Blue junk behind transparent pixels.
        pixels[2:6, 2:6] = [255, 0, 0, 255]
        result = np.asarray(reconstruct(Image.fromarray(pixels), 4))
        self.assertEqual(result.shape, (32, 32, 4))
        visible = result[:, :, 3] > 0
        self.assertTrue(np.all(result[:, :, 0][visible] == 255))
        self.assertTrue(np.all(result[:, :, 1:3][visible] == 0))

    def test_flat_color_and_opacity_are_preserved(self):
        image = Image.new('RGBA', (8, 4), (93, 174, 28, 128))
        result = np.asarray(reconstruct(image, 4))
        self.assertTrue(np.all(result == [93, 174, 28, 128]))


if __name__ == '__main__':
    unittest.main()
