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
