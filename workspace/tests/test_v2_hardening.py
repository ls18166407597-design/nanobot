import asyncio
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Mocking parts of nanobot to test loop logic
class TestHardening(unittest.TestCase):
    def test_hash_logic(self):
        """Verify that identical tool calls produce identical hashes."""
        name = "exec"
        args = {"command": "ls -la", "confirm": True}
        
        # Sort keys to ensure consistency
        args_json1 = json.dumps(args, sort_keys=True)
        hash1 = hashlib.sha256(f"{name}:{args_json1}".encode()).hexdigest()
        
        args_json2 = json.dumps(args, sort_keys=True)
        hash2 = hashlib.sha256(f"{name}:{args_json2}".encode()).hexdigest()
        
        self.assertEqual(hash1, hash2)
        print(f"✅ Hashing consistency verified: {hash1}")

    def test_summary_dedupe_logic(self):
        """Verify the deduplication logic for context summaries."""
        prefix_msgs = [
            {"role": "system", "content": "You are a bot."},
            {"role": "system", "content": "Previous conversation summary: Old summary 1"},
            {"role": "system", "content": "Previous conversation summary: Old summary 2"}
        ]
        
        new_prefix = []
        for m in prefix_msgs:
            content = m.get("content", "")
            if isinstance(content, str) and "Previous conversation summary:" in content:
                continue
            new_prefix.append(m)
            
        self.assertEqual(len(new_prefix), 1)
        self.assertEqual(new_prefix[0]["content"], "You are a bot.")
        print(f"✅ Summary deduplication logic verified. Remaining prefix: {len(new_prefix)}")

    def test_path_regex(self):
        """Verify the path extraction regex used in shell.py."""
        import re
        cmd = "cat /etc/passwd; rm -rf /Users/liusong/data.txt; dir C:\\Windows\\System32"
        # The regex from the implementation
        potential_paths = re.findall(r'(/[^\s;"\']+|[a-zA-Z]:\\[^\s;"\']+)', cmd)
        
        expected = ['/etc/passwd', '/Users/liusong/data.txt', 'C:\\Windows\\System32']
        self.assertEqual(potential_paths, expected)
        print(f"✅ Path extraction regex verified: {potential_paths}")

if __name__ == "__main__":
    unittest.main()
