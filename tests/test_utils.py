import unittest
import os
import shutil
import json
from unittest.mock import patch

from utils.schema import safe_parse, get_api_key
from utils import cache

class TestUtils(unittest.TestCase):
    
    @patch.dict(os.environ, {"GEMINI_KEY_1": "key1", "GEMINI_KEY_2": "key2", "GEMINI_KEY_3": "key3"}, clear=True)
    def test_get_api_key_cycles_keys(self):
        # We need to reload the module to pick up the mocked env vars
        import importlib
        import utils.schema
        importlib.reload(utils.schema)
        
        self.assertEqual(utils.schema.get_api_key(), "key1")
        self.assertEqual(utils.schema.get_api_key(), "key2")
        self.assertEqual(utils.schema.get_api_key(), "key3")
        self.assertEqual(utils.schema.get_api_key(), "key1")
        
    def test_safe_parse_success(self):
        text = '{"key": "value", "num": 123}'
        result = safe_parse(text)
        self.assertEqual(result, {"key": "value", "num": 123})
        
    def test_safe_parse_failure(self):
        text = '{"key": "value", invalid json}'
        with self.assertRaises(ValueError):
            safe_parse(text)
            
    def test_safe_parse_required_keys_success(self):
        text = '{"key": "value", "num": 123}'
        result = safe_parse(text, required_keys=["key", "num"])
        self.assertEqual(result, {"key": "value", "num": 123})
        
    def test_safe_parse_required_keys_failure(self):
        text = '{"key": "value"}'
        with self.assertRaises(ValueError):
            safe_parse(text, required_keys=["key", "num"])
            
    def test_safe_parse_empty_dict(self):
        text = '{}'
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
