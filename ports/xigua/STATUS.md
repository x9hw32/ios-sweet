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
- TEST 02 автоматически вернулся в Android. Затем через fastboot boot отправлен
  out/phone-xnu-ramroot-1/boot.img: Sending/Booting OKAY, результат экрана ожидается.
- 22 резервные копии загрузочных разделов/калибровок проверены. Boot/recovery/
  init_boot/vendor_boot/userdata/GPT не прошивались.

## Исходники и CI

- Донор: 425b25102b6a9ee4b68fb2b9ca5d6a086b8a4116.
- Форк x9hw32/ios-sweet, main и xigua-bringup: f9e98ef (ядро 7c704f2).
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
- 14 тестов границ payload, пересечений RAM и профиля проходят.
- Наше kernel.development.xigua + native shim в QEMU: PID 1 и heartbeat,
  no_panic_observed, unknown_glyphs=0 (build/qemu-native-xigua/result.json).
- Аппаратной загрузки XNU, SM8550 UFS, iOS root и интерфейса пока нет.

## Продолжить

1. XIGUA CI и native QEMU PID 1 уже проверены; не повторять без изменения ядра.
2. EFI-проба выполнена, ESP восстановлен. TEST 02 прошёл на телефоне;
   журнал fastboot: diagnostics/native-diag-2-boot.txt.
3. out/phone-xnu-ramroot-1/boot.img собран с нашим XIGUA-ядром и статическим init.
   Временная загрузка отправлена; получить экран. Аппаратный XNU пока не подтверждён.
