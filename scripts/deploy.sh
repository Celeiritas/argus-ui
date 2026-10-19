#!/bin/bash
# deploy.sh - update the running Argus from git, on the machine that runs it:
#   cd ~/src/argus-ui && bash scripts/deploy.sh [theme]
# Pulls the latest main, builds the package and installs it. Your sounds (~/.config/argus-ui/sfx), weather
# location and listen address are kept. Nothing is deleted: the previous version is moved to .set-aside-<date>.
set -e
R=$(cd "$(dirname "$0")/.." && pwd); cd $R
git pull --ff-only
bash scripts/build.sh "${1:-leafy-realm}"
V=$(cat VERSION); bash "dist/argus-ui-$V-${1:-leafy-realm}/install.sh"
