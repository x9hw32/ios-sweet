"""Resolve helper sources in the standalone workspace or the published fork."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DONOR = ROOT / 'upstream/ios-sweet'
if not (DONOR / 'tools/mkpayload.py').is_file():
    candidate = ROOT.parent.parent
    if (candidate / 'tools/mkpayload.py').is_file() and (candidate / 'shim/font.h').is_file():
        DONOR = candidate
    else:
        raise RuntimeError('ios-sweet sources missing: run tools/bootstrap.py')
