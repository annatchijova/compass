#!/usr/bin/env bash
# COMPASS Autopilot — Cloud Run Job entrypoint.
#
# Sweep every sealed compass once and exit. The sweep restores each user's
# base from GCS, runs the autopilot (Sentinel + next-step briefing), records
# the briefing hash in the chain, and snapshots the base back. It moves NO
# sealed index: a fail-closed guard raises if it ever did.
set -euo pipefail

exec python -m compass.agent.autopilot
