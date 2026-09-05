"""Read-only rendering regression tests; requires PyYAML and Jinja2."""
from pathlib import Path
import unittest

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROLES = ROOT / "bastion/ansible/roles"


class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.context = yaml.safe_load((ROOT / "cluster.yaml.example").read_text())
        self.site = next(s for s in self.context["services"] if s["name"] == "personal-site")

    def render(self, path):
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        return yaml.safe_load(env.from_string((ROLES / path).read_text()).render(self.context))

    def test_only_personal_site_routes_are_removed(self):
        before = self.render("traefik/templates/dynamic.yml.j2")
        self.site["state"] = "absent"
        after = self.render("traefik/templates/dynamic.yml.j2")
        del before["http"]["routers"]["personal-site"]
        del before["http"]["services"]["personal-site-svc"]
        del before["http"]["middlewares"]["personal-site-retry"]
        self.assertEqual(before, after)

    def test_missing_state_remains_present(self):
        explicit = self.render("traefik/templates/dynamic.yml.j2")
        del self.site["state"]
        self.assertEqual(explicit, self.render("traefik/templates/dynamic.yml.j2"))

    def test_absent_homepage_link_is_not_rendered(self):
        self.site["state"] = "absent"
        after = self.render("homepage/templates/services.yaml.j2")
        self.context["services"].remove(self.site)
        self.assertEqual(after, self.render("homepage/templates/services.yaml.j2"))

    def test_absent_only_removes_known_files_and_preserves_images_and_volumes(self):
        tasks = yaml.safe_load((ROLES / "personal_site/tasks/absent.yaml").read_text())
        compose = next(t["community.docker.docker_compose_v2"] for t in tasks
                       if "community.docker.docker_compose_v2" in t)
        self.assertEqual(compose["state"], "absent")
        self.assertEqual(compose["project_name"], "personal-site")
        self.assertNotIn("remove_images", compose)
        self.assertFalse(compose["remove_volumes"])
        self.assertFalse(compose["remove_orphans"])
        deletes = [t for t in tasks if "ansible.builtin.file" in t]
        self.assertEqual(len(deletes), 1)
        self.assertEqual(deletes[0]["loop"], [
            "/etc/systemd/system/personal-site-update.timer",
            "/etc/systemd/system/personal-site-update.service",
            "/opt/stacks/personal-site/docker-compose.yml",
        ])


if __name__ == "__main__":
    unittest.main()
