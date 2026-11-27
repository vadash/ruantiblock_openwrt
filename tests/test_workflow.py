import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SDK_NAME = "openwrt-sdk-24.10.0-rockchip-armv8_gcc-13.3.0_musl.Linux-x86_64.tar.zst"
SDK_HASH = "f61047b0edf02049d0a4c9df3192e682505d5f5e1fed33a3641db80f60232d18"


class WorkflowTests(unittest.TestCase):
    def test_sdk_metadata_parser_handles_binary_marker(self):
        workflow = (ROOT / ".github/workflows/build-packages.yml").read_text()
        step = re.search(
            r"- name: Download OpenWrt SDK\n.*?run: \|\n(.*?)(?=\n      - name:)",
            workflow,
            re.DOTALL,
        )
        self.assertIsNotNone(step)
        commands = textwrap.dedent(step.group(1))
        parser = "\n".join(
            line for line in commands.splitlines()
            if line.strip().startswith(("sdk_file=", "sdk_hash="))
        )
        self.assertIn("sdk_file=", parser)
        self.assertIn("sdk_hash=", parser)

        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "sha256sums").write_text(f"{SDK_HASH} *{SDK_NAME}\n")
            script = directory / "parse.sh"
            script.write_text(
                "set -eu\n"
                + parser
                + f"\ntest \"$sdk_file\" = {SDK_NAME}\n"
                + f"test \"$sdk_hash\" = {SDK_HASH}\n"
            )
            result = subprocess.run(
                ["bash", str(script)], cwd=directory, capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
