import os
import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CUSTOM_CRON = "0 3 */3 * * /usr/bin/ruantiblock update\n15 4 * * * /usr/bin/other update\n"
PACKAGE_MAKEFILES = (
    "ruantiblock/Makefile",
    "luci-app-ruantiblock/Makefile",
    "ruantiblock-mod-lua/Makefile",
    "ruantiblock-mod-py/Makefile",
)


class PackageHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.prefix = Path(self.temp.name)
        for directory in ("usr/bin", "etc/init.d", "etc/crontabs", "tmp"):
            (self.prefix / directory).mkdir(parents=True, exist_ok=True)

        self._write_executable(
            "usr/bin/ruantiblock",
            """#!/bin/sh
printf 'main:%s\\n' "$1" >> "$PREFIX/tmp/calls"
case "$1" in
    raw-status)
        cat "$PREFIX/tmp/running" 2>/dev/null || printf '2'
        ;;
    destroy)
        printf '0' > "$PREFIX/tmp/running"
        ;;
esac
""",
        )
        self._write_executable(
            "etc/init.d/ruantiblock",
            """#!/bin/sh
printf 'init:%s\\n' "$1" >> "$PREFIX/tmp/calls"
case "$1" in
    enabled)
        test "$(cat "$PREFIX/tmp/enabled" 2>/dev/null)" = 1
        ;;
    enable)
        printf '1' > "$PREFIX/tmp/enabled"
        ;;
    disable)
        printf '0' > "$PREFIX/tmp/enabled"
        ;;
    start)
        printf '1' > "$PREFIX/tmp/running"
        ;;
esac
""",
        )
        self._write_executable(
            "etc/init.d/cron",
            """#!/bin/sh
printf 'cron:%s\\n' "$1" >> "$PREFIX/tmp/calls"
""",
        )
        (self.prefix / "etc/crontabs/root").write_text(CUSTOM_CRON)
        (self.prefix / "tmp/enabled").write_text("1")
        (self.prefix / "tmp/running").write_text("0")

    def _write_executable(self, relative_path, content):
        path = self.prefix / relative_path
        path.write_text(content)
        path.chmod(0o755)

    def _hook(self, name):
        makefile = (ROOT / "ruantiblock/Makefile").read_text()
        match = re.search(
            rf"^define Package/\$\(PKG_NAME\)/{name}\n(.*?)^endef$",
            makefile,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match, f"missing {name} maintainer hook")
        body = match.group(1).replace("$$", "$")
        script = self.prefix / "tmp" / name
        script.write_text(body)
        script.chmod(0o755)
        if 'PREFIX="${PREFIX:-}"' not in body:
            self.fail(f"{name} must support PREFIX for isolated execution")
        return script

    def _run(self, hook, action):
        environment = os.environ.copy()
        environment["PREFIX"] = str(self.prefix)
        subprocess.run(
            ["sh", str(self._hook(hook)), action],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )

    def _calls(self):
        path = self.prefix / "tmp/calls"
        return path.read_text() if path.exists() else ""

    def _upgrade(self):
        self._run("preinst", "upgrade")
        self._run("prerm", "upgrade")
        self._run("postinst", "configure")

    def test_upgrade_preserves_enabled_running_service_and_custom_cron(self):
        self._upgrade()

        self.assertEqual((self.prefix / "tmp/enabled").read_text(), "1")
        self.assertEqual((self.prefix / "tmp/running").read_text(), "1")
        self.assertEqual((self.prefix / "etc/crontabs/root").read_text(), CUSTOM_CRON)
        self.assertNotIn("init:disable", self._calls())
        self.assertNotIn("cron:restart", self._calls())

    def test_upgrade_preserves_disabled_stopped_service(self):
        (self.prefix / "tmp/enabled").write_text("0")
        (self.prefix / "tmp/running").write_text("2")

        self._upgrade()

        self.assertEqual((self.prefix / "tmp/enabled").read_text(), "0")
        self.assertEqual((self.prefix / "tmp/running").read_text(), "0")
        self.assertNotIn("init:enable\n", self._calls())
        self.assertNotIn("init:start\n", self._calls())

    def test_upgrade_restarts_busy_service(self):
        (self.prefix / "tmp/running").write_text("3")

        self._upgrade()

        self.assertEqual((self.prefix / "tmp/running").read_text(), "1")

    def test_fresh_install_does_not_change_service_or_cron(self):
        (self.prefix / "tmp/enabled").write_text("0")
        (self.prefix / "tmp/ruantiblock.opkg-state").write_text("1\n1\n")

        self._run("preinst", "install")
        self._run("postinst", "configure")

        self.assertEqual((self.prefix / "tmp/enabled").read_text(), "0")
        self.assertEqual((self.prefix / "tmp/running").read_text(), "0")
        self.assertEqual((self.prefix / "etc/crontabs/root").read_text(), CUSTOM_CRON)
        self.assertFalse((self.prefix / "tmp/ruantiblock.opkg-state").exists())
        self.assertNotIn("init:enable", self._calls())
        self.assertNotIn("init:start", self._calls())

    def test_removal_cleans_service_and_only_ruantiblock_cron(self):
        self._run("prerm", "remove")

        self.assertEqual((self.prefix / "tmp/enabled").read_text(), "0")
        self.assertEqual((self.prefix / "tmp/running").read_text(), "0")
        self.assertEqual(
            (self.prefix / "etc/crontabs/root").read_text(),
            "15 4 * * * /usr/bin/other update\n",
        )
        self.assertIn("init:disable", self._calls())
        self.assertIn("cron:restart", self._calls())

    def test_removal_without_crontab_succeeds(self):
        (self.prefix / "etc/crontabs/root").unlink()

        self._run("prerm", "remove")

        self.assertIn("cron:restart", self._calls())


class PackageVersionTests(unittest.TestCase):
    def test_all_feed_packages_use_first_release_versions(self):
        for relative_path in PACKAGE_MAKEFILES:
            with self.subTest(makefile=relative_path):
                content = (ROOT / relative_path).read_text()
                version = re.search(r"^PKG_VERSION:=(.+)$", content, re.MULTILINE)
                release = re.search(r"^PKG_RELEASE:=(.+)$", content, re.MULTILINE)
                self.assertIsNotNone(version)
                self.assertIsNotNone(release)
                self.assertEqual(version.group(1), "2.2.0")
                self.assertEqual(release.group(1), "1")

    def test_release_validation_requires_all_four_package_versions(self):
        workflow = (ROOT / ".github/workflows/build-packages.yml").read_text()
        step = re.search(
            r"- name: Validate release versions\n.*?run: \|\n(.*?)(?=\n      - name:)",
            workflow,
            re.DOTALL,
        )
        self.assertIsNotNone(step)
        commands = textwrap.dedent(step.group(1))
        environment = os.environ.copy()
        environment.update(GITHUB_REF_TYPE="branch", GITHUB_REF_NAME="main")
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for relative_path in PACKAGE_MAKEFILES:
                makefile = directory / relative_path
                makefile.parent.mkdir(parents=True, exist_ok=True)
                version = "2.1.12" if relative_path == "ruantiblock-mod-lua/Makefile" else "2.2.0"
                makefile.write_text(f"PKG_VERSION:={version}\nPKG_RELEASE:=1\n")
            mismatched = subprocess.run(
                ["bash", "-e", "-o", "pipefail", "-c", commands],
                cwd=directory,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(mismatched.returncode, 0)
            for relative_path in PACKAGE_MAKEFILES:
                (directory / relative_path).write_text("PKG_VERSION:=2.2.0\nPKG_RELEASE:=1\n")
            matching = subprocess.run(
                ["bash", "-e", "-o", "pipefail", "-c", commands],
                cwd=directory,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(matching.returncode, 0, matching.stderr)


    def test_translation_version_matches_feed_release(self):
        content = (ROOT / "luci-app-ruantiblock/Makefile").read_text()
        po_version = re.search(r"^PKG_PO_VERSION:=(.+)$", content, re.MULTILINE)
        self.assertIsNotNone(po_version)
        self.assertEqual(po_version.group(1), "$(PKG_VERSION)-r$(PKG_RELEASE)")


if __name__ == "__main__":
    unittest.main()
