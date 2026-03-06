import unittest
import os
import shutil
import json
from unittest.mock import patch

from utils.schema import clean_json_response, safe_parse, get_api_key
from utils import cache

class TestUtils(unittest.TestCase):
    
    @patch.dict(os.environ, {"GEMINI_KEY_1": "key1", "GEMINI_KEY_2": "key2", "GEMINI_KEY_3": "key3"}, clear=True)
    def test_get_api_key_cycles_through_keys(self):
        # We need to reload the module to pick up the mocked env vars
        import importlib
        import utils.schema
        importlib.reload(utils.schema)
        
        self.assertEqual(utils.schema.get_api_key(), "key1")
        self.assertEqual(utils.schema.get_api_key(), "key2")
        self.assertEqual(utils.schema.get_api_key(), "key3")
        self.assertEqual(utils.schema.get_api_key(), "key1")
        
    def test_clean_json_response_plain_json(self):
        text = '{"key": "value"}'
        self.assertEqual(clean_json_response(text), '{"key": "value"}')
        
    def test_clean_json_response_fenced_json(self):
        text = '```json\n{"key": "value"}\n```'
        self.assertEqual(clean_json_response(text), '{"key": "value"}')
        
    def test_clean_json_response_fenced_plain(self):
        text = '```\n{"key": "value"}\n```'
        self.assertEqual(clean_json_response(text), '{"key": "value"}')
        
    def test_clean_json_response_whitespace(self):
        text = '   \n  {"key": "value"}  \n   '
        self.assertEqual(clean_json_response(text), '{"key": "value"}')
        
    def test_safe_parse_success(self):
        text = '```json\n{"key": "value", "num": 123}\n```'
        result = safe_parse(text)
        self.assertEqual(result, {"key": "value", "num": 123})
        
    def test_safe_parse_failure(self):
        text = '```json\n{"key": "value", invalid json}\n```'
        with self.assertRaises(ValueError):
            safe_parse(text)
            
    def test_cache_roundtrip(self):
        # Ensure cache dir is clean
        if os.path.exists("cache"):
            shutil.rmtree("cache")
            
        data = {"test": "data", "nested": {"a": 1}}
        cache.save("test_stage", data)
        
        # Verify directory was created
        self.assertTrue(os.path.exists("cache"))
        self.assertTrue(os.path.exists("cache/test_stage.json"))
        
        loaded = cache.load("test_stage")
        self.assertEqual(data, loaded)
        
    def test_cache_load_missing(self):
        self.assertIsNone(cache.load("non_existent_stage"))

if __name__ == "__main__":
    unittest.main()
