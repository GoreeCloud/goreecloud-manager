# GoreeCloud Manager Linux Desktop Client

This directory contains the Linux desktop client for GoreeCloud Manager.

It is a companion to the repository's existing server-side Django GoreeCloud Manager application. The desktop client is kept in this repository so its source, history, packaging scripts, and recovery state remain under Git version control without replacing or overwriting the existing web application.

## Current version

**v0.2.5 — read-only stability hardening**

The client is built with Python and PySide6/Qt. It runs on a Linux workstation and can use the system OpenSSH client to collect read-only operational information from a GoreeCloud server.

v0.2.5 keeps the existing v0.2.4 monitoring feature set and strengthens the runtime boundary with exact direct dependency pins, `pip check`, private atomic configuration writes, bounded parsing for malformed numeric and boolean configuration values, fail-closed SSH host-key verification, and staged installation with rollback-safe cutover.

### Overview

- Remote CPU, memory, root-disk, uptime, load, OS, kernel, CPU-thread, and failed-systemd-unit information
- Operational Status summary for System, Docker, NetBird, and configured Services
- Lightweight Overview auto-refresh so Docker discovery does not distort the VPS CPU sample
- Manual full refresh for server, Docker, and NetBird state

### Containers

- Read-only Docker discovery and inventory
- Docker Engine version, total/running/stopped counts, and health-check summary
- Search, filters, sorting, and collapsible container details
- CPU, memory, image, state, health, ports, status, PID, exit code, restart policy, OOM-killed state, timestamps, Docker network mode, per-network IPs, mounts, and health failing streak
- No start, stop, restart, delete, or other container-control actions in this release

### Network

- Read-only NetBird status from the installed NetBird CLI
- Local NetBird IP, management/signal state, agent/daemon version, interface type, peer counts, peer status, connection type, and readable latency
- Search, filtering, and sorting
- The local VPS is excluded from its own remote-peer list

### Services

No service catalogue is preloaded. Services are added explicitly from **Settings > Services** only when they actually exist in the environment.

Each configured service can have a name, description, browser URL, optional health URL, and dashboard-enabled toggle.

## Run from source

```bash
./scripts/start.sh
```

On first launch, `start.sh` creates `.venv` and installs the exact direct Python dependency versions recorded in `requirements.txt`. Setup also runs `python -m pip check` before reporting success.

## Permanent Linux installation / upgrade

```bash
./scripts/install.sh
```

The desktop client installs under:

```text
~/.local/opt/goreecloud-manager
```

The desktop entry is installed under:

```text
~/.local/share/applications
```

User configuration is kept separately at:

```text
~/.config/goreecloud-manager/config.yaml
```

Manager writes the configuration through a same-directory atomic replacement and restricts the final file to mode `0600`. This file must not be committed to the repository.

The installer prepares a complete staged replacement beside the current installation before changing the active path. It reuses the existing `.venv` only when `requirements.txt` is unchanged, runs `pip check`, compiles the desktop Python package, and then performs the cutover. The previous installation remains available as a rollback copy until the new application directory and desktop entry are both installed successfully. If cutover or desktop-entry installation fails, the installer restores the previous application directory automatically.

The separately stored user configuration is not replaced by application upgrades.

## SSH monitoring

In **Settings > Monitoring**, choose **GoreeCloud server over SSH** and configure the server address. Username and SSH key path may remain blank when `~/.ssh/config`, `ssh-agent`, or normal OpenSSH defaults already provide them.

For example, if this already works from a terminal:

```bash
ssh goreecloud-vps-01
```

then `goreecloud-vps-01` can be used as the desktop client's Server address.

The application invokes the system OpenSSH client with non-interactive behavior. It does not prompt for or persist an SSH password. GoreeCloud Manager also requires the target host key to have been trusted already; it does not automatically accept a previously unseen SSH host identity. Establish or verify that trust through the approved OpenSSH workflow before using the desktop client.

## Security boundary

v0.2.5 is intentionally read-only. It does not start, stop, restart, delete, or modify Docker containers, NetBird configuration, systemd units, or other server workloads.

No private SSH key contents, passwords, API tokens, or populated user configuration belong in this repository.
