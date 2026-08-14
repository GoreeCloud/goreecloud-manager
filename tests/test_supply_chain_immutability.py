"""Regression tests for GoreeCloud Manager software-supply-chain inputs."""

from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = REPOSITORY_ROOT / ".github" / "workflows"


class SupplyChainImmutabilityTests(SimpleTestCase):
    def test_lock_contains_only_exact_hashed_packages_and_covers_direct_requirements(self):
        direct_text = (REPOSITORY_ROOT / "requirements.txt").read_text(encoding="utf-8")
        lock_text = (REPOSITORY_ROOT / "requirements.lock").read_text(encoding="utf-8")

        direct = {}
        for raw_line in direct_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s]+)", line)
            self.assertIsNotNone(match, f"direct requirement is not exactly pinned: {line}")
            direct[match.group(1).casefold()] = match.group(2)

        locked = {}
        lines = lock_text.splitlines()
        index = 0
        while index < len(lines):
            line = lines[index].strip()
            if not line or line.startswith("#"):
                index += 1
                continue

            self.assertTrue(line.endswith("\\"), f"locked requirement lacks continuation: {line}")
            requirement = line[:-1].strip()
            package_match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s]+)", requirement)
            self.assertIsNotNone(package_match, f"invalid locked requirement: {line}")
            self.assertLess(index + 1, len(lines), f"missing hash for {line}")
            hash_line = lines[index + 1].strip()
            self.assertRegex(hash_line, r"^--hash=sha256:[0-9a-f]{64}$")

            name = package_match.group(1).casefold()
            self.assertNotIn(name, locked)
            locked[name] = package_match.group(2)
            index += 2

        self.assertEqual(len(locked), 12)
        for name, version in direct.items():
            self.assertIn(name, locked)
            self.assertEqual(locked[name], version)

    def test_runtime_and_ci_install_only_from_hash_locked_binary_requirements(self):
        dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")
        ci = (WORKFLOW_ROOT / "ci.yml").read_text(encoding="utf-8")
        install_contract = (
            "python -m pip install --require-hashes --only-binary=:all: "
            "-r requirements.lock"
        )

        self.assertIn("--require-hashes --only-binary=:all: -r requirements.lock", dockerfile)
        self.assertIn(install_contract, ci)
        self.assertNotIn("pip install -r requirements.txt", dockerfile)
        self.assertNotIn("pip install -r requirements.txt", ci)

    def test_application_base_image_is_tagged_and_digest_pinned(self):
        dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")
        base_image = re.search(
            r"^FROM python:(\d+\.\d+\.\d+)-slim@sha256:([0-9a-f]{64})$",
            dockerfile,
            re.MULTILINE,
        )

        self.assertIsNotNone(base_image)
        self.assertEqual(base_image.group(1), "3.14.6")

    def test_all_external_github_actions_use_full_commit_shas(self):
        action_pattern = re.compile(r"uses:\s*([^\s@]+/[^\s@]+)@([^\s#]+)")
        found = []

        for workflow_path in sorted(WORKFLOW_ROOT.glob("*.yml")):
            workflow = workflow_path.read_text(encoding="utf-8")
            self.assertNotIn("runs-on: ubuntu-latest", workflow)
            self.assertIn("runs-on: ubuntu-24.04", workflow)
            self.assertRegex(workflow, r"timeout-minutes:\s*\d+")

            for repository, reference in action_pattern.findall(workflow):
                found.append((workflow_path.name, repository, reference))
                self.assertRegex(
                    reference,
                    r"^[0-9a-f]{40}$",
                    f"{workflow_path.name} uses mutable action reference {repository}@{reference}",
                )

        self.assertTrue(found, "expected at least one external GitHub Action reference")
