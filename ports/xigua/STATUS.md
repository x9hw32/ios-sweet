# XIGUA handoff — 2026-10-21

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
4. Скачивается Apple iPhone X 20H392 IPSW: artifacts/ios-20H392/; aria2 resume.
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
