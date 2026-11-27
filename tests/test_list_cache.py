import os
import subprocess
import shutil
import time
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

SHELL = shutil.which("sh")
ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "ruantiblock/files/usr/libexec/ruantiblock/ruab_list_cache"


class ListCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for directory in (
            "etc/config",
            "etc/ruantiblock",
            "usr/bin",
            "usr/libexec/ruantiblock",
            "var/ruantiblock",
            "var/dnsmasq.d",
            "tmp",
        ):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / "etc/config/ruantiblock").write_text("config ruantiblock 'config'\n")
        (self.root / "etc/ruantiblock/ruantiblock.conf").write_text("PROXY_MODE=1\n")
        (self.root / "usr/bin/ruantiblock").write_text("#!/bin/sh\n")
        (self.root / "usr/libexec/ruantiblock/parser").write_text("#!/bin/sh\n")
        self.environment = os.environ.copy()
        self.environment.update(
            RUAB_ROOT=self.root.as_posix(),
            DATA_DIR=(self.root / "var/ruantiblock").as_posix(),
            DNSMASQ_CONFDIR=(self.root / "var/dnsmasq.d").as_posix(),
        )
        self.payload = {
            "ruantiblock.ip": "main ip\n",
            "ruantiblock_bypass.ip": "bypass ip\n",
            "ruantiblock_user_instances.ip": "user ip\n",
            "update_status": "1 2 3 01.02.2024-03:04\n",
            "user_entries_status": "4 5 6 local\n",
        }
        self.dnsmasq = {
            "00-ruantiblock_bypass.dnsmasq": "bypass dns\n",
            "01-ruantiblock_user_instances.dnsmasq": "user dns\n",
            "02-ruantiblock.dnsmasq": "main dns\n",
        }
        self.write_payload(self.payload, self.dnsmasq)

    @property
    def cache(self):
        return self.root / "etc/ruantiblock/cache/lists.tar.gz"

    def write_payload(self, payload, dnsmasq):
        for name, content in payload.items():
            (self.root / "var/ruantiblock" / name).write_text(content)
        for name, content in dnsmasq.items():
            (self.root / "var/dnsmasq.d" / name).write_text(content)

    def run_cache(self, operation, environment=None):
        self.assertIsNotNone(SHELL, "POSIX shell required")
        return subprocess.run(
            [SHELL, str(HELPER), operation],
            env=environment or self.environment,
            capture_output=True,
            text=True,
        )

    def test_save_and_restore_round_trip_all_lists_and_original_status(self):
        saved = self.run_cache("save")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertTrue(self.cache.is_file())

        self.write_payload(
            {name: "changed\n" for name in self.payload},
            {name: "changed\n" for name in self.dnsmasq},
        )
        restored = self.run_cache("restore")
        self.assertEqual(restored.returncode, 0, restored.stderr)

        for name, content in self.payload.items():
            self.assertEqual((self.root / "var/ruantiblock" / name).read_text(), content)
        for name, content in self.dnsmasq.items():
            self.assertEqual((self.root / "var/dnsmasq.d" / name).read_text(), content)



    def test_fresh_matching_cache_suppresses_only_persistent_write(self):
        self.assertEqual(self.run_cache("save").returncode, 0)
        original = self.cache.read_bytes()
        original_mtime = self.cache.stat().st_mtime_ns
        (self.root / "var/ruantiblock/ruantiblock.ip").write_text("fresh network list\n")

        saved = self.run_cache("save")

        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertEqual(self.cache.read_bytes(), original)
        self.assertEqual(self.cache.stat().st_mtime_ns, original_mtime)
        self.assertEqual(
            (self.root / "var/ruantiblock/ruantiblock.ip").read_text(),
            "fresh network list\n",
        )

    def test_save_reports_actual_write_or_fresh_cache_skip(self):
        first = self.run_cache("save")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, "updated\n")

        second = self.run_cache("save")

        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(second.stdout, "unchanged\n")

    def test_seven_day_old_cache_is_replaced_at_boundary(self):
        self.assertEqual(self.run_cache("save").returncode, 0)
        old_time = time.time() - 604800
        os.utime(self.cache, (old_time, old_time))
        (self.root / "var/ruantiblock/ruantiblock.ip").write_text("seven day list\n")

        saved = self.run_cache("save")

        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertGreater(self.cache.stat().st_mtime, old_time)
        (self.root / "var/ruantiblock/ruantiblock.ip").write_text("discard me\n")
        self.assertEqual(self.run_cache("restore").returncode, 0)
        self.assertEqual(
            (self.root / "var/ruantiblock/ruantiblock.ip").read_text(),
            "seven day list\n",
        )



    def test_future_cache_timestamp_forces_replacement(self):
        self.assertEqual(self.run_cache("save").returncode, 0)
        future = time.time() + 3600
        os.utime(self.cache, (future, future))
        (self.root / "var/ruantiblock/ruantiblock.ip").write_text("future clock list\n")

        saved = self.run_cache("save")

        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertLessEqual(self.cache.stat().st_mtime, time.time())
        (self.root / "var/ruantiblock/ruantiblock.ip").write_text("discard me\n")
        self.assertEqual(self.run_cache("restore").returncode, 0)
        self.assertEqual(
            (self.root / "var/ruantiblock/ruantiblock.ip").read_text(),
            "future clock list\n",
        )

    def test_changed_inputs_replace_fresh_cache(self):
        self.assertEqual(self.run_cache("save").returncode, 0)
        original = self.cache.read_bytes()
        (self.root / "etc/ruantiblock/ruantiblock.conf").write_text("PROXY_MODE=2\n")
        (self.root / "var/ruantiblock/ruantiblock.ip").write_text("new inputs list\n")

        saved = self.run_cache("save")

        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertNotEqual(self.cache.read_bytes(), original)
        (self.root / "var/ruantiblock/ruantiblock.ip").write_text("discard me\n")
        restored = self.run_cache("restore")
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(
            (self.root / "var/ruantiblock/ruantiblock.ip").read_text(),
            "new inputs list\n",
        )


    def test_corrupt_cache_warns_without_overwriting_runtime_and_is_replaced(self):
        self.assertEqual(self.run_cache("save").returncode, 0)
        self.cache.write_bytes(b"not a gzip archive")
        runtime = self.root / "var/ruantiblock/ruantiblock.ip"
        runtime.write_text("last working list\n")

        restored = self.run_cache("restore")

        self.assertNotEqual(restored.returncode, 0)
        self.assertIn("corrupt", restored.stderr)
        self.assertEqual(runtime.read_text(), "last working list\n")
        saved = self.run_cache("save")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        runtime.write_text("discard me\n")
        self.assertEqual(self.run_cache("restore").returncode, 0)
        self.assertEqual(runtime.read_text(), "last working list\n")


    def test_incompatible_cache_warns_and_leaves_runtime_until_successful_save(self):
        self.assertEqual(self.run_cache("save").returncode, 0)
        (self.root / "etc/ruantiblock/ruantiblock.conf").write_text("PROXY_MODE=3\n")
        runtime = self.root / "var/ruantiblock/ruantiblock.ip"
        runtime.write_text("current runtime list\n")

        restored = self.run_cache("restore")

        self.assertNotEqual(restored.returncode, 0)
        self.assertIn("incompatible", restored.stderr)
        self.assertEqual(runtime.read_text(), "current runtime list\n")
        self.assertEqual(self.run_cache("save").returncode, 0)
        runtime.write_text("discard me\n")
        self.assertEqual(self.run_cache("restore").returncode, 0)
        self.assertEqual(runtime.read_text(), "current runtime list\n")


    def test_missing_cache_is_normal_and_preserves_runtime(self):
        runtime = self.root / "var/ruantiblock/ruantiblock.ip"

        restored = self.run_cache("restore")

        self.assertNotEqual(restored.returncode, 0)
        self.assertEqual(restored.stderr, "")
        self.assertEqual(runtime.read_text(), "main ip\n")


    def test_capture_returns_verified_archive_with_all_processed_files(self):
        captured = self.run_cache("capture")
        self.assertEqual(captured.returncode, 0, captured.stderr)
        archive_path = self.root / "capture.tar.gz"
        copied = subprocess.run(
            [SHELL, "-c", 'mv "$1" "$2"', "sh", captured.stdout.strip(), archive_path.as_posix()],
            env=self.environment,
            capture_output=True,
            text=True,
        )
        self.assertEqual(copied.returncode, 0, copied.stderr)

        with tarfile.open(archive_path, "r:gz") as archive:
            self.assertEqual(
                set(archive.getnames()),
                {
                    "manifest",
                    "data/ruantiblock.ip",
                    "data/ruantiblock_bypass.ip",
                    "data/ruantiblock_user_instances.ip",
                    "dnsmasq/00-ruantiblock_bypass.dnsmasq",
                    "dnsmasq/01-ruantiblock_user_instances.dnsmasq",
                    "dnsmasq/02-ruantiblock.dnsmasq",
                    "status/update_status",
                    "status/user_entries_status",
                },
            )
            status = archive.extractfile("status/update_status").read().decode().splitlines()[0]
            self.assertEqual(status, "1 2 3 01.02.2024-03:04")


    def test_failed_archive_write_preserves_previous_cache(self):
        self.assertEqual(self.run_cache("save").returncode, 0)
        original = self.cache.read_bytes()
        environment = self.environment.copy()
        saved = subprocess.run(
            [SHELL, "-c", 'tar() { exit 1; }; HELPER="$1"; ACTION="$2"; set -- "$ACTION"; . "$HELPER"', "sh", str(HELPER), "save"],
            env=environment,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(saved.returncode, 0)
        self.assertIn("Warning:", saved.stderr)
        self.assertEqual(self.cache.read_bytes(), original)

    def test_readable_incomplete_archive_is_not_published(self):
        self.assertEqual(self.run_cache("save").returncode, 0)
        original = self.cache.read_bytes()
        (self.root / "etc/ruantiblock/ruantiblock.conf").write_text("PROXY_MODE=2\n")
        script = '''
tar() {
    case " $* " in
        *" -czf "*)
            while [ $# -gt 0 ]; do
                if [ "$1" = "-czf" ]; then
                    command tar -czf "$2" --files-from /dev/null
                    return $?
                fi
                shift
            done
        ;;
        *) command tar "$@" ;;
    esac
}
HELPER="$1"
set -- save
. "$HELPER"
'''
        saved = subprocess.run(
            [SHELL, "-c", script, "sh", str(HELPER)],
            env=self.environment,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(saved.returncode, 0)
        self.assertEqual(self.cache.read_bytes(), original)


    def test_unwritable_cache_path_warns_and_does_not_report_success(self):
        self.cache.parent.mkdir(parents=True)
        self.cache.mkdir()

        saved = self.run_cache("save")

        self.assertNotEqual(saved.returncode, 0)
        self.assertIn("Warning:", saved.stderr)
        self.assertTrue(self.cache.is_dir())

    def test_payload_tampering_fails_manifest_verification(self):
        self.assertEqual(self.run_cache("save").returncode, 0)
        with tarfile.open(self.cache, "r:gz") as archive:
            members = [(member, archive.extractfile(member).read()) for member in archive.getmembers()]
        with tarfile.open(self.cache, "w:gz") as archive:
            for member, content in members:
                if member.name == "data/ruantiblock.ip":
                    content = b"tampered\n"
                archive.addfile(member, io.BytesIO(content))
        runtime = self.root / "var/ruantiblock/ruantiblock.ip"
        runtime.write_text("last working list\n")

        restored = self.run_cache("restore")

        self.assertNotEqual(restored.returncode, 0)
        self.assertIn("checksum", restored.stderr)
        self.assertEqual(runtime.read_text(), "last working list\n")
    def test_uci_and_parser_changes_invalidate_fresh_cache(self):
        self.assertEqual(self.run_cache("save").returncode, 0)
        runtime = self.root / "var/ruantiblock/ruantiblock.ip"
        for path, content in (
            (self.root / "etc/config/ruantiblock", "option enabled '1'\n"),
            (self.root / "usr/libexec/ruantiblock/parser", "#!/bin/sh\nexit 0\n"),
        ):
            original = self.cache.read_bytes()
            path.write_text(path.read_text() + content)
            runtime.write_text(content)
            saved = self.run_cache("save")
            self.assertEqual(saved.returncode, 0, saved.stderr)
            self.assertNotEqual(self.cache.read_bytes(), original)

    def test_partial_restore_failure_preserves_previous_runtime_files(self):
        self.assertEqual(self.run_cache("save").returncode, 0)
        self.write_payload(
            {name: "current\n" for name in self.payload},
            {name: "current\n" for name in self.dnsmasq},
        )
        script = '''
mv() {
    if [ "$1" = "-f" ] && [ "$2" = "$RUAB_ROOT/var/ruantiblock/ruantiblock_user_instances.ip.tmp" ] && [ ! -e "$RUAB_ROOT/tmp/mv_failed" ]; then
        : > "$RUAB_ROOT/tmp/mv_failed"
        return 1
    fi
    command mv "$@"
}
HELPER="$1"
set -- restore
. "$HELPER"
'''
        restored = subprocess.run(
            [SHELL, "-c", script, "sh", str(HELPER)],
            env=self.environment,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(restored.returncode, 0)
        self.assertIn("Warning:", restored.stderr)
        for name in self.payload:
            self.assertEqual((self.root / "var/ruantiblock" / name).read_text(), "current\n")
        for name in self.dnsmasq:
            self.assertEqual((self.root / "var/dnsmasq.d" / name).read_text(), "current\n")





if __name__ == "__main__":
    unittest.main()
