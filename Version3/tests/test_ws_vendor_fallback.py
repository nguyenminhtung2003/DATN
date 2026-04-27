import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import network.ws_client as ws_client


class WebSocketVendorFallbackTest(unittest.TestCase):
    def test_import_websocket_module_uses_vendor_path_after_primary_import_failure(self):
        sentinel = object()
        calls = []
        original_sys_path = list(sys.path)

        def fake_import(name):
            calls.append((name, list(sys.path)))
            websocket_calls = [entry for entry in calls if entry[0] == "websocket"]
            if len(websocket_calls) == 1:
                raise ImportError("missing system websocket")
            return sentinel

        vendor_dir = str(Path("D:/vendor/websocket"))
        with patch("network.ws_client.importlib.import_module", side_effect=fake_import):
            module = ws_client._import_websocket_module(vendor_dir=vendor_dir)

        self.assertIs(module, sentinel)
        self.assertEqual([name for name, _ in calls], ["websocket", "websocket"])
        self.assertEqual(sys.path[0], vendor_dir)
        sys.path[:] = original_sys_path


if __name__ == "__main__":
    unittest.main()
