> Superseded by the verified native migration-file repair. The old
> SpringBoard binary workaround is removed from the phone and should not be
> reinstalled. Its installer refuses a locally marked superseded plan.
> See HFS_RECOVERY.md and STATUS.md for the current approach and phone results.

# Local SpringBoard state for the PJA110 research port

The captured SpringBoard main thread waits in MobileActivation while the
unsupported activation daemon repeatedly aborts with "Migration failed."
All three physical keys have verified read/HID edges on PJA110; this wait can
still prevent visible UI response.

The approach comes from [OOSEX GANG inject_sb.c](https://github.com/oosexgang/hackios-xnu-userland/blob/a79ff0772a3454fd1ef127e181e5b3bce6c9ce18/userland/src/inject_sb.c):
set the local SBLockdownManager state to2. Our tools support ONLY the verified
arm64 method in20H392. They check its352-byte SHA256 and the original ad-hoc
code-page hash, patch16bytes, and repair the changed SHA256 signature slot.
They do not depend on the other project's iOS16.5 addresses or input ABI.

Prepare against a read-only mounted CURRENT root snapshot with a receipt
containing its verified phone-source SHA256:

```bash
sudo python3 tools/prepare_activation_patch.py \
  --cache-file MOUNT/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64.21 \
  --root-image SNAPSHOT/root.img --output out/activation-state-1
```

Preparation uses read-only FIBMAP and compares physical sectors to the snapshot.
Only host output files are written. Keep the generated sector originals and
receipt private and accessible to the user invoking the installer. Unmount the
host snapshot, then install in PJA110 recovery:

```bash
python3 tools/apply_activation_patch.py --prepared out/activation-state-1
```

The installer checks the allocated linux partition, volume identity, receipt,
old/new sector hashes, and reads all targets before writes. It uses BusyBox dd,
verifies each full sector readback, and rolls back if a write fails. Undo in
recovery with the same command plus `--restore`. Do not transfer a prepared
physical sector plan to another root image; recalculate it from that snapshot.

The existing native iOS ESP and physical-key kernel remain in use. This is a
local port compatibility change; phone UI behavior still requires a real boot
test. See STATUS.md for the latest observed result.
