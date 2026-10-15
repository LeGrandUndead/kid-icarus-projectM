import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('native_ui_audit', Path(__file__).parents[1] / 'audit_native_ui.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class NativeUiCatalogTests(unittest.TestCase):
    def test_original_events_and_unresolved_links_are_preserved(self):
        original = {'bodyName_': 'Button', 'rightBodyName_': 'Unavailable',
                    'cursorSE_': 7, 'funcs_': {'Focus': [{'frame_': 12, '@class': 123}]}}
        data = {'menuID_': 'TEST', 'menuParams_': [{'params_': [original]}]}
        result = audit.describe(data)
        self.assertEqual(result['bodies'][0]['parameters'][0], original)
        self.assertEqual(result['unresolved_navigation'][0]['target'], 'Unavailable')
        self.assertEqual(result['sounds'][0]['value'], 7)
        self.assertFalse(result['runtime_state_verified'])
        self.assertFalse(result['actions_enabled'])

    def test_declared_navigation_and_multiple_dialogue_events(self):
        data = {'menuID_': 'TEST', 'menuParams_': [{'params_': [
            {'bodyName_': 'A', 'rightBodyName_': 'B'}, {'bodyName_': 'B'},
            {'talkList_': [{'talkFace_': 'expression_1', 'talkTimeEng_': 1.25},
                           {'talkFace_': 'expression_2', 'talkTimeEng_': 3.5}]}]}]}
        result = audit.describe(data)
        self.assertEqual(result['unresolved_navigation'], [])
        self.assertEqual([r['original']['talkTimeEng_'] for r in result['dialogue']], [1.25, 3.5])

    def test_unidentified_data_is_not_a_menu(self):
        with self.assertRaises(ValueError):
            audit.describe({'menuParams_': []})


if __name__ == '__main__':
    unittest.main()
