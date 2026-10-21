#!/bin/bash
# deploy.sh - update the running Argus from git, on the machine that runs it:
#   cd ~/src/argus-ui && bash scripts/deploy.sh [--no-pull] [theme]
# Pulls the latest main, builds the package and installs it. Your sounds (~/.config/argus-ui/sfx), weather
# location and listen address are kept. Nothing is deleted: the previous version is moved to .set-aside-<date>.
# --no-pull: build and install the commit that is checked out, without touching git. A deploy tool (Zeus) checks
# out the approved commit itself and then runs this. The line "ZEUS_STAGE=install" marks where the install
# begins: a failure before it changed nothing; a failure after it means the previous version should go back.
set -e
R=$(cd "$(dirname "$0")/.." && pwd); cd $R
PULL=1; [ "$1" = "--no-pull" ] && { PULL=; shift; }
[ -n "$PULL" ] && git pull --ff-only
bash scripts/build.sh "${1:-leafy-realm}"
echo ZEUS_STAGE=install
V=$(cat VERSION); bash "dist/argus-ui-$V-${1:-leafy-realm}/install.sh"
