# UniXNU-xigua

Initial OnePlus Ace 2 Pro PJA110 port based on UniXNU-sheng and shared SM8550 support.
This is source preparation, not a bootable or device-verified UniXNU image.
The previous XNU/iOS 16 port's evidence is not proof that these new drivers work.

The selected profile is iPadOS 17.7.11 / 21H461, XNU 10063.141.1. Existing
20H392 iOS files cannot be reused as this profile's userland or kernel ABI inputs.
The configuration intentionally remains example=true until firmware, OS inputs,
reserved memory, storage bounds and component integration are complete.

The reference tablet matches SM8550 and Adreno 740. Its Novatek touch, panel,
power policy, firmware and userdata layout do not match PJA110. PJA110 has
Synaptics S3910 over GENI SPI at 0xa90000 and 1240x2772 GOP at 0xb8000000.
All eight CPUs are described as enabled, matching the sheng reference. No GPU or storage driver is enabled.
Only the allocated esp (96 MiB), installer and linux partitions may be used;
Android, boot slots, calibration and GPT are preserved. Do not run sheng's
installation/reset scripts against PJA110. Local QEMU is prohibited by the user.

Next milestone: resolve the minimal CPU/platform source tree, qualify a loader
under the existing Mu-xigua UEFI and reach a native diagnostic without disk writes.
Then adapt storage bounds, GOP, S3910 and physical buttons one subsystem at a time.

From ../unixnu:

```sh
./unixnu defconfig xigua_defconfig -D ../unixnu-xigua
./unixnu status --json -D ../unixnu-xigua
python3 scripts/porting-record.py check --device ../unixnu-xigua
```
