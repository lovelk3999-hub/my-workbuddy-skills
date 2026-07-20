import importlib.util
from pathlib import Path
import unittest


def load_haimgr():
    path = Path(__file__).resolve().parents[1] / "scripts" / "haimgr.py"
    spec = importlib.util.spec_from_file_location("haimgr_security_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HaimgrSecurityTests(unittest.TestCase):
    def test_public_video_rule_indexes_selects_only_public_6888_and_6889_rules(self):
        module = load_haimgr()
        ingress = [
            {"PolicyIndex": 1, "Port": "6888", "CidrBlock": "0.0.0.0/0", "Ipv6CidrBlock": ""},
            {"PolicyIndex": 2, "Port": "6889", "CidrBlock": "", "Ipv6CidrBlock": "::/0"},
            {"PolicyIndex": 3, "Port": "6889", "CidrBlock": "127.0.0.1/32", "Ipv6CidrBlock": ""},
            {"PolicyIndex": 4, "Port": "22", "CidrBlock": "0.0.0.0/0", "Ipv6CidrBlock": ""},
        ]

        self.assertEqual(module.public_video_rule_indexes(ingress), [1, 2])

    def test_video_access_cidrs_keeps_tencent_and_http_egress_sources(self):
        module = load_haimgr()

        cidrs = module.video_access_cidrs(lambda: "156.229.162.251")

        self.assertEqual(cidrs, ["156.229.162.251/32", "MY_PUBLIC_IP"])


if __name__ == "__main__":
    unittest.main()
