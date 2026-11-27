import os
import shutil
import subprocess
import time
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "ruantiblock/files/usr/bin/ruantiblock"
HELPER = ROOT / "ruantiblock/files/usr/libexec/ruantiblock/ruab_list_cache"
SHELL = shutil.which("sh")


class RuantiblockCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for directory in (
            "bin",
            "etc/config",
            "etc/init.d",
            "etc/ruantiblock/user_instances",
            "usr/bin",
            "usr/libexec/ruantiblock",
            "usr/share/ruantiblock",
            "var/ruantiblock",
            "var/dnsmasq.d",
            "var/run",
            "tmp",
        ):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        self.copy_runtime()
        self.write_commands()
        self.write_config()
        self.environment = os.environ.copy()
        self.environment.update(
            RUAB_ROOT=self.root.as_posix(),
            DATA_DIR=(self.root / "var/ruantiblock").as_posix(),
            DNSMASQ_CONFDIR=(self.root / "var/dnsmasq.d").as_posix(),
            PATH=(self.root / "bin").as_posix() + os.pathsep + self.environment["PATH"],
        )
        self.write_runtime("old")
        (self.root / "tmp/network.ip").write_text("new-main\n")
        (self.root / "tmp/network.dnsmasq").write_text("new-dns\n")

    @property
    def main(self):
        return self.root / "usr/bin/ruantiblock"

    @property
    def helper(self):
        return self.root / "usr/libexec/ruantiblock/ruab_list_cache"

    @property
    def cache(self):
        return self.root / "etc/ruantiblock/cache/lists.tar.gz"

    def copy_runtime(self):
        shutil.copy2(MAIN, self.main)
        shutil.copy2(HELPER, self.helper)
        for name in ("nft_functions", "user_instances_common", "info_output"):
            shutil.copy2(
                ROOT / "ruantiblock/files/usr/share/ruantiblock" / name,
                self.root / "usr/share/ruantiblock" / name,
            )
        (self.root / "usr/share/ruantiblock/blacklist_sources").write_text("")
        (self.root / "usr/libexec/ruantiblock/parser").write_text(
            """#!/bin/sh
printf 'parser staging=%s\\n' "$ENABLE_TMP_DOWNLOADS" >> "$RUAB_ROOT/tmp/parser.log"
$WGET_CMD https://example.invalid/list "$RUAB_ROOT/tmp/downloaded" || exit 1
[ ! -f "$RUAB_ROOT/tmp/parse_fail" ] || exit 1
cp "$RUAB_ROOT/tmp/network.ip" "$IP_DATA_FILE"
cp "$RUAB_ROOT/tmp/network.dnsmasq" "$DNSMASQ_DATA_FILE"
printf '7 8 9' > "$UPDATE_STATUS_FILE"
"""
        )
        (self.root / "usr/libexec/ruantiblock/ruab_parser_user_entries").write_text(
            """#!/bin/sh
: > "$I_IP_DATA_FILE"
: > "$I_DNSMASQ_DATA_FILE"
printf '0 0 0 local\\n' > "$I_USER_ENTRIES_STATUS_FILE"
"""
        )
        for path in (
            self.main,
            self.helper,
            self.root / "usr/libexec/ruantiblock/parser",
            self.root / "usr/libexec/ruantiblock/ruab_parser_user_entries",
        ):
            path.chmod(0o755)

    def write_commands(self):
        commands = {
            "nft": """#!/bin/sh
printf 'nft %s\\n' "$*" >> "$RUAB_ROOT/tmp/nft.log"
case "$1" in
    -c)
        [ -f "$RUAB_ROOT/tmp/nft_running" ]
        exit $?
    ;;
    -f)
        cat "$2" >> "$RUAB_ROOT/tmp/applied"
        if [ -f "$RUAB_ROOT/tmp/nft_fail" ]; then
            case "$2" in
                *ruantiblock.ip*)
                    rm -f "$RUAB_ROOT/tmp/nft_fail"
                    exit 1
                ;;
            esac
        fi
    ;;
    add)
        if [ "$2" = "table" ]; then
            : > "$RUAB_ROOT/tmp/nft_running"
        fi
    ;;
esac
exit 0
""",
            "ip": "#!/bin/sh\n[ \"$1 $2\" = \"-4 addr\" ] && printf '    inet 192.0.2.1/24 scope global eth0\\n'\nexit 0\n",
            "wget": """#!/bin/sh
printf 'wget %s\\n' "$*" >> "$RUAB_ROOT/tmp/wget.log"
[ ! -f "$RUAB_ROOT/tmp/download_fail" ] || exit 1
while [ $# -gt 0 ]; do
    if [ "$1" = "-O" ]; then
        printf 'downloaded\\n' > "$2"
        exit 0
    fi
    shift
done
exit 0
""",
            "logger": '#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$RUAB_ROOT/tmp/logger.log"\n',
            "nslookup": "#!/bin/sh\nexit 0\n",
        }
        for name, content in commands.items():
            path = self.root / "bin" / name
            path.write_text(content)
            path.chmod(0o755)
        dnsmasq = self.root / "etc/init.d/dnsmasq"
        dnsmasq.write_text('#!/bin/sh\nprintf "dnsmasq %s\\n" "$*" >> "$RUAB_ROOT/tmp/dnsmasq.log"\n')
        dnsmasq.chmod(0o755)

    def write_config(self):
        (self.root / "etc/config/ruantiblock").write_text("config ruantiblock 'config'\n")
        (self.root / "etc/ruantiblock/bypass_entries").write_text("allowed.example\n192.0.2.10\n")
        (self.root / "etc/ruantiblock/ruantiblock.conf").write_text(
            f'''DATA_DIR="{self.root.as_posix()}/var/ruantiblock"
MODULES_DIR="{self.root.as_posix()}/usr/libexec/ruantiblock"
RUN_FILES_DIR="{self.root.as_posix()}/var/run"
DNSMASQ_CONFDIR="{self.root.as_posix()}/var/dnsmasq.d"
DNSMASQ_RESTART_CMD="{self.root.as_posix()}/etc/init.d/dnsmasq restart"
HTML_DIR="{self.root.as_posix()}/www"
ENABLE_LOGGING=1
DEBUG=0
ENABLE_HTML_INFO=0
BLLIST_PRESET=test
BLLIST_MODULE="{self.root.as_posix()}/usr/libexec/ruantiblock/parser"
MODULE_RUN_ATTEMPTS=1
MODULE_RUN_TIMEOUT=0
USER_INSTANCES_MAX=5
NFTSET_CLEAR_SETS=0
VPN_ROUTE_CHECK=0
'''
        )

    def write_runtime(self, marker):
        payload = {
            "ruantiblock.ip": f"{marker}-main\n",
            "ruantiblock_bypass.ip": f"{marker}-bypass\n",
            "ruantiblock_user_instances.ip": f"{marker}-user\n",
            "update_status": f"1 2 3 {marker}-timestamp\n",
            "user_entries_status": f"4 5 6 {marker}-local\n",
        }
        for name, content in payload.items():
            (self.root / "var/ruantiblock" / name).write_text(content)
        dnsmasq = {
            "00-ruantiblock_bypass.dnsmasq": f"{marker}-bypass-dns\n",
            "01-ruantiblock_user_instances.dnsmasq": f"{marker}-user-dns\n",
            "02-ruantiblock.dnsmasq": f"{marker}-dns\n",
        }
        for name, content in dnsmasq.items():
            (self.root / "var/dnsmasq.d" / name).write_text(content)

    def runtime(self, name):
        directory = "var/dnsmasq.d" if name.endswith(".dnsmasq") else "var/ruantiblock"
        return self.root / directory / name

    def log(self, name):
        path = self.root / "tmp" / name
        return path.read_text() if path.exists() else ""

    def logged_events(self, priority):
        marker = f"-p user.{priority} "
        return [
            line.split(marker, 1)[1]
            for line in self.log("logger.log").splitlines()
            if marker in line
        ]

    def run_helper(self, operation):
        return subprocess.run(
            [SHELL, str(self.helper), operation],
            env=self.environment,
            capture_output=True,
            text=True,
        )

    def run_cli(self, action, setup=""):
        script = setup + '''
which() {
    case "$1" in
        nft|wget|nslookup|ip|logger|uci) printf '%s/bin/%s\\n' "$RUAB_ROOT" "$1" ;;
        *) command which "$1" ;;
    esac
}
APP="$0"
ACTION="$1"
shift
. "$APP" "$ACTION" "$@"
'''
        return subprocess.run(
            [SHELL, "-c", script, str(self.main), action],
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_start_restores_and_applies_snapshot_without_network_download(self):
        self.assertEqual(self.run_helper("save").returncode, 0)
        self.write_runtime("volatile")
        (self.root / "tmp/nft_running").unlink(missing_ok=True)
        (self.root / "var/run/ruantiblock_start.pid").unlink(missing_ok=True)
        (self.root / "var/run/ruantiblock.instances").unlink(missing_ok=True)

        started = self.run_cli("start")

        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertEqual(self.runtime("ruantiblock.ip").read_text(), "old-main\n")
        self.assertEqual(self.runtime("update_status").read_text(), "1 2 3 old-timestamp\n")
        self.assertIn("old-main", self.log("applied"))
        self.assertEqual(self.logged_events("notice"), ["blacklist restored from cache"])
        self.assertEqual(self.log("parser.log"), "")
        self.assertEqual(self.log("wget.log"), "")

    def test_update_always_downloads_and_fresh_cache_only_skips_write(self):
        (self.root / "tmp/nft_running").write_text("")

        first = self.run_cli("update")

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue(self.cache.is_file())
        self.assertEqual(self.runtime("ruantiblock.ip").read_text(), "new-main\n")
        original = self.cache.read_bytes()
        original_mtime = self.cache.stat().st_mtime_ns
        (self.root / "tmp/network.ip").write_text("newer-main\n")

        second = self.run_cli("update")

        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.log("wget.log").count("wget "), 2)
        self.assertEqual(self.runtime("ruantiblock.ip").read_text(), "newer-main\n")
        self.assertEqual(self.cache.read_bytes(), original)
        self.assertEqual(self.cache.stat().st_mtime_ns, original_mtime)
        self.assertEqual(self.logged_events("notice").count("blacklist updated from network"), 2)
        self.assertEqual(self.logged_events("info").count("list cache updated"), 1)
        self.assertNotIn("update: network update", self.logged_events("notice"))
        self.assertNotIn("list cache write skipped", self.log("logger.log"))

    def test_failed_download_restores_old_cache_and_preserves_failure_status(self):
        (self.root / "tmp/nft_running").write_text("")
        self.assertEqual(self.run_cli("update").returncode, 0)
        cached_status = self.runtime("update_status").read_text()
        old_time = time.time() - 8 * 86400
        os.utime(self.cache, (old_time, old_time))
        (self.root / "tmp/download_fail").write_text("")

        failed = self.run_cli("update")

        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(self.runtime("ruantiblock.ip").read_text(), "new-main\n")
        self.assertEqual(self.runtime("update_status").read_text(), cached_status)
        self.assertEqual(self.cache.stat().st_mtime, old_time)
        self.assertEqual(self.logged_events("notice").count("blacklist update failed; using cache"), 1)
        self.assertNotIn("blacklist restored from cache", self.logged_events("notice"))
        self.assertEqual(self.logged_events("notice").count("blacklist updated from network"), 1)
        self.assertIn("staging=1", self.log("parser.log"))


    def test_nftables_failure_restores_cache_and_reapplies_it(self):
        (self.root / "tmp/nft_running").write_text("")
        self.assertEqual(self.run_cli("update").returncode, 0)
        original = self.cache.read_bytes()
        (self.root / "tmp/network.ip").write_text("unapplied-main\n")
        (self.root / "tmp/nft_fail").write_text("")

        failed = self.run_cli("update")

        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(self.runtime("ruantiblock.ip").read_text(), "new-main\n")
        self.assertEqual(self.cache.read_bytes(), original)
        applied = self.log("applied")
        self.assertIn("unapplied-main", applied)
        self.assertGreater(applied.rfind("new-main"), applied.find("unapplied-main"))
        self.assertEqual(self.logged_events("notice").count("blacklist update failed; using cache"), 1)
        self.assertNotIn("blacklist restored from cache", self.logged_events("notice"))

    def test_first_failed_update_without_cache_preserves_all_runtime_files(self):
        (self.root / "tmp/nft_running").write_text("")
        names = (
            "ruantiblock.ip",
            "ruantiblock_bypass.ip",
            "ruantiblock_user_instances.ip",
            "00-ruantiblock_bypass.dnsmasq",
            "01-ruantiblock_user_instances.dnsmasq",
            "02-ruantiblock.dnsmasq",
            "update_status",
            "user_entries_status",
        )
        before = {name: self.runtime(name).read_bytes() for name in names}
        (self.root / "tmp/download_fail").write_text("")

        failed = self.run_cli("update")

        self.assertNotEqual(failed.returncode, 0)
        self.assertFalse(self.cache.exists())
        self.assertEqual({name: self.runtime(name).read_bytes() for name in names}, before)
        self.assertIn("old-main", self.log("applied"))
        self.assertIn("blacklist update failed; using runtime lists", self.logged_events("notice"))

    def test_partial_promotion_failure_rolls_back_without_cache(self):
        (self.root / "tmp/nft_running").write_text("")
        names = (
            "ruantiblock.ip",
            "ruantiblock_bypass.ip",
            "ruantiblock_user_instances.ip",
            "00-ruantiblock_bypass.dnsmasq",
            "01-ruantiblock_user_instances.dnsmasq",
            "02-ruantiblock.dnsmasq",
            "update_status",
            "user_entries_status",
        )
        before = {name: self.runtime(name).read_bytes() for name in names}
        setup = '''
mv() {
    if [ "$1" = "-f" ] && [ "$2" = "$RUAB_ROOT/var/ruantiblock/ruantiblock_user_instances.ip.tmp" ] && [ ! -e "$RUAB_ROOT/tmp/mv_failed" ]; then
        : > "$RUAB_ROOT/tmp/mv_failed"
        return 1
    fi
    command mv "$@"
}
'''

        failed = self.run_cli("update", setup)

        self.assertNotEqual(failed.returncode, 0)
        self.assertFalse(self.cache.exists())
        self.assertEqual({name: self.runtime(name).read_bytes() for name in names}, before)
        self.assertIn("blacklist update failed; using runtime lists", self.logged_events("notice"))

    def test_first_nftables_failure_without_runtime_lists_clears_partial_sets(self):
        (self.root / "tmp/nft_running").write_text("")
        for name in ("ruantiblock.ip", "ruantiblock_bypass.ip", "ruantiblock_user_instances.ip"):
            self.runtime(name).unlink()
        (self.root / "tmp/nft_fail").write_text("")

        failed = self.run_cli("update")

        self.assertNotEqual(failed.returncode, 0)
        self.assertFalse(self.runtime("ruantiblock.ip").exists())
        self.assertGreaterEqual(self.log("nft.log").count("flush set"), 2)
        self.assertIn("blacklist update failed; using runtime lists", self.logged_events("notice"))

    def test_parse_failure_restores_cache_without_promoting_partial_lists(self):
        (self.root / "tmp/nft_running").write_text("")
        self.assertEqual(self.run_cli("update").returncode, 0)
        (self.root / "tmp/network.ip").write_text("partial-main\n")
        (self.root / "tmp/parse_fail").write_text("")

        failed = self.run_cli("update")

        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(self.runtime("ruantiblock.ip").read_text(), "new-main\n")
        self.assertNotIn("partial-main", self.log("applied"))
        self.assertEqual(self.logged_events("notice").count("blacklist update failed; using cache"), 1)
        self.assertNotIn("blacklist restored from cache", self.logged_events("notice"))

    def test_unwritable_cache_does_not_fail_successful_network_update(self):
        (self.root / "tmp/nft_running").write_text("")
        self.cache.parent.mkdir(parents=True)
        self.cache.mkdir()

        updated = self.run_cli("update")

        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertIn("Warning:", updated.stderr)
        self.assertEqual(self.runtime("ruantiblock.ip").read_text(), "new-main\n")
        self.assertTrue(self.cache.is_dir())
        self.assertEqual(self.logged_events("notice").count("blacklist updated from network"), 1)
        self.assertNotIn("list cache updated", self.logged_events("info"))
        self.assertEqual(self.logged_events("warning"), ["list cache update failed"])

    def test_corrupt_cache_warns_at_start_and_successful_update_replaces_it(self):
        self.assertEqual(self.run_helper("save").returncode, 0)
        self.cache.write_bytes(b"corrupt")
        (self.root / "tmp/nft_running").unlink(missing_ok=True)

        started = self.run_cli("start")

        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertIn("corrupt", started.stderr.lower())
        self.assertEqual(self.runtime("ruantiblock.ip").read_text(), "old-main\n")
        self.assertNotIn("blacklist restored from cache", self.logged_events("notice"))
        self.assertEqual(self.logged_events("warning"), ["list snapshot unavailable; using runtime lists"])

        updated = self.run_cli("update")

        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertEqual(self.cache.read_bytes()[:2], b"\x1f\x8b")
        self.assertEqual(self.run_helper("restore").returncode, 0)
        self.assertEqual(self.logged_events("notice").count("blacklist updated from network"), 1)
        self.assertEqual(self.logged_events("info").count("list cache updated"), 1)

    def test_old_cache_never_suppresses_network_update_and_is_replaced(self):
        (self.root / "tmp/nft_running").write_text("")
        self.assertEqual(self.run_cli("update").returncode, 0)
        old_time = time.time() - 604800
        os.utime(self.cache, (old_time, old_time))
        (self.root / "tmp/network.ip").write_text("old-cache-new-network\n")

        updated = self.run_cli("update")

        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertEqual(self.log("wget.log").count("wget "), 2)
        self.assertGreater(self.cache.stat().st_mtime, old_time)
        self.assertEqual(self.runtime("ruantiblock.ip").read_text(), "old-cache-new-network\n")
        self.runtime("ruantiblock.ip").write_text("discard\n")
        self.assertEqual(self.run_helper("restore").returncode, 0)
        self.assertEqual(self.runtime("ruantiblock.ip").read_text(), "old-cache-new-network\n")
        self.assertEqual(self.logged_events("info").count("list cache updated"), 2)

    def test_force_update_forces_staging_despite_legacy_option(self):
        (self.root / "tmp/nft_running").write_text("")

        updated = self.run_cli("force-update")

        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertIn("staging=1", self.log("parser.log"))
        self.assertIn("ruantiblock.ip.tmp", self.log("nft.log"))
        self.assertFalse(self.runtime("ruantiblock.ip.tmp").exists())
        self.assertFalse(self.runtime("02-ruantiblock.dnsmasq.tmp").exists())
        self.assertEqual(self.logged_events("notice").count("blacklist updated from network"), 1)
        self.assertEqual(self.logged_events("info").count("list cache updated"), 1)

    def test_changed_inputs_replace_fresh_cache_after_successful_update(self):
        (self.root / "tmp/nft_running").write_text("")
        self.assertEqual(self.run_cli("update").returncode, 0)
        original = self.cache.read_bytes()
        config = self.root / "etc/ruantiblock/ruantiblock.conf"
        config.write_text(config.read_text() + "BLLIST_MIN_ENTRIES=1\n")
        (self.root / "tmp/network.ip").write_text("changed-input-main\n")

        updated = self.run_cli("update")

        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertNotEqual(self.cache.read_bytes(), original)
        self.runtime("ruantiblock.ip").write_text("discard\n")
        self.assertEqual(self.run_helper("restore").returncode, 0)
        self.assertEqual(self.runtime("ruantiblock.ip").read_text(), "changed-input-main\n")
        self.assertEqual(self.logged_events("info").count("list cache updated"), 2)

    def test_failed_update_does_not_restore_incompatible_cache(self):
        (self.root / "tmp/nft_running").write_text("")
        self.assertEqual(self.run_cli("update").returncode, 0)
        before = {name: self.runtime(name).read_bytes() for name in (
            "ruantiblock.ip",
            "ruantiblock_bypass.ip",
            "ruantiblock_user_instances.ip",
            "02-ruantiblock.dnsmasq",
            "update_status",
        )}
        config = self.root / "etc/ruantiblock/ruantiblock.conf"
        config.write_text(config.read_text() + "BLLIST_MIN_ENTRIES=1\n")
        (self.root / "tmp/download_fail").write_text("")

        failed = self.run_cli("update")

        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("incompatible", failed.stderr.lower())
        self.assertEqual({name: self.runtime(name).read_bytes() for name in before}, before)
        self.assertIn("blacklist update failed; using runtime lists", self.logged_events("notice"))

    def test_missing_cache_startup_uses_runtime_without_warning(self):
        (self.root / "tmp/nft_running").unlink(missing_ok=True)

        started = self.run_cli("start")

        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertNotIn("warning", started.stderr.lower())
        self.assertEqual(self.runtime("ruantiblock.ip").read_text(), "old-main\n")
        self.assertIn("old-main", self.log("applied"))
        self.assertEqual(self.logged_events("notice"), [])
        self.assertEqual(self.logged_events("warning"), [])




if __name__ == "__main__":
    unittest.main()
