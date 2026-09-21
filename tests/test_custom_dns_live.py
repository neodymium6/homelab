"""Optional real Unbound tests on loopback; no production DNS or Internet used."""
import contextlib
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
import unittest

import test_custom_dns as dns_tests


@unittest.skipUnless(all(shutil.which(c) for c in ("unbound", "unbound-checkconf", "dig")),
                     "requires unbound, unbound-checkconf and dig")
class UnboundIntegrationTests(unittest.TestCase):
    def port(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def query(self, port, name, kind="A", short=True):
        args = ["dig", "@127.0.0.1", "-p", str(port), name, kind, "+time=1", "+tries=1"]
        if short:
            args.append("+short")
        return subprocess.run(args, text=True, capture_output=True, timeout=4)

    @contextlib.contextmanager
    def server(self, path, config, port):
        path.write_text(config)
        checked = subprocess.run(["unbound-checkconf", str(path)], text=True, capture_output=True)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        with (path.parent / (path.stem + ".log")).open("w+") as log:
            proc = subprocess.Popen(["unbound", "-d", "-c", str(path)], stdout=log, stderr=log)
            try:
                for _ in range(30):
                    if proc.poll() is not None:
                        log.seek(0)
                        self.fail(log.read())
                    if self.query(port, "vm.internal.example.com").returncode == 0:
                        break
                    time.sleep(0.1)
                else:
                    self.fail("isolated Unbound did not start")
                yield
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)

    def test_generated_custom_upstream_and_removal(self):
        with tempfile.TemporaryDirectory(prefix="homelab-dns-test-") as tmp:
            root = Path(tmp)
            upstream_port, port = self.port(), self.port()
            while port == upstream_port:
                port = self.port()
            common = ('server:\n  interface: 127.0.0.1\n  username: ""\n'
                      '  chroot: ""\n  use-syslog: no\n  module-config: "iterator"\n'
                      f'  directory: "{root}"\n  pidfile: ""\n')
            upstream = (common + f'  port: {upstream_port}\n'
                        '  local-zone: "example.net." static\n'
                        '  local-data: "sibling.example.net. A 192.0.2.90"\n'
                        '  local-data: "reader.example.net. A 192.0.2.91"\n'
                        '  local-zone: "internal.example.com." static\n')
            helper = dns_tests.CustomDNSTests()
            records = [helper.record(), helper.record(type="AAAA", value="2001:db8::10"),
                       helper.record(name="reader.example.net")]

            def config(items):
                rendered = helper.render(items).replace('server:\n', common, 1)
                rendered = rendered.replace('  interface: 127.0.0.1\n', '', 1)
                rendered = rendered.replace('  directory: "/var/lib/unbound"\n', '')
                rendered = rendered.replace('  username: "unbound"\n', '')
                rendered = rendered.replace('port: 5353', f'port: {port}')
                rendered = rendered.replace('forward-addr: 192.0.2.53',
                                            f'forward-addr: 127.0.0.1@{upstream_port}')
                return rendered.replace('  hide-identity: yes', '  do-not-query-localhost: no\n  hide-identity: yes')

            with self.server(root / "upstream.conf", upstream, upstream_port):
                with self.server(root / "resolver.conf", config(records), port):
                    for name, kind, expected in (
                        ("vm.internal.example.com", "A", "192.0.2.10"),
                        ("app.internal.example.com", "A", "192.0.2.10"),
                        ("reader.internal.example.com", "A", "192.0.2.10"),
                        ("reader.internal.example.com", "AAAA", "2001:db8::10"),
                        ("10.2.0.192.in-addr.arpa", "PTR", "vm.internal.example.com."),
                        ("reader.example.net", "A", "192.0.2.10"),
                        ("sibling.example.net", "A", "192.0.2.90"),
                    ):
                        with self.subTest(name=name, kind=kind):
                            answer = self.query(port, name, kind)
                            self.assertEqual(answer.returncode, 0, answer.stderr)
                            self.assertEqual(answer.stdout.strip(), expected)
                    answer = self.query(port, "missing.internal.example.com", short=False)
                    self.assertIn("status: NXDOMAIN", answer.stdout)
                with self.server(root / "resolver.conf", config([]), port):
                    self.assertEqual(self.query(port, "reader.example.net").stdout.strip(), "192.0.2.91")
                    self.assertEqual(self.query(port, "vm.internal.example.com").stdout.strip(), "192.0.2.10")


if __name__ == "__main__":
    unittest.main()
