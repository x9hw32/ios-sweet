## Touch probe2 SENT; current root backed up and LaunchServices stores persisted — 2026-10-23

KernelCI40009954336 SUCCESS at commit2de11dd. ZIPCRC+SHA verified:
fc1d392a86ed6bf35e4500b4edd74f36f2f167fa9e68ff4d47b92673173cde07.
Kernel includes local GENI event-enable correction plus step/phase/IRQ/FIFO/
clock failure diagnostics. Actual _tp_fault and _xigua_touch_start linked.
Host40checks PASS and full touch C ARM64 compile PASS before this CI.

In recovery READ ONLY captured the CURRENT12GiB root for inspection/backup:
diagnostics/ios-ufs-60-1-root-snapshot/root.img; receipt SHA
299d85c7429b8429163df5e4fd4eb13963aad66b5a72002f7ba471bcd9da0bf9.
No root partition writes by this capture. Mounted baseline and snapshot read
only on host for inspection; BOTH UNMOUNTED afterward. Filesystem on phone
unchanged by inspection. Snapshot journal was not replayed.

Confirmed persistent cache difference: baseline has0 LaunchServices candidate
files; current root has26 including two csstore databases (4407296B,3637248B).
Private evidence diagnostics/ios-ufs-60-1-native-analysis-2/
{baseline-launchservices-files.json,live-launchservices-files.json,
cache-persistence.json}. Therefore first native boot DID save LS databases;
RAMroot previously discarded them. This makes second native boot timing a
necessary next measurement; it has NOT been measured and is NOT promised fast.
Actual first-boot stacks locate LS database reseeding as a startup gate, not
GPU rasterization. Current VeryLowDisk state (~94MiB free) is also confirmed.
Do not delete files or resize blindly. Preserve original and current snapshots.

Saved prior ESP in diagnostics/ios-before-touch-probe-2, restored original,
then installed out/efi-touch-probe-2/esp.img via recoveryBusyBoxdd. FullSHA
readback VERIFIEDeea76460f9aeee0ab93ed1bd74ac8e0263c0a526a6f52a383ae691d83052b69b.
TemporaryMu fastbootboot Sending/Booting OKAY; diagnostics/touch-probe-2-boot.txt
and json. Tiny RAM PID1, CPU6, touchON, UFSOFF, no Apple userland or rootwrites.
USER SCREEN RESULT PENDING via async question. Need new failure step/phase and
CMD/IRQ/ACTIVE or coordinate reports after taps. Do not reboot while waiting.
Touch NOT yet confirmed working. Buttons remain separate next hardware task.

PreparedONLY full native iOS+touch candidate using this NEW kernel:
out/phone-ios-ufs-touch-2 and out/efi-ios-ufs-touch-2/esp.img. NOT INSTALLED.
CPU6/fit60 cap, nativeRWlinux, noRAMroot, touchON. Added host CLI optional
--sample-processes; candidate samples SpringBoard,backboardd,lsd (existing
kernel feature, no new kernel code). Boot it AFTER the raw-touch test succeeds;
measure whether persisted LS caches remove the15min delay. Old baseline CRCs
remain invalid for current filesystem. No local QEMU and no boot partition
flashes. Public repo never includes Apple files, snapshots or device logs.

## Native iOS boot confirmed, delay traced to LaunchServices; touch probe1 timed out — 2026-10-23

User reports native UFS iOS DID start after ~15 min, buttons/touch inactive.
Touch was OFF in that image. Saved diagnostics/ios-ufs-60-1-user-result.json.
No significant boot-time improvement from dropping12GiB RAMroot. In recovery
read actual native console: diagnostics/ios-ufs-60-1-native-log (263214B, flush
127, seven samples). Data captured BEFORE any touch boot overwrote state.
Header shows free98340864B (~94MiB), down from baseline432340992B (~413MiB).
Actual log: hfs set VeryLowDisk, freeblks100400 dangerlimit131072. No ENOSPC
message found; low space is evidence, not yet proof of the boot delay's cause.
ACTUAL runtime CPU line: 6/6 CPUs initialized, SGI1 verified.

Symbolicated59 frame addresses with ipsw dyld a2f batch. Results PRIVATE in
 diagnostics/ios-ufs-60-1-native-analysis/{symbols.json,first-stacks.txt}.
Across all seven samples (~90..810s after sampler start), SpringBoard main
waits in __os_unfair_lock_lock_slow -> LSContextInitCommon -> LSApplicationRecord
-> CCSModuleRepository associated-bundle lookup. A backboardd worker waits in
XPC -> LAUNCH_SERVICES_IS_RESEEDING_ITS_DATABASE_AND_MAY_BLOCK -> LSCopyServerStore.
This localizes a real startup gate to LaunchServices database initialization;
it is not evidence that GPU rendering consumed the whole15min. RAMroot boots
previously discarded all newly-built databases every reboot. First native UFS
boot can persist them, so check native LS database/reboot before inventing a
bypass. Need inspect current root and lsd state, then compare a second native
boot. No root files changed by investigation.

Host baseline mounted READ ONLY at build/boot-delay-root-ro for symbol lookup;
MUST unmount before stopping. Source image unchanged. Read-only cache index
outside image: build/boot-delay-reference/symbols.a2s (730MB), main executables
copied in same private reference directory. Apple files and diagnostics NOTgit.
New tools/analyze_boot_log.py handles per-process ASLR, crashes, space/waits,
including concatenated/truncated console records; collect_ufs_log also saves
volume-header.bin and volume.json via BusyBox reads (no mount/journal replay).
40hostchecks currentlyPASS; fulltouch driver ARM64 compile being checked.

Touch fastprobe1 installed with recoveryBusyBoxdd/fullSHAverified:
out/efi-touch-probe-1/esp.img SHA
dc79226241425fe4046b0b8331757f44d4b39fd2cee0bc66430d366f464a887e.
TemporaryMu boot OKAY, diagnostics/touch-probe-1-boot.txt/json. Tiny RAMinit,
GUI service/HID enabled via ios-userland flag but NO Apple userland, UFSOFF,
no rootwrites, cpus6. User reports SPI firmware102 status0 then initerror60;
no coordinate reports. Saved diagnostics/touch-probe-1-result.json.
Candidate touchfix: arm local GENI IRQ event enables instead of zeroing them,
while keeping external IRQ routing/GSI OFF. Matches Linux initialization and
proven donor polling pattern. Add detailed step/phase/IRQ/clock/FIFO diagnostics.
Need remote kernel CI and touchprobe2. Touch NOT working yet. User asked to
return recovery while build runs; no subsequent phone changes yet.

PreparedONLY full iOS+touch candidate from OLD kernel (not installed):
out/efi-ios-ufs-touch-1/esp.img SHA
aa784109f48bc74b6c4ea27357c49f21d1bbb4f7b214eb4eb539656e6452da78.
Do not use it to repeat old timeout. Buttons remain separate future task.

## Native iOS from UFS at 60 fps cap: installed and boot sent — 2026-10-23

User confirmed recovery; ADB verified PJA110/recovery/root BusyBox. Saved the
previous probe3 ESP in diagnostics/ios-before-ios-ufs-60-1, then restored the
original ESP as required by the installation guard. Installed the prepared
out/efi-ios-ufs-60-1/esp.img via recovery BusyBox dd. Full readback SHA verified:
fc23e21fc929bb7147109d53846a7658131f3346c5b52e5dbcfa858b3330b6b4.
Logs: diagnostics/ios-before-ios-ufs-60-1.log and ios-ufs-60-1-esp-install.log.
Temporary fastboot boot of the user's Mu-xigua-0.img returned Sending/Booting
OKAY. Started 2026-10-23 18:44:27 UTC / 21:44:27 Moscow. Receipt and output:
diagnostics/ios-ufs-60-1-boot.json and ios-ufs-60-1-boot.txt.

Same hardware-proven read-check kernel CI40003280437, SHA
 a670969edfad80fa1dbd9fe1cdc87c40886573c750d75adfba5587f8a2412bfe.
Payload arguments independently verified: rd=ufsroot0 xiguaufs=2 ufsrw=1,
cpus=6 sweetfb_hz=60 sweetfb_fit=1. No external RAM root, no 12 GiB preload.
This is the first REAL iOS root boot from UFS; previous probe ran tiny PID1.
Presentation cap is 60 fps, not a measured frame rate or confirmed physical
panel frequency. Touch remains OFF for an isolated native-root boot test.
User screen observation is PENDING through async question. Do not reboot or
start another phone test until the observation arrives.

Native root now permits bounded writes inside allocated linux only. The root
filesystem and console tail may change; baseline RAM-preload/probe CRC tables
are no longer valid for judging the on-phone filesystem after these writes.
Do not rewrite the 12 GiB root or retry old full-baseline probes blindly.
Persistent console and process sampler are enabled. If boot stalls, after the
user returns to recovery read it with tools/collect_ufs_log.py into a fresh
diagnostics directory. If UI boots, next requested task is touch: compiled
S3910 driver is opt-in via --touch with --display-mode fit; no kernel rebuild
is needed merely to enable it. No local QEMU or boot partition flashes.

## Hardware UFS READ CHECK PASS; native iOS UFS / 60 fps candidate ready — 2026-10-23

User reports probe3 READ CHECK PASS followed by XIGUA init still-alive.
Saved diagnostics/ufs-probe-3-result.json. Kernel40003280437 / 4d53528 ACTIVE
activation resolves the prior02/04/02 failure. Actual target data reads and
three 4 MiB CRC samples match the prepared root. Handoff + SCSI + GPT + HFSX
header and all three CRCs now verified on phone. Probe remained READ ONLY.

User now requests60/120Hz. Current compiled framebuffer uses16667us vsync
and a flush divisor: sweetfb_hz60 selects everytick (previous30 every2ticks).
This is a PRESENTATION CAP, not measured FPS or confirmed physical DSI panel
mode. No claim of120Hz: that needs panel/DSI mode verification and more work.
Built out/phone-ios-ufs-60-1 and out/efi-ios-ufs-60-1/esp.img SHA
fc23e21fc929bb7147109d53846a7658131f3346c5b52e5dbcfa858b3330b6b4.
Same proven UFS kernel SHAa670969edfad80fa1dbd9fe1cdc87c40886573c750d75adfba5587f8a2412bfe.
Payload args verified rd=ufsroot0 xiguaufs2 ufsrw1 cpus6 sweetfb_hz60 andfit1;
no externalRAMroot andtouchOFF. Full13GiB managedRAM minus kernel (no12GiBcopy).
Root is already present inlinux; do not rewrite it. Read-onlyCRC milestone is
satisfied, so install this nativeRWroot candidate once recovery is available.
Manualrecovery requested viaasync; currently noADB. Image NOT YET INSTALLED.

After first nativeRWboot, rootfilesystem andconsole tail maychange inlinux.
Old baseline verified-crcs.json and RAM-preload ESP CRC tables MUST NOT be
used to judge the changed on-phone filesystem. Keep local original12GiB image
as baseline; do not blindly reinstall or replace it. Native root mode correctly
checks geometry+HFSX header but skips baselineCRCs. tools/collect_ufs_log.py can
read the nativeconsole tail fromrecovery to diagnose boot delays. ExistingRAM
fallback ESPs assume original rootCRCs and may need refreshed cache afterRW.
Touch driver compiled, remainsOFF pending actual nativeUFSroot UI test.

## UFS probe3 with ACTIVE activation SENT to phone — 2026-10-23

KernelCI40003280437 SUCCESS commit4d53528, ZIPCRC+SHA verified:
a670969edfad80fa1dbd9fe1cdc87c40886573c750d75adfba5587f8a2412bfe.
Actualkernel contains ready/activate code, DEVICE WLUN d0 and finalpanicLUN;
readiness disassembly build/ufs-ready-ci-40003280437.asm. 35hostchecks PASS
bothworkspace/published; fullUFS ARM64localcompilePASS. No localQEMU.

Phone enteredrecovery manually. Backed up priorESP2 in
 diagnostics/ios-before-ufs-probe-3 and restoredoriginal (fullSHAverified).
Installed out/efi-ufs-probe-3/esp.img withBusyBoxdd inrecovery; FULLSHAreadback
2876b16290f383532bb74761992aeed57fbe7efc2ec60c67896b5d54628f3851 VERIFIED.
TemporaryMu fastbootboot Sending/Booting OKAY. Logs diagnostics/
ios-before-ufs-probe-3.log, ufs-probe-3-esp-install.log, ufs-probe-3-boot.txt/json.
CPU6, tinyRAMroot, no12GiBcopy, UFSREADONLY andtouchOFF. USER SCREEN RESULT
PENDING through async question. Do NOT reboot until observation. Ifpanic,
getstage/op/lun/ocs/st/sense. READCHECKPASS still REQUIRED before anyRWroot.

PreparedONLY (NOT INSTALLED) matching nativeUFS iOSroot fallback/nextstep:
out/phone-ios-ufs-3 and out/efi-ios-ufs-3/esp.img SHA
9502dacc5908ddc094cbc9c26f942fd84124a0ea1e206594635402e89777b3c7.
Samekernel, CPU6, fit30Hz, --ufs-root --ios-userland, touchOFF. NoRAMrootpreload;
root alreadyinlinux and MUST NOT be rewritten. Install this only AFTER actual
probe3CRC PASS. It enables boundedRWlinux andexistingpersistentconsole/process
sampler; tools/collect_ufs_log.py reads tail fromrecovery ifbootstalls.
Touch source compiled buthardwareuntested; hold inputtest untilUFSmilestone.

## Probe2 isolates NOT READY 02/04/02; DEVICE WLUN activation added — 2026-10-23

USER EXACT PANIC: ready err5 op00 ocs0 upiu21 rsp01 st02 sense02/04/02 IS1.
Saved diagnostics/ufs-probe-2-result.json. Handoff and descriptor/response DMA
worked enough to exchange TEST UNIT READY with device. DATA READS/CRCs not yet
verified. Failure is CHECK CONDITION, NOT READY / LOGICAL UNIT NOT READY,
INITIALIZING COMMAND REQUIRED. Do not assume changing DMA/PHY/SMMU is needed.

Added kernel/xigua_ufs_ready.h: retain alreadyready path; on specific02/04/02
send UFS START STOP UNIT ACTIVE (1b 00 00 00 10 00) to DEVICE WLUN0xd0, NOT
RPMB0xc4, temporarily restore su.lun=0 on everyexit. Matches OnePlus Linux
ufshcd_set_dev_pwr_mode with ACTIVE1 inCDBbyte4highnibble. Filtered bounded
UNIT ATTENTION retries and2sec readywait for04/01 or04/02, no retries forDMA/
illegalrequest/manualintervention errors. No mediawrite/format/modepages or
linkreset. Finalpanic now includescommandLUN andactivation/readinessstage.
Hosttest uses EXACTphone response, checks SSU targetCDB, alreadyready path,
activationUA/reject, restoredLUN, nonretryable errors andboundedwait.
35hosttests PASS; fullUFS C localARM64compilePASS. Need remoteCI thenprobe3.
Touch remainsOFF during UFS tests. Phone had noADB; user asked to reboot to
recovery while building. Do not enable nativeUFSRW before actualCRC PASS.

## Diagnostic UFS probe2 SENT to phone — 2026-10-23

KernelCI40001017670 SUCCESS commit78a86f2, verified SHA
 ec0167e191760a1bf96c67a85d62fa837702c32c393c56735545453edfbd13d5.
Actualkernelstrings/symbols confirm xigua_ufs_probe_fail andlinkedtouchdriver;
MMIO/DSB disassembly saved build/ufs-handoff-ci-40001017670.asm.
Built out/phone-ufs-probe-2 and out/efi-ufs-probe-2. ESP SHA
995069b76bbbdc87f257f6da1bbf3d6f259692b53b52af7cd83674a85c7b11fd.
ADB Android -> recovery. Backed up probe1 ESP in
 diagnostics/ios-before-ufs-probe-2, restoredoriginal, installedprobe2 through
recoveryBusyBoxdd and FULL SHA readback VERIFIED. Logs diagnostics/
ios-before-ufs-probe-2.log, ufs-probe-2-esp-install.log, ufs-probe-2-boot.txt/json.
TemporaryMu fastbootboot Sending/Booting OKAY. CPU6, UFSREADONLY mode1,
no12GiB preload, tinyRAMroot, touchOFF. NEW SCREEN RESULT PENDING.
If newpanic, finalmessage carriesstage/op/ocs/upiu/rsp/st/sense/IS; getthisline.
If initrunningPID1 appears, IOFindBSDRoot's probe returnedwithoutfailure, but
obtain READ CHECK PASS observation to confirmchecks explicitly. Do not enable
nativeUFSRW untilverifiedreadpass. Do not reboot whileawaitingobservation.

Touch implementation compiled SUCCESS in39999855589 and40001017670; input
hardware remainsUNTESTED, keepseparatetest afterUFS. All34hostchecksPASS,
updatedUFSdriver localARM64compilePASS. NoQEMU andnobootpartitionwrites.

## Active build continuation — 2026-10-23 18:12 UTC

Currentcandidate78a86f2, kernelCI40001017670 inprogress; fetchdaemon
build/fetch-kernel-40001017670.py/log/status running. Host34tests bothcopiesPASS,
fullUFS ARM64compilePASS. Need actualartifact -> buildout/phone-ufs-probe-2 and
out/efi-ufs-probe-2 using --ufs-probe CPU6 tinyroot + verifiedCRCcache. Reboot
ADB Android to recovery only onceimage ready. Backupprobe1ESP, BusyBoxdd/write
verify, temporaryMu boot. Newpaniccontainsstage+OCS/status/sense; ask onlythat
line iffail. Keep touchOFF andnativeUFS RWoff untilverifiedreadpass.
Touchkernel9ae4474 downloaded artifacts/xigua-ci-39999855589 SHA
bab53ad3ec36cd1bf73268428e0e5c4eb635d5243189b92605ca9f716853647e.
Actualsymbols _xigua_touch_start/_tp_thread/_tp_spi/HIDstart confirmedlinked.
No touchhardwaretestyet. Do not bootthatoldkernel to repeatuninformativeUFS EIO.

## UFS probe1 FAILED EIO on phone; diagnostic probe2 prepared — 2026-10-23

User saw panic(cpu0): XIGUA UFS read-only probe failed:5 atIOKitBSDInit.cpp780.
NO READ CHECK PASS. User manually rebooted before earlierhost/SCSI lines could
be read; now ADB Android (ro.bootmode smpl). Do not enable nativeUFS RW.
out/efi-ios-ufs-1 was prepared only; NEVER installed, currentESP remainsprobe1.
Actual stage remains UNKNOWN: EIO can mean listreadback, SCSI/OCS, or CRC.

Added finalpanic diagnostics with stage (handoff-stop/base/run,ready,gpt,
root-header,root-crc), command, OCS, UPIU response/status, fixed/descriptor sense,
and savedinterruptstatus. Failurehostregisters printed beforepanic.
Added explicit100ms handshake polling for async RSR stop/start andlistreadback
barriers; noPHY/linkreset, noSMMUreconfiguration ordiskwrites. Actualheader
xigua_ufs_handoff.h hosttested against delayedcontroller model plus stuckstop,
ignoredbase,stuckstart,outstandingDBR. 34hostchecks PASS; entireupdatedUFS C
crosscompile against realXNU ARM64 headers PASS (build/ufs-local-compile-2.log).
Need compile newkernel, build/install probe2, read finaldiagnostic iffailure.

Touchcandidate9ae4474 CI39999855589 BUILD SUCCESS incl HID C++/driver. This is
compile evidence only, touchOFF in UFSprobe1 and NOT hardwaretested. Need not
switch phone to a touchtest while UFS remains activepriority. 90daylegacyIIG
artifact bootstrap verified by thisCI too. Android read-onlyUFSreference:
diagnostics/android-ufs-reference-1.txt and android-ufs-qcom-1.txt. IOMMUgroup3
unmanaged, physicalSMMU15000000; no changes made. No inference that firmware's
IOMMU state matchesAndroid. LUN0driverflow still needs actual error values.

## UFS kernel39997597747 compiled and read-only probe SENT; touch candidate — 2026-10-23

macos15/Xcode16.4 + legacyIIG source cache BUILD SUCCESS. Commit496e2e7,
kernelSHA4bfd8d05034db22a6388025ad76c730680023046f112d7c36c6a04d1887942ff.
ZIPCRC+SHA verified artifacts/xigua-ci-39997597747. UFS MMIO disassembly
build/ufs-handoff-ci-39997597747.asm confirms plain no-writeback register ops.
Booted out/efi-ufs-probe-1/esp.img SHA
f13dd44a88ea4be818d40c0d7cffbec019fc44735ef51020990f6154cea302e4.
ADB found Android; rebooted recovery, backed up display2 ESP in
 diagnostics/ios-before-ufs-probe-1, restored original then BusyBoxdd installed
probe and fullreadback verified. Logs diagnostics/ufs-probe-1-esp-install.log,
ufs-probe-1-boot.txt/json. TemporaryMu fastbootboot OKAY. CPU6, tiny diagnostic
RAMroot, xiguaufs1 READONLY, no12GiB copy, no rootwrites. USER SCREEN RESULT
PENDING via async question; do not enable RW native root until READ CHECK PASS.

New OPT-IN touch candidate kernel/xigua_touch.c + xigua_tcm.h, generator
xigua_touch_overlay.py, hostCLI --touch (requires ios-userland + display-modefit).
GENISPI a90000 FIFO/polledGPIO25, only clockvotes+GPIO10power+GPIO24reset;
requires alreadyloadedSPI controller firmware, no PMIC or FWflash. TouchComv1
identification/maxwrite limits, chunked commands, appmode/start retries,
HBPrawdisable + LBP2 switch + configured report0x11. Decodes up to10 contacts,
scales rawcoords to1240x2772, emits existingnativeHID lifecycle/edgegestures.
SweetHID physicalpanel dims fromPE_Video, normalizesfullpanel fit correctly.
DefaulttouchOFF; current UFSprobe kernel does NOT include this newdriver.
33hostchecks PASS both workspace and publishedports. Added independent C
known-vector contact/bounds/lifecycle/chunk-reassembly test. Actualdriver local
ARM64 MachO crosscompile with generated XNUheaders PASS (not mockheaders),
build/touch-local-compile.log. Local HID C++ compile requires AppleClang type
summary builtins unavailable in LinuxClang; validate it in the next CI. Hardwaretouch
NOT TESTED. First nativeUFSboot should still keep touchOFF for isolated test.
Workflow now bootstraps IIG from90day xnu-iig-legacy artifact of39997597747,
removing dependency on old7day buildtree. No localQEMU started.

## Build runner brownout handled: macOS15 + verified legacy IIG cache — 2026-10-23

UFS CI39994662621 never got a runner. Found official GitHub macOS14 brownout
Oct23 14UTC-Oct24 00UTC (retirementNov2). Waiting on macos14 cannot progress.
Workflow moved to STANDARDmacos15 (free public runner), pins Xcode16.4.
Do NOT extendIORPC ABI just to satisfy newIIG. Instead tools/iig-legacy.py
reuses generatedh/cpp from successfulCI39662845808 xnu-buildtree (download23MB),
validates ALL34DriverKit sourceinputs SHA and everygeneratedfile SHA, emits17
sameABIinterfacepairs. Everyobject is rebuilt. Local prepare of ACTUALartifact
and generation ofIOService againstcurrentXNU source PASSEDbytecomparison.
Workflow downloads sourceartifact, cacheslegacyIIG17pairs as90dayartifact,
sets IIG/IIG_LEGACY_CACHE env. No old objects/kernelbinaryreused. Need newCI
result to assess remaining Xcode16 hostcompatibility. Initialrawsourcecache
expires7days; afterfirstsuccessfulnewCI updatebootstrap to90dayartifact.

UFSmodeimplementation31fefaa awaitingkernelcompile/hardwareprobe.32hostchecks
andEFIpackagingpassed. Added tools/collect_ufs_log.py (recoveryBusyBoxreadONLY,
linuxpartitiontailconsole decoder) for nativeUFSboot logs. Not run onphoneyet.
Touchadditionalfacts: actualDTcompatibleqcom,spi-geni =>Linuxspi-msm-geni.c,
notupstreamspi-geni-qcom.c. SynapticsS3910 LBP2 normalcoordinate reports
supported (disableHBP0x23report,setdynamicID0x11value2). GENI a90000,GPIO44-47
mux1; TLMMnodef000000 withperGPIOcontrolbase+100000=f100000. GPIO10powerhigh,
GPIO24resetlow10ms then80msdelay, GPIO25IRQlow. GCCbase100000:wrap1SE4clock
vote52008bit26 andwrapperAHBbits20/21;se4halt184e4. RawcoordsappinfoLE16at32/34,
DT19840x44352. ExistingSweetHIDtouchhardcodes1080/2400 andneedsXIGUAgeometry
adaptation before newSPI driver. Touch not yetcoded orhardwaretested.

## User orders UFS implementation + touch if possible — 2026-10-23

Explicit user instruction: DO IT, also implement touch if possible. This
supersedes waiting for display2 observation; current implementation task UFS,
then Synaptics S3910 SPI touch. No QEMU; tests directly on phone; fb>=30Hz.
Current USB/fastboot absent, phone may still be in display2 iOS. Manual recovery
will be needed once new image is ready. Do not ask redundant permission.

IMPLEMENTED candidate native UFS handoff in0082 via tools/xigua_ufs_overlay.py:
opt-in xiguaufs=1 read-only probe, =2 UFS root; default stays disabled.
Explicit register-only MMIO; lowDMA0xc4000000/2MiB (known conventional UEFI range)
reserved by AllocateAddress before EBS; emitted same DMA region in ADT.
XNU single Normal-NC mapping of firmware-owned DMA buffer, no highbank DMA or
invalid physical cache ops. Inherit live legacyUTP host state, report HCE/HCS/
CAP/version, validate list takeover, genericSCSI onLUN0. Require exact host
1d84000/3000, partitionname linux and known77137424384B capacity. No old PMIC,
Goodix or USB init onXIGUA. Writes allowed ONLY mode2+ufsrw1 and only inlinux.

Read-only probe compares first/middle/last4MiB of prepared12GiB root against
existing verifiedCRC cache (three checks,12MiB total); HFSXheader also verified.
IOFindBSDRoot triggers probe before tiny RAM-root init. No12GiB copy/no15minwait.
Host CLI --ufs-probe --ramdisk build/xigua-init/root-padded.img --ufs-crc-cache
artifacts/ios-20H392/root-12g/verified-crcs.json; --ufs-root --ios-userland selects
rd=ufsroot0, boundedRW, persistentconsole tail oflinux and processsampler.
Native root does NOT use baselineCRCs after iOS has modified filesystem.

Fullpatch applies cleanly.3 new small host checks pass (real C CRCprobe versus
independentzlib data, corruption/geometry rejects, ADT DMA/sample guards).
Full32checks + EFIshim pipeline being checked. out/host-ufs-* artifacts use
OLD kernel solely to compile/check host pipeline: DO NOT BOOT THOSE ON PHONE.
Next remotekernelCI, inspect result, build actual kernel probe/fullroot variants,
install probeESP via recoveryBusyBoxdd, temporaryMu boot, obtain READ CHECK PASS.
Do not install RW UFS root until actual readchecks pass. Rootlinux remains
original verified12GiB; preserveworkingESP2/display2 fallback. Bootpartitions
notflashed. Touch not yet implemented; sources under .cache/input-source/oneplus/.

## Linux UFS references acquired; no new phone changes — 2026-10-23

User can provide Linux kernel sources only. Official OnePlus Ace2Pro sources
suffice as reference for a native XNU UFS port; no promise of drop-in Linux
module. Downloaded13 UFS/PHY files (core ufshcd/HCI/UPIU, ufs-qcom, Kalama PHY)
from OnePlusOSS/android_kernel_oneplus_sm8550, branch
oneplus/sm8550_v_15.0.0_ace_2_pro, commit
fe53a93e64c6d6b01e68b8dbc35be235a0fe78b4. Local .cache/input-source/oneplus-kernel/;
SHA256/source manifest build/oneplus-ufs-source-ref.json. No kernel build/test
or device action for this acquisition. Existing modules/DT reference remains
82601baff20dde1770d62adc8da7a51474304bad. Actual liveUFS regs1d84000/3000,
1d88000/8000,1d90000/9000. Existing donor XNU UFS has generic legacyUTP/SCSI,
but remains disabled for XIGUA. DMA mapping/firmware handoff/host compatibility
must be checked before using it. First future storage milestone: read-only
partition reads with known checksums, then filesystem root. Do not rewrite
root or enable disk writes just from source availability.
Current phone test is STILL display2 CPU6/fit30; observation pending. Preserve
one-task ordering; don't reboot it to run UFS diagnostics while awaiting that.

## Display performance test2 SENT to phone — 2026-10-23

out/efi-ios-display-2/esp.img installed in recovery through BusyBox dd;
full SHA readback VERIFIED0920546fa5c32d0078ab907f9a6255f71637b504ddd33d68de7f0888b6029248.
First upload failed transient USB BEFOREdd, retry succeeded. Logs diagnostics/
ios-before-display-2.log, ios-display-2-esp-install.log (failed upload),
ios-display-2-esp-install-retry.log (verified success). Prior working CPU6 ESP
saved in diagnostics/ios-before-display-2/esp-after-probe.img (96MiB verified).
TemporaryMu fastbootboot SUCCEEDED, Sending/Booting OKAY:
diagnostics/ios-display-2-boot.txt/.json. CPU6/fb30/fitON, cachedcanvas+dirtytiles,
SAME proven-boot CI39662845808 with GICstride0x40000. Rootlinux untouched.
User observation pending: full-panel fit, visible redraw speed, possible panic.
Do not reboot or move on to inputs while waiting. Apple-logo15min cause still
UNMEASURED; old root leaves~960MiB managedRAM before further kerneloverhead.
No QEMU and no10Hz. One task at a time: finish display test before another.

## CPU6-configured iOS boots; display performance test prepared — 2026-10-23

User reports stride-fix build BOOTED iOS, calls it6cores/30Hz, but speed feels
unchanged and Apple-logo stage still takes15minutes. Root-copy stage is NOT
main delay (user explicit). No captured6/6line/runtimeCPU counters, so separate
user report from instrumented count. GIC panics no longer reported with this
CI39662845808 kernel. Current next single task: framebuffer performance/fit.

Read-only host root audit: migration/SpringBoard/Setup skip prefs are present
and correct; no evidence migration is the15minute cause. HFS root12GiB in13GiB
UEFI reservedRAM leaves960MiB before further kernel allocations (root starts
64MiB afterRAMbase); memory pressure plausible but UNMEASURED. No root edits.
Readonly mount unmounted. Private audits build/ios-root-size-audit.txt and
build/ios-system-library-size-audit.txt. No local QEMU, still forbidden.

FOUND current CPU6 image fitOFF: cached composition+changedtiles code already
compiled into successful kernel but inactive. Prepared new out/phone-ios-display-2
and out/efi-ios-display-2/esp.img using SAME CI39662845808 kernel/root, CPU6,
GICRstride0x40000, fb30, sweetfb_fit1. Embedded payload verified:1125x2436logical
canvas retained; output scaled to1240x2772physical. Enables cached canvas,
previousframe comparison and changed64pixel tile writes; initialfullclear.
ESP SHA0920546fa5c32d0078ab907f9a6255f71637b504ddd33d68de7f0888b6029248.
Rootlinux remains12GiBunchanged; bootpartitions notflashed. Phone foundAndroid
rootPJA110, bootmode=reboot; adb reboot recovery sent. Awaitrecovery, then
probe_device.py restore --output diagnostics/ios-before-display-2, install
--prepared-image out/efi-ios-display-2/esp.img; temporaryMu boot. Record actual
results before claiming improved speed. Boot15minutes still UNSOLVED; this
single test targets visible redraw/blackborders, then revisit startup/memory.
Do not start keys/touch or rewrite root while waiting for display observation.

## Stride-fix kernel ready; CPU6 hardware test3 — 2026-10-21

CI39662845808 SUCCESS, commit5f0e41364d83ca34820e78f74f4701c5cd151e00.
Kernel artifact CRC/SHA verified, SHA
177b33ca0c9bba1f626f1a196b9d56cf5db41bd39afb47aa76f184dfdb23c776.
Final linked pe_init_fiq verified: loads xigua_gicr_stride and uses it before
VLPIS fallback; no base-writeback MMIO. Disassembly saved under build/.
out/phone-ios-cpu6-stride-1 embedded payload (not only loose ADT) checked:
CPU6 realMPIDRs0..500, redistributor-stride uint64LE0x40000, fb30, fitOFF.
ESP out/efi-ios-cpu6-stride-1/esp.img SHA
3f8047535be6fc7133a697a990d337417c42d12b9892e87a6e064d27b3e7ff62.
Recovery PJA110 root confirmed, previous ESP saved diagnostics/
ios-before-cpu6-stride-1/esp-after-probe.img; original restored/fullSHAverified.
New ESP install PASSED full SHA readback, ios-cpu6-stride-esp-install-1.log.
TemporaryMu fastbootboot SUCCEEDED (Sending/Booting OKAY), logs
ios-cpu6-stride-boot-1.txt/.json. Await user CPU6/6+SGI1 or panic. No reboot after user observation until needed.
Root linux12GiB unchanged, boot partitions untouched. ONLY SMP task; NO QEMU,
NO10Hz; display fit/input deferred. Six working CPUs still NOT proven.

## CPU1 undefined LDR; missing live-DT redistributor stride fixed — 2026-10-21

MMIO-fix CI39659598333 hardware reaches CPU1, then panic Undefined kernel
instruction instr=f940016b, caller0xfffffe0007ad5170, sleh.c951. User PC
0xfffffe0007a77bf44 has extra digit; matching exact instruction in binary
at0xfffffe0007a77bf4 = pe_init_fiq+0x154, ldr x11,[x11], reading GICR_TYPER
in RD search. CPU0's previous writeback STR fault passed. No ESR/X11 visible
on this panic screen; don't ask user to transcribe entire backtrace.

FOUND omitted hardware fact: actual live.dtb GIC has redistributor-stride
64-bit BE <0 0x40000>, verified fdtget and Python parser. Our summarizer/profile/
ADT dropped this property. Prior scanner used VLPIS bit only, potentially
stepping0x20000 into unimplemented hole when firmware masks VLPIS. This
explains CPU1 failure, but full fix needs phone verification.

Now preserve stride through inspect_dtb -> make_profile -> little-endian ADT
property redistributor-stride -> XNU boot CPU parses/validates global stride,
scanner prioritizes it over VLPIS. No register-width/security bypasses.
Keep explicit no-writeback MMIO helpers. Bound whole RD+SGI frame in region.
Phone SMP profiles without stride are rejected to prevent reuse of old profile.
29 host checks pass, including FDT-node/profile/ADT stride propagation and
invalid/missing/out-of-range stride guards. No QEMU. Full0082 apply-check OK.

Fresh build/phone-ios-smp-stride-profile.json (also updated phone-ios-smp-profile)
regenerated from real live DT + verified UEFI report2; stride0x40000,8frames in
0x200000, fb verified flag retained. Kernel CI39662845808 running, commit5f0e413; remote host checks39662845912/39662845809 SUCCESS.
Next: CPU6/fb30/old
geometry fitOFF, completeESP via BusyBox dd in recovery, temporaryfastbootMu.
Root linux unchanged12GiB; boot partitions untouched. ONLY SMP task current.
Phone last on panic screen, no ADB/fastboot; manual recovery needed for newtest.

## MMIO-fix kernel verified; CPU6 hardware test2 — 2026-10-21

CI39659598333 SUCCESS, commit51ff437321e4a0503141cbb44486c391f9689b58.
Kernel ZIP CRC and SHA verified: 519914d9f57b0e55d7a4a27634326ed3a9ecffac9a58c70695bf62f463d8abfa.
Final linked pe_init_fiq disassembly checked: twelve 32-bit register-only STRs,
no pre/post-indexed base writeback. Saved build/pe-init-fiq-39659598333.asm.
27 host checks passed; no VM run. out/phone-ios-cpu6-mmio-1 verified against
new kernel SHA, ADT6 real MPIDRs0..500, cpus6, fb30, old geometry fitOFF.
ESP out/efi-ios-cpu6-mmio-1/esp.img SHA
b39dedb9e0b06aad50699e9cd876462e38051f967af46fa0ca5ecb1018e2c281.
Phone confirmed PJA110 recovery uid0; previous ESP6 saved in
 diagnostics/ios-before-cpu6-mmio-1/esp-after-probe.img, original restored and
verified. New ESP install PASSED full SHA readback: diagnostics/ios-cpu6-mmio-esp-install-1.log.
No root linux or boot partition writes. Temporary Mu fastboot boot SUCCEEDED;
Sending/Booting OKAY, diagnostics/ios-cpu6-mmio-boot-1.txt/.json.
Await hardware CPU6/6+SGI1 and iOS; fix is NOT yet hardware-proven. Only SMP
current task. NO QEMU, NO10Hz; display fit/input remain deferred.

## CPU6 repeats GIC abort; MMIO instruction fix — 2026-10-21

CPU6 attempt also PANICKED, same CI39654978298 PC0xfffffe0007a77c54;
reported ESR0x96000010, FAR0xfffffe030db60080. No CPU6 success; count reduction
alone did not fix anything. Panic is pe_init_fiq+0x1b4, str w9,[x8,#0x80]!,
GICR_IGROUPR0. Known-working CI39646487365 uses a register-offset STR without
base writeback instead. Candidate cause: EL2 MMIO emulation cannot decode
pre/post-indexed access (ISV=0), injecting synchronous external abort. Gunyah
upstream API explicitly limits emulation to single-register no-writeback loads/
stores: https://github.com/quic/gunyah-hypervisor/blob/develop/docs/api/gunyah_api.md
Firmware identity/cause NOT yet hardware-proven. Do not claim final fix yet.

0082 now routes ONLY XIGUA GIC MMIO through explicit single-register ldr/str
with register-only addresses and memory clobber. No security-group bypass,
no physical address change, no stride change. Header kernel/xigua_mmio.h is
staged as pexpert/arm64/XiguaMMIO.h. Added matched GICR affinity/offset/TYPER/VA
log for hardware evidence. One focused ARM Apple-target code-generation test
passes at O2/Os/O3 (rejects writeback/paired/unscaled accesses); full patch
applies cleanly. Build new kernel remotely, inspect final binary, then build
CPU6/30Hz/old geometry and ESP, install via recovery BusyBox dd. Root linux
unchanged12GiB; no boot flash; no QEMU; display/input still deferred.
Phone last on panic screen, no ADB at last check. Needs manual recovery.

## CPU6 hardware test sent — 2026-10-21

ESP6 installed through recovery BusyBox dd, full SHA readback verified:
08e2e3f36469accbb83e4460b1d8d39a726ef86eccf483286685f4cb88a00330.
Previous failed CPU8 ESP backed up in diagnostics/ios-before-cpu6-1/
esp-after-probe.img. Logs ios-before-cpu6-1.log, ios-cpu6-esp-install-1.log.
Temporary fastboot Mu boot SUCCEEDED: Sending OKAY0.027s, Booting OKAY0.342s.
Results diagnostics/ios-cpu6-boot-1.txt and .json are authoritative. SAME CI39654978298, cpus6/ADT6, fb30, fitOFF.
Root linux and boot partitions unchanged. Await actual CPU6/6+SGI1 and iOS
or next panic. CPU6 is not yet proven. If panic recurs, obtain FAR/ESR and
GIC target; do not keep varying CPU count blindly. No QEMU/no display work.

## CPU8 panic; CPU6 requested — 2026-10-21

User reported panic(cpu 0 caller 0xfffffe0007ad4df8): Kernel data abort,
pc 0xfffffe0007a77c54, lr 0xfffffe0007a77c44,
saved state 0xfffffe00080b3b40. Exact CI39654978298 symbolication:
pc = pe_init_fiq+0x1b4, instruction str w9,[x8,#0x80]!, writing
GICR_IGROUPR0 (redistributor+0x10080); caller sleh_synchronous_sp1.
FAR/ESR not available; cause NOT proven. Do not attribute to eight cores.
User permits six cores and points to donor's six A55 support. SM8550 has
other cores; donor's count does not prove an SM8550 limitation.

Prepared out/phone-ios-cpu6-1 and out/efi-ios-cpu6-1/esp.img, SAME kernel
CI39654978298 as failed CPU8. Only CPU selection differs: cpus=6,
ADT MPIDRs 0..0x500 verified, fb30, old geometry, fit OFF. This isolates
count; no GIC fix yet. Root linux unchanged. Phone observed Android root
PJA110; adb reboot recovery sent. ESP6 installation/boot pending.
Only current task SMP, target6 now acceptable. NO QEMU, NO10Hz, no inputs
or display work until SMP confirmed. Working oneCPU ESP2 preserved.

# XIGUA handoff — 2026-10-21

## СЕЙЧАС: только задача «8 ядер», тест уже запущен на телефоне

- Новое правило пользователя: по одной задаче до подтверждения работы, проверки
  сразу на телефоне. QEMU ЗАПРЕЩЁН и остановлен. Не работать сейчас над кнопками,
  тачем, USB или разрешением параллельно. Пользователь запретил возврат к10Гц.
- Порядок пересмотрен после вопроса о ядрах: СНАЧАЛА8CPU для скорости, затем
  размер/рамки картинки, затем ввод. Тест CPU8 сохраняет известный iPhone X
  canvas1125x2436 с рамками; framebuffer cap30Hz по требованию пользователя.
- Kernel CI39654978298 SUCCESS, commit20e9296, CRC/SHA проверены.
  SHA256 b74706cb0304704f0b5d06dae52f3dff85fddc643b4fe271b38e8d365b5062bc.
- ГОТОВ ДЛЯ ТЕЛЕФОНА: out/phone-ios-cpu8-1 (cpus8, fb30, display iphone-x),
  готовый96MiB ESP out/efi-ios-cpu8-1/esp.img. В payload проверены cpus=8,
  sweetfb_hz=30, восемь ADT CPU nodes, fit flag отсутствует. Hardware8CPU
  пока НЕ проверены. Старый kernel CI39646487365 работал на одном CPU.
- out/phone-ios-display-1 и out/efi-ios-display-1 тоже построены:1CPU/fit/30Hz,
  но это ОТЛОЖЕННЫЙ тест геометрии. НЕ устанавливать его вместо CPU8.
- Root linux прежний, полностью verified12GiB; НЕ пересобирать/не писать снова.
  tools/build_efi_boot.py --root-crc-cache принимает таблицу, связанную с root.json
  SHA/геометрией. artifacts/ios-20H392/root-12g/verified-crcs.json получен из
  loader-config ESP2, который уже загрузил этот root на аппарат с полным CRC.
  Это предотвращает повторное чтение12GiB на HDD при каждом новом ESP.
- Телефон кратко появился ADB (PJA110, ro.bootmode=reboot, uid0 KSU), затем
  пропал ДО adb reboot recovery. Команда reboot не отправлена. Ни ADB, ни
  fastboot не видны. Пользователю дано действие: подключить USB в recovery,
  async вопрос о режиме задан. ESP сейчас по-прежнему рабочий ESP2, не CPU8.
- Когда recovery появится: tools/probe_device.py restore --output
  diagnostics/ios-before-cpu8-1 (сохранит весь текущий ESP2 и восстановит original),
  затем install --prepared-image out/efi-ios-cpu8-1/esp.img. Install требует
  исходный ESP, поэтому restore необходим. Оба действия BusyBox dd, full SHA.
  Потом adb reboot bootloader, временно fastboot boot пользовательского
  /home/rajok/Загрузки/Telegram Desktop/Mu-xigua-0.img; журнал ios-cpu8-boot-1.txt.
  Не прошивать boot, не трогать linux. После boot проверить с пользователем
  строки XIGUA CPU:8/8 CPUs initialized,SGI1 verified и время запуска iOS.
- Keys/touch ИССЛЕДОВАНИЕ ОТЛОЖЕНО. Файлы .cache/input-source (официальные
  Linux/OnePlus), refs build/oneplus-source-ref.json/tree.json. Важная поправка:
  PMK8550 PON1310 bit7=power,bit6=Linux115 volume-up; PM8550GPIO6 RT8d10 active
  low = Linux114 volume-down (несмотря на label vol_up). SPMIv7 map core+2000,
  owner cnfg+4*apid, observer stride20, EE stride8000, bus0 apid count core+4.
  Не реализовывать сейчас; вернуться после CPU и экрана.

## Текущие требования после первого GUI

- НАСТОЯЩИЙ АППАРАТНЫЙ GUI ПОДТВЕРЖДЁН: пользователь увидел экран блокировки
  iOS с красными часами после Apple logo -> чёрного экрана. Kernel1d5c416,
  CI39646487365, ESP out/efi-ios-ram-2, root linux verified12GiB.
- Пользователь просит исправить размер интерфейса, очень медленную/видимую
  отрисовку, включить хотя бы 6 или 8 CPU. Сообщил: тач и все кнопки не работают.
  Новая работа: SMP8 + framebuffer/layout/performance + кнопки + Synaptics SPI.
  Автозагрузку пока не устанавливать, сначала улучшить рабочую сборку.
- ПРЯМОЙ ЗАПРЕТ ПОЛЬЗОВАТЕЛЯ: выключить локальный QEMU, расходует ресурсы ноутбука.
  Все QEMU остановлены, проверено active=[]; backing qemu-ios-memory-1..4.bin
  удалены. БОЛЬШЕ QEMU НЕ ЗАПУСКАТЬ. Kernel собирать в GitHub Actions, локально
  допустимы небольшие проверки кода/профилей. Никакие таймеры QEMU не оставлены.
- Телефон остаётся в iOS, USB/ADB и кнопки в XNU пока не реализованы. Для новой
  записи ESP потребуется ручной перевод пользователем в recovery с ADB.
- Проверено по live DT: CPU MPIDR 0,0x100,...,0x700; PSCI1.0 method smc.
  Текущий kernel SMP limit1, ADT1CPU, command cpus=1. Donor SMP8 уже умеет
  эти MPIDR; нужно убрать лимит XIGUA, добавить CPU nodes в наш ADT/CLI.
- GICR scanner сейчас фиксированно шагает0x20000. Для SM8550 следует учитывать
  VLPIS bit1 в GICR_TYPER (stride0x40000), сохраняя границы региона.
- Framebuffer сейчас логический1125x2436, панель1240x2772, центрируется без
  масштабирования. Default10Hz. Canvas disp0 тоже1125x2436 (НЕ1080x2400).
  sweetfb_native=1 есть в доноре, но неизвестный UIKit screen class способен
  показывать red rdar banner. Нужно решить fit/native по ответу пользователя:
  задан вопрос: поля/обрезано/неверные пропорции. Есть write-combine mapping.
- Исходники для ввода: live DT содержит PMIC arb v7 layout: core c400000/3000,
  cnfg c42d000/4000, observer c440000/80000, chnls c500000/400000, ee0,bus0.
  PM8550 SID1 GPIO6 volume-up; PMK8550 SID0 PON. Нужен точный PN RT layout.
  Тач активный synaptics,tcm-spi-hbp at a90000, S3910, IRQ TLMM25 active-low,
  reset TLMM24, AVDD TLMM10, SPI19MHz, mode0. Старый synaptics-s3910 disabled.
  Не активировать чужие SM7150 драйверы.
- Официальные исходники для исследования: torvalds/linux drivers/spmi/
  spmi-pmic-arb.c и OnePlusOSS/android_kernel_modules_and_devicetree_oneplus_sm8550.
- Последний публичный commit f8f9845 (ещё только reported launch, нужно обновить
  milestone до подтверждённого lock screen). 0082 локально совпал с CI1d5c416;
  sampler BSD-hook был отменён до commit/CI. Новых изменений kernel пока нет.

## Актуальное состояние: пользователь сообщил запуск iOS на телефоне

- Root iOS 20H392, 12 GiB записан в linux и полностью проверен readback SHA-256:
  diagnostics/ios-root-install-2/verified.json. SHA-256
  7ed76a14da8d9bf21ceb2d3f62c2524492e0ec30a3405128ca0c7879322fd7df.
- Новый kernel 1d5c416 / CI 39646487365 SUCCESS исправляет memdev >4 GiB.
  QEMU подтвердил HFS+ mount, Apple launchd и exec SpringBoard; GUI не доказан.
- out/efi-ios-ram-2/esp.img установлен в ESP через recovery BusyBox dd;
  полный SHA-256 проверен: diagnostics/ios-esp-install-1.log.
  Оригинальный ESP сейчас НЕ установлен. Резервная копия сохранена.
- Телефон перезагружен из recovery в fastboot и временно загружен
  Mu-xigua-0.img. Fastboot Sending/Booting OKAY: diagnostics/ios-boot-1.txt.
  Пользователь подтвердил счётчик загрузки iOS по 1 GiB в RAM: UEFI читает root.
  Затем пользователь сообщил Apple logo без полосы, потом чёрный экран,
  затем успешный запуск iOS (пользователь радовался запуску). Уточняется,
  какой именно интерфейс появился и работает ли касание. Фото/логи не получены.
  Это первая аппаратная попытка с настоящим root iOS. Вопрос о типе экрана
  (рабочий стол/блокировка/Setup) и касаниях задан. Телефон не перезагружать.
- Не перезагружать телефон и не восстанавливать ESP, пока пользователь сообщает
  наблюдения. Boot_a/boot_b не прошивались. Автозагрузка из boot ещё не сделана.
- Исходники предыдущего исправления: 12e0ac2. После успешного аппаратного GUI
  вернуться к цели автозагрузки из boot. Touch/USB/UFS SM8550 ещё не реализованы.

## Цель и ограничения

Автозагрузка iOS на Ace 2 Pro из boot; dual boot позже. Пользователь разрешил
использовать esp, installer, linux. ESP записывать готовым образом через dd в
recovery; монтировать разделы через BusyBox. Не прошивать образы QEMU на телефон.

## Телефон

- Подключение после перезапуска восстановлено. Fastboot подтвердил unlocked=yes,
  current-slot=a, product=kalama. В boot ничего не записывалось.
- Временно выполнен fastboot boot Mu-xigua-0.img; EFI probe сохранил отчёт и
  вернул телефон в Android. Далее adb reboot recovery.
- diagnostics/uefi-phone-1/ содержит полный ESP после пробы и xigua-probe-*.txt.
  Оригинальный ESP восстановлен через /sbin/busybox dd в recovery; SHA-256 совпал
  с backup/initial/manifest.json. ESP больше не содержит временной пробы.
- Отчёт подтвердил EL1, TGran16=1, CNTFRQ=19200000, MPIDR affinity=0,
  GOP BGR framebuffer b8000000, 1240x2772, stride4960, size13749120.
- build/phone-profile.json выбирает кандидат RAM 0x880000000/512MiB по DT+UEFI.
  Native TEST 02 подтвердил запись/чтение страницы 16 КиБ по 0x881000000
  и вывод framebuffer под ABL (пользователь подтвердил TEST 02 / RAM PASSED).
  Остальные 512 МиБ этой проверкой не покрыты.
- Аппаратный XNU подтверждён пользователем: init running as PID 1 и повторяющийся
  heartbeat. Образ out/phone-xnu-ramroot-1/boot.img, kernel CI 39631591118.
- EFI-проба v2: diagnostics/uefi-phone-2/. Успешное выделение всех 13 GiB
  [0x8c0000000,0xc00000000), проверка трёх страниц, чтение ESP/installer/linux.
  Оригинальный ESP снова восстановлен через BusyBox dd с проверкой SHA-256.
- Телефон в recovery. UEFI stager с маленьким root был временно загружен;
  пользователь сообщил логи XNU и затем сам перезагрузил телефон. Причина
  возврата в Android — ручная перезагрузка. PID 1 под UEFI отдельно не подтверждён.
  Затем ESP восстановлен побайтно: diagnostics/efi-native-test-2-restored/.
  Пользователю обещано: следующий запуск на телефоне уже с настоящим root iOS.
- 22 резервные копии загрузочных разделов/калибровок проверены. Boot/recovery/
  init_boot/vendor_boot/userdata/GPT не прошивались.

## Исходники и CI

- Донор: 425b25102b6a9ee4b68fb2b9ca5d6a086b8a4116.
- Форк x9hw32/ios-sweet, main и xigua-bringup: dded2cb (новое ядро CI 39637551537).
- Патч 0082 добавляет XIGUA. 0001–0082 применяются последовательно.
- CI 39626328183 остановилась до компиляции на дублирующем TrustCache.patch.
  Исправлено: обязательны номерные патчи; необязательные патчи инструментария
  могут пропускаться как в доноре. CI 39629480987 не собрала HFS/BearSSL из-за SWEET-only make guards.
  Исправлено в 7c704f2. CI 39631591118 успешно собрала kernel.development.xigua;
  артефакт скачан и SHA-256 проверен в artifacts/xigua-ci-39631591118/.
- Host CI 39634141927 и 39634141289 прошли: все 14 проверок.
- GitHub CLI: .cache/gh-cli/gh_2.102.1_linux_amd64/bin/gh, авторизован x9hw32.
  Не выводить и не копировать токены в репозиторий.

## Проверено локально

- EFI probe ARM64 PE/COFF (6144 байта): QEMU, FAT-отчёт, холодный reset.
- Донорский kernel 0081 из CI 39158169212: QEMU, RAM-root, PID 1 и heartbeat.
  Доказательство: build/qemu-baseline/run/fb.txt и result.json.
- Native diagnostic shim: Linux Image entry, CPU/FDT, отказ на пустом payload.
  Boot v4 около 80 КиБ; ELF без relocations. Это образ для QEMU.
- 22 теста границ payload/профиля и ограничений записи ESP/linux проходят.
- Наше kernel.development.xigua + native shim в QEMU: PID 1 и heartbeat,
  no_panic_observed, unknown_glyphs=0 (build/qemu-native-xigua/result.json).
- Аппаратный XNU + статический PID 1 работают. Apple launchd, iOS root, GUI
  и SM8550 UFS-драйвер пока не проверены.
- tools/build_test_init.py создаёт собственный init с XIGUA в сообщениях и подписи.
  QEMU out/qemu-xigua-init-2 подтвердил PID 1 и XIGUA heartbeat без panic.

## Продолжить

1. XIGUA CI и native QEMU PID 1 уже проверены; не повторять без изменения ядра.
2. EFI-проба выполнена, ESP восстановлен. TEST 02 прошёл на телефоне;
   журнал fastboot: diagnostics/native-diag-2-boot.txt.
3. UEFI stager + native XNU PID 1 проверены в QEMU: build/efi-qemu-test-2/.
   Чтение отдельного GPT-раздела с 4K секторами и CRC тоже прошло до PID 1:
   build/efi-qemu-external-root-1/. Новое ядро dded2cb + 13 GiB RAM с резервом
   первых 12 GiB + HFS+ root на верхнем краю загрузило PID 1 без panic:
   build/efi-qemu-large-hfs-5/. Варианты 1–4 отклонены EFI до исполнения XNU,
   потому что диапазон перекрывал реальные allocations самой QEMU EFI.
   Вариант 5 использует найденный по карте свободный диапазон.
   Вариант 6 проверяет чтение через DMA bounce-buffer ниже 4 GiB и CRC назначения.
4. Apple iPhone X 20H392 IPSW полностью скачан: artifacts/ios-20H392/.
   apfs-fuse собран в build/apfs-fuse; hfsprogs в .cache/hfsprogs.
5. Создать HFS+ root iOS (цель 12 GiB), записать только в выделенный linux из recovery.
   UEFI читает его в RAM, XNU использует md0. Не включать SM7150 UFS/USB/touch.
6. kernel/0082 обновлён: XIGUA-префиксы, iPhone X canvas на большем экране.
   CI 39637551537 успешно собрала ядро dded2cb. Скачано выборочно из ZIP артефакта
   с проверкой CRC и SHA256: artifacts/xigua-ci-39637551537/.
7. tools/prepare_ios_root.py --wait-download уже запущен и сам начнёт сборку
   после завершения aria2; лог artifacts/ios-20H392/prepare-root.log.
   build/phone-ios-ram-profile-verified.json получен из probe v2 через --large-ram.
   out/phone-ios-ram-1/ содержит native image под новый kernel + 12 GiB root.
   Не грузить напрямую: сначала UEFI обязан прочитать root в RAM.
8. Для записи root использовать tools/install_ios_root.py только в recovery:
   проверяет HFS+, хеш/размер, boot/ESP backups, mapping, mounted aliases;
   BusyBox iflag=fullblock поддерживается и проверен. Не писать до готового root.json.

## Настоящий iOS root — 2026-10-21

- 12 GiB HFS+ root собран из полного Apple IPSW (20H392); launchd, dyld,
  shared cache проверены, root tweaks применены. Финальный fsck -f -n: OK.
  Свободно 413 MiB. root.json готов; SHA-256 всех входов и root рассчитаны.
- Реальный root запущен в file-backed QEMU: build/qemu-ios-1/.
  build/qemu-ios-live-2/console.txt: md0 зарегистрирован с размером 12 GiB,
  но hfs_mountfs отказал (EINVAL), поэтому launchd ещё не запущен.
- Найдена причина: bsd/dev/memdev.c сдвигает uint32_t mdSize на 12 бит до
  расширения; 12 GiB превращаются в ноль. Исправляется продвижением в uint64_t
  до сдвига в strategy/ioctl/raw IO; raw IO также ограничивает count до INT_MAX.
  Патч 0082 обновлён (1d5c416). CI 39646487365 собирается; 22 host checks OK.
  Нужна повторная QEMU-проверка полного root новым ядром.
- out/efi-ios-ram-1 строится со старым ядром; НЕ устанавливать его на телефон.
  После нового ядра пересобрать native Image и ESP в новых каталогах.
- Телефон остаётся в recovery. Установщик root запущен, сначала проверяет хеши
  backups и самого образа; diagnostics/ios-root-install-1.log. Следующий аппаратный boot
  должен использовать настоящий root, после исправления выявленной ошибки.

## Новое ядро и Apple launchd

- CI 39646487365 SUCCESS, commit 1d5c416, kernel SHA-256
  6cd000a67efa88fce45cc658c79daa1434ac40973397baeef569b6828b43abb3.
- out/phone-ios-ram-2 и out/qemu-ios-2 используют исправленное ядро.
  out/efi-ios-ram-2 собирается с полным root и новым native Image.
- Реальный root в QEMU: HFS+ смонтирован; exec launchd; Early boot complete;
  exec SpringBoard (build/qemu-ios-live-6/console.txt). GUI ещё не подтверждён.
  QEMU временно остановлен через QMP после capture, чтобы ускорить проверки
  на HDD. Перед продолжением отправить QMP cont; тест завершится через 600 s
  от запуска (build/qemu-ios-2, backing build/qemu-ios-memory-2.bin).
- Первый root installer остановился ДО записи: adb exec-out смешал dd stderr
  со stdout в metadata backup. Исправлено на shell -T (protocol v2).
  Проверено на телефоне: бинарная копия ровно 1048576 байт. 22 tests OK.
- Повторный installer: diagnostics/ios-root-install-2.log и каталог -2.
  Пока считает root SHA; ESP/boot всё ещё не менялись.

## Root записан и проверен на телефоне

- diagnostics/ios-root-install-2/verified.json: 12884901888 bytes записаны только
  в /dev/block/by-name/linux; полный readback SHA-256 совпал:
  7ed76a14da8d9bf21ceb2d3f62c2524492e0ec30a3405128ca0c7879322fd7df.
- ESP out/efi-ios-ram-2/esp.img готов (96 MiB), SHA-256
  6c61b1eee1237d85b65f0f80b78bee5c7433bb2fa2c6ab9760cf8ee6d899e603.
  Install запущен: diagnostics/ios-esp-install-1.log. После его проверки
  временно fastboot boot Mu-xigua-0.img, никакой прошивки boot.
- QEMU закончил snapshot по таймеру, пока был приостановлен для передачи root.
  result.json: no_panic_observed; это НЕ доказательство GUI. Полный console
  build/qemu-ios-live-7: Apple launchd, exec SpringBoard; GUI не подтверждён.
- Остаточные APFS FUSE mounts /tmp/tmp.qdasOfBpop/* размонтированы.

## После появления Apple logo

- Пользователь подтвердил логотип Apple на телефоне после загрузки root в RAM.
  Не выдавать логотип за успешный рабочий стол. Ждём полосу/дальнейший экран.
- В доноре NOTES.md описан Apple logo + progress bar, отрисованный backboardd
  во время DataMigration; там подготовка заняла около часа. Наш root уже имеет
  migration skip preferences, поэтому нельзя считать это той же причиной без
  наблюдения полосы или логов.
- Независимый QEMU повтор с настоящим root запущен на 1200 s без пауз:
  build/qemu-ios-3, backing build/qemu-ios-memory-3.bin, native out/qemu-ios-2,
  kernel CI39646487365, tool session 48157. IO priority idle; телефон не трогаем.
  Первый capture: build/qemu-ios-live-8, дошёл до HFS initialization.

## После сообщения об успешном запуске

- Пользователь: Apple logo без полосы -> чёрный экран -> сообщение об успешном
  запуске iOS. Точный экран и работоспособность ввода ожидают уточнения.
- Из Android/fastboot телефон не появился (read-only adb/fastboot check).
  Нельзя удалённо перезагрузить его: драйвер USB SM8550 в XNU не реализован.
- Образ для будущей автозагрузки подготовлен: out/phone-autoboot-1/boot.img,
  точная копия пользовательского Mu-xigua-0.img (boot v4, 1.1 MiB), который
  только что временно загрузил эту конфигурацию. build.json и SHA256SUMS рядом.
  Backup boot_a/boot_b повторно проверены. НИЧЕГО в boot пока не прошито.
  Для следующего этапа пользователь должен физически вернуть телефон в fastboot;
  сейчас дать посмотреть iOS, не просить разрешение заново на уже заданную цель.
- RAM-root изменения теряются после reboot, сенсор/USB/нативный UFS не перенесены.
- Попытка добавить sampler BSD-hook отменена до CI: пользователь сообщил запуск,
  текущий проверенный kernel менять не стали. Патч 0082 cmp совпал с CI1d5c416.
- QEMU --private-memory реализован: guest changes не пишутся обратно в файл;
  полный console снимать через capture_qemu.py ПОКА VM ЖИВА. 22 checks OK.
  QEMU4 (tool13291) private memory, out/qemu-ios-2, build/qemu-ios-4,
  build/qemu-ios-memory-4.bin; capture14 дошёл до backboardd IOKit lookups.
  QEMU3 остановлен вручную из-за 11 GiB mmap writeback на HDD (не panic).

## Аппаратный CPU8 тест1 отправлен

- Recovery появился сам после переподключения. Прежний рабочий ESP2 целиком
  сохранён в diagnostics/ios-before-cpu8-1/esp-after-probe.img; затем original
  ESP восстановлен и проверен, чтобы пройти install guard.
- Новый ESP CPU8 установлен, full SHA verified:
  5a682a7ba10f511479da05f085ef51c298e5f1ffc27eb5ea36e7be8dbb09b4f0.
  Логи ios-before-cpu8-1.log, ios-cpu8-esp-install-1.log.
- Временный fastboot boot Mu-xigua-0.img отправлен SUCCESS (Sending/Booting OKAY),
  diagnostics/ios-cpu8-boot-1.txt и .json. Kernel39654978298, cpus8, fb30,
  iphone-x geometry, fit DISABLED. Root linux не менялся. Boot не прошивался.
- Пользователю сообщён критерий: XIGUA CPU:8/8 CPUs initialized, SGI1 verified.
  Async вопрос о root-copy /8CPU/CPU-PSCI-panic/iOS открыт. ЕЩЁ НЕ ПОДТВЕРЖДЕНО8CPU.
- Не трогать телефон, пока он наблюдает текущую попытку. Никакого QEMU.
  До подтверждения8CPU не переходить к размеру картинки или вводу.
