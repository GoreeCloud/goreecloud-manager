"""Regression tests for GoreeCloud Manager software-supply-chain inputs."""

from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = REPOSITORY_ROOT / ".github" / "workflows"
EXACT_REVISION_EXPRESSION = "${{ github.event.pull_request.head.sha || github.sha }}"


def workflow_job_blocks(workflow: str) -> dict[str, str]:
    """Return top-level workflow job bodies without requiring a YAML dependency."""
    lines = workflow.splitlines()
    try:
        jobs_index = next(index for index, line in enumerate(lines) if line.rstrip() == "jobs:")
    except StopIteration:
        return {}

    jobs: dict[str, list[str]] = {}
    current_job: str | None = None
    for line in lines[jobs_index + 1 :]:
        if line and not line.startswith((" ", "\t", "#")):
            break
        job_match = re.match(r"^  ([A-Za-z0-9_-]+):\s*(?:#.*)?$", line)
        if job_match:
            current_job = job_match.group(1)
            jobs[current_job] = []
            continue
        if current_job is not None:
            jobs[current_job].append(line)

    return {name: "\n".join(body) for name, body in jobs.items()}


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

    def test_all_external_github_actions_use_full_commit_shas_and_exact_checkout(self):
        action_pattern = re.compile(r"uses:\s*([^\s@]+/[^\s@]+)@([^\s#]+)")
        reusable_job_pattern = re.compile(
            r"^    uses:\s*([^\s@]+/[^\s@]+)@([^\s#]+)\s*$",
            re.MULTILINE,
        )
        found = []

        for workflow_path in sorted(WORKFLOW_ROOT.glob("*.yml")):
            workflow = workflow_path.read_text(encoding="utf-8")
            jobs = workflow_job_blocks(workflow)
            self.assertTrue(jobs, f"{workflow_path.name} must define at least one job")

            for job_name, job in jobs.items():
                reusable = reusable_job_pattern.search(job)
                if reusable:
                    self.assertNotIn(
                        "runs-on:",
                        job,
                        f"{workflow_path.name}:{job_name} reusable caller must not own a runner",
                    )
                    self.assertNotIn(
                        "timeout-minutes:",
                        job,
                        f"{workflow_path.name}:{job_name} reusable caller timeout belongs in called workflow",
                    )
                    self.assertRegex(
                        reusable.group(2),
                        r"^[0-9a-f]{40}$",
                        f"{workflow_path.name}:{job_name} uses mutable reusable workflow reference",
                    )
                else:
                    self.assertNotIn(
                        "runs-on: ubuntu-latest",
                        job,
                        f"{workflow_path.name}:{job_name} must use the pinned runner image",
                    )
                    self.assertIn(
                        "runs-on: ubuntu-24.04",
                        job,
                        f"{workflow_path.name}:{job_name} must use ubuntu-24.04",
                    )
                    self.assertRegex(
                        job,
                        r"timeout-minutes:\s*\d+",
                        f"{workflow_path.name}:{job_name} must have an explicit timeout",
                    )
                    self.assertIn(
                        f"ref: {EXACT_REVISION_EXPRESSION}",
                        job,
                        f"{workflow_path.name}:{job_name} must check out the exact PR head or main commit",
                    )

            for repository, reference in action_pattern.findall(workflow):
                found.append((workflow_path.name, repository, reference))
                self.assertRegex(
                    reference,
                    r"^[0-9a-f]{40}$",
                    f"{workflow_path.name} uses mutable action reference {repository}@{reference}",
                )

        self.assertTrue(found, "expected at least one external GitHub Action reference")

    def test_ci_checksum_pins_trivy_release_archive_and_uses_debian_os_policy(self):
        ci = (WORKFLOW_ROOT / "ci.yml").read_text(encoding="utf-8")
        self.assertIn('TRIVY_VERSION: "0.74.0"', ci)
        self.assertIn(
            'TRIVY_LINUX_AMD64_SHA256: '
            '"2ae6fe3ee734b7fdf11335663e18c75ea12dccc76062f09f164a3b0f8be4371a"',
            ci,
        )
        self.assertIn("sha256sum --check", ci)
        self.assertIn("--pkg-types os", ci)
        self.assertNotIn("--vuln-type os", ci)
        self.assertIn("--vuln-severity-source debian", ci)
        self.assertIn("--disable-telemetry", ci)
        self.assertIn("--skip-version-check", ci)
        self.assertIn("--scanners vuln", ci)
        self.assertIn("--exit-on-eol 2", ci)
        self.assertIn("security/trivy-container-policy.json", ci)
        self.assertIn("goreecloud-manager-image.cdx.json", ci)
        self.assertIn("manager-container-os-vulnerability-summary.json", ci)
