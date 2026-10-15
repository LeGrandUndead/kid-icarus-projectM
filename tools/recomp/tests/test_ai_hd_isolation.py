import os, sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from launch_ai_hd import configuration,validate_art_policy

class Isolation(unittest.TestCase):
    def test_unknown_capture_requires_art_review(self):
        with patch.object(Path,'read_text',return_value='{"original_only":[],"approved_for_ai":[]}'), \
             patch.object(Path,'glob',return_value=[Path('new-portrait.png')]):
            with self.assertRaisesRegex(ValueError,'Unreviewed'):
                validate_art_policy(Path('isolated-edition'))

    def test_rejects_a_character_replacement_even_if_pack_manifest_omits_it(self):
        # The renderer discovers PNG files directly, so checking only the
        # manifest would let a leftover portrait replacement slip through.
        with patch.object(Path,'read_text',return_value='{"original_only":["portrait.png"]}'), \
             patch.object(Path,'exists',return_value=True):
            with self.assertRaisesRegex(ValueError,'must remain original'):
                validate_art_policy(Path('isolated-edition'))

    def test_paths_and_inherited_overrides_stay_isolated(self):
        root=Path(__file__).resolve().parents[3]/'build/ai-hd-edition'
        with patch.dict(os.environ,{'KIU_TEXTURE_PACK':'outside', 'ZAKURO_REPLAY':'outside',
                                     'KIU_TEXTURE_FILTER':'cubic', 'KIU_INPUT_TRACE':'outside'}):
            command,env=configuration(root)
        for variable in ['APPDATA','LOCALAPPDATA','KIU_TEXTURE_PACK']:
            self.assertTrue(Path(env[variable]).is_relative_to(root))
        for variable in ['ZAKURO_REPLAY','KIU_TEXTURE_FILTER','KIU_INPUT_TRACE']:
            self.assertNotIn(variable,env)
        for index in [0,1,3,5]:
            self.assertTrue(Path(command[index]).is_relative_to(root))

if __name__=='__main__': unittest.main()
