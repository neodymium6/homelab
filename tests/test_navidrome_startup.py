"""Offline checks for mount-ordered Navidrome startup."""
from pathlib import Path
import unittest

from jinja2 import Environment, StrictUndefined
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "bastion/ansible/roles/navidrome"


class NavidromeStartupTests(unittest.TestCase):
    def test_unit_orders_mount_before_attached_compose(self):
        template = Environment(undefined=StrictUndefined).from_string(
            (ROLE / "templates/navidrome.service.j2").read_text())
        for library in ("/mnt/nfs/music/library", "/srv/music"):
            with self.subTest(library=library):
                unit = template.render(navidrome_library_dir=library,
                                       navidrome_dir="/opt/stacks/navidrome",
                                       navidrome_compose_path="/opt/stacks/navidrome/docker-compose.yaml")
                self.assertIn("RequiresMountsFor=" + library, unit)
                self.assertIn("Requires=docker.service", unit)
                self.assertIn("After=docker.service", unit)
                self.assertIn("PartOf=docker.service", unit)
                self.assertIn("WantedBy=multi-user.target docker.service", unit)
                self.assertIn("--exit-code-from navidrome navidrome", unit)
                self.assertIn("--pull never", unit)
                self.assertNotIn(" up -d", unit)
                self.assertIn("Restart=always", unit)
                self.assertIn("stop --timeout 30 navidrome", unit)
                self.assertNotIn(" down", unit)

    def test_docker_cannot_bypass_systemd(self):
        template = (ROLE / "templates/docker-compose.yaml.j2").read_text()
        self.assertIn('restart: "no"', template)
        self.assertNotIn("restart: unless-stopped", template)
        handlers = yaml.safe_load((ROLE / "handlers/main.yaml").read_text())
        self.assertEqual(handlers[0]["ansible.builtin.systemd"]["name"], "navidrome.service")

    def test_role_uses_idempotent_service_start_and_preserves_data(self):
        tasks = yaml.safe_load((ROLE / "tasks/startup.yaml").read_text())
        self.assertIn("community.docker.docker_image", tasks[0])
        service = tasks[-1]["ansible.builtin.systemd"]
        self.assertTrue(service["enabled"])
        self.assertIn("else 'started'", service["state"])
        self.assertNotIn("state: absent", (ROLE / "tasks/startup.yaml").read_text())
        main = yaml.safe_load((ROLE / "tasks/main.yaml").read_text())
        imported = next(t for t in main if t.get("ansible.builtin.import_tasks") == "startup.yaml")
        self.assertIn("navidrome-startup", imported["tags"])


if __name__ == "__main__":
    unittest.main()
