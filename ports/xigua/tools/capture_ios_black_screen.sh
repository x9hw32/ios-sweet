#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
case_dir="diagnostics/ios-black-$(date -u +%Y%m%dT%H%M%S)-$$"
python3 tools/collect_ufs_log.py --output "$case_dir"
python3 tools/analyze_boot_log.py "$case_dir/console.txt" --output "$case_dir/analysis"
printf '\nDisplay / touch / panic messages:\n'
rg -a 'FB: display|XIGUA TOUCH|panic\(|Kernel data abort' "$case_dir/console.txt" | tail -50 || true
printf '\nSaved: %s\n' "$case_dir"
