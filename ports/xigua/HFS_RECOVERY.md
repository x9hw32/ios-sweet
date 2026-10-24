# Recovery filesystem diagnosis with a host copy-on-write device

`recovery_hfs_cow.py` exposes only the first12GiB of the allocated PJA110 linux
partition as an unused host `/dev/nbd3`. Remote operations are exclusively
BusyBox **reads**. Virtual writes stay in host files. It refuses a busy NBD,
wrong phone/mode/partition; session/PID checks protect disconnects. No VM runs.

Start with phone in recovery and the Linux nbd module available:

```bash
sudo python3 tools/recovery_hfs_cow.py --output out/FRESH-COW
sudo python3 tools/replay_hfs_journal.py --cow out/FRESH-COW
```

The journal parser checks committed-range geometry, header/data checksums,
sequence, and target bounds before touching even the host virtual volume.
Unknown layouts or corruption fail closed. Strict replay does not search
uncommitted data beyond the recorded end. Check the virtual volume with
fsck_hfs, then use ordinary host HFS+ mounts on `/dev/nbd3` to inspect/repair
ONLY the host overlay. Never mount the phone root read-write in recovery.

After any virtual edits: unmount, run full fsck, recheck the target files and
journal, and save a task-specific validated.json. A new directory can require
counter/bitmap correction; validation must finish before device installation.
The supported tasks are migration-file repair and chronod's home environment.

Disconnect to export original/changed4KiB sectors and checksums:

```bash
sudo python3 tools/recovery_hfs_cow.py --output out/FRESH-COW --disconnect
```

Make generated files accessible to the user invoking the installer. Inspect
the plan, then `apply_hfs_cow.py --prepared out/FRESH-COW` installs only checked
changed sectors via recoveryBusyBoxdd. It compares every source sector first,
reads all results back, commits the journal header last, and rolls back the
preflight bytes on an I/O failure. Prepared originals remain private.

Metadata restoration with `--restore` requires all sectors still match known
old/new contents; later native boots can change catalog/header sectors. The
installer refuses those to protect newer filesystem data. Do not force an old
metadata plan onto a filesystem that has since changed. No snapshot, Apple file
or sector payload belongs in git.

Current actual fixes/results are in STATUS.md. chronod HOME is a candidate;
its success has not yet been confirmed on the phone. The prior native migration
file restoration stopped mobileactivationd's crash loop on the actual phone.
