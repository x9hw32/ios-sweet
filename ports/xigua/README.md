# XNU / iOS для OnePlus Ace 2 Pro (PJA110, xigua)

Экспериментальный перенос [ios-sweet](https://github.com/dipa-studio/ios-sweet)
на SM8550. Цель: сначала автозагрузка iOS из boot, dual boot позже.
**На телефоне работают XNU и тестовый PID 1. Настоящий iOS root с Apple launchd запускается в QEMU. На телефоне пользователь подтвердил логотип Apple; рабочий стол ещё не подтверждён.** Образы qemu-* предназначены для эмулятора.
Текущее состояние, CI и продолжение работы — в [STATUS.md](STATUS.md).

## Подтверждено на телефоне

- SM8550, 16 ГБ RAM, активный слот _a. Оба boot: 201326592 байта (192 МиБ), header v4.
- esp: 96 МиБ FAT32; installer: 6899630080 байт; linux: 77137424384 байта.
  Эти три раздела пользователь выделил под порт.
- GICD: 0x17100000/0x10000; GICR: 0x17180000/0x200000; virtual timer: INTID 27.
- Основная RAM выше 32 ГиБ физического адресного пространства. UEFI зарезервировал
  непрерывные 13 ГиБ и проверил три страницы; работа всего диапазона под XNU
  на телефоне ещё не подтверждена. Touch — Synaptics TCM HBP через SPI 0xa90000.
- Пользователь проверял Mu-xigua-0.img. Android сообщает locked/green при root и
  кастомном ядре; fastboot подтвердил unlocked=yes.

**Условие пользователя:** ESP записывать готовым образом через dd в recovery.
Монтирование разделов — через BusyBox. Утилита ESP требует recovery и /sbin/busybox.

## Подготовлено

- 22 резервные копии загрузочных разделов, recovery и калибровок, полный ESP.
  Размеры и SHA-256 сверены с телефоном; файлы в backup/initial/.
- Live DTB и аппаратный отчёт в diagnostics/ace2pro-verified/.
- Отдельная конфигурация XIGUA: один CPU, plain arm64, RAM-root. Для неё отключены
  обращения к framebuffer Redmi, его UFS/input/USB/дисковым логам и реальному PMIC.
- EFI-проба снимает CPU, UEFI memory map и GOP в xigua-probe-*.txt на ESP, затем
  делает холодный reset. Boot Services остаются активны; GOP ещё не доказывает
  обновление панели после выхода из UEFI. Native TEST 02 подтвердил вывод под ABL
  и запись/чтение одной страницы RAM на реальном телефоне.
- Native shim содержит XNU payload внутри Linux Image, проверяет все границы
  копирования и передаёт ADT/boot_args. UFS/USB/touch он не трогает.
- EFI-проба и native shim проверены в QEMU. Донорское и наше XIGUA-ядро
  смонтировали RAM-root, запустили тестовый PID 1 и heartbeat. 22 проверки границ памяти, профиля и ограничений записи проходят.

Форк: [x9hw32/ios-sweet, xigua-bringup](https://github.com/x9hw32/ios-sweet/tree/xigua-bringup).
Apple IPSW, образы iOS, дампы и идентификаторы устройства исключены из git.

## EFI-проба на телефоне

```bash
python3 tools/build_efi_probe.py
# Только recovery с ADB; ESP должен совпадать с исходной резервной копией:
python3 tools/probe_device.py install
```

Утилита создаёт out/efi/esp-probe.img из backup, заменяя EFI/BOOT/BOOTAA64.EFI,
проверяет EFI-файл внутри FAT и записывает образ строго в /dev/block/by-name/esp
блоками 4096 байт через BusyBox dd. SHA-256 проверяется после передачи и записи.

После временной загрузки Mu UEFI проба должна сохранить отчёт и вернуть обычную
загрузку. Снова войти в recovery и выполнить:

```bash
python3 tools/probe_device.py collect-restore --output diagnostics/uefi-run-1
```

Сначала весь текущий ESP и отчёт сохраняются на ПК, затем оригинальный ESP
восстанавливается побайтно. Восстановление выполняется и без отчёта; неполное
чтение ESP останавливает операцию до записи. Форматирование и GPT не используются.

## Native boot image

```bash
python3 tools/bootstrap.py
python3 tools/make_profile.py --dtb diagnostics/ace2pro-verified/live.dtb \
  --probe diagnostics/uefi-run-1/xigua-probe-REPORT.txt --output build/phone-profile.json
python3 tools/build_boot.py --profile build/phone-profile.json \
  --stock-boot backup/initial/boot_a.img --output out/phone-diag \
  --experimental-abl-framebuffer
```

Профиль проверяет поддержку 16 КиБ, выбирает кандидат RAM по пересечению live DT
и UEFI ConventionalMemory, исключая известные резервы. Профиль из новой EFI-пробы
по умолчанию считает вывод под ABL непроверенным. TEST 02 держит экран 45 секунд
и проверяет запись/чтение одной страницы RAM. После рабочего вывода добавить
--kernel PATH --ramdisk PATH для RAM-root. Образ ограничен 192 МиБ.
Финальную установку в boot_a выполнять после временных загрузок; boot_b сохранить.

## Проверки на ПК

```bash
python3 -m unittest discover -s tests -v
python3 tools/make_profile.py --qemu --output build/qemu-profile.json
python3 tools/build_boot.py --profile build/qemu-profile.json --output out/qemu-diag
python3 tools/test_native_qemu.py out/qemu-diag/Image build/qemu-diag-test --secs 5
```

Зависимости: Python 3, git, adb/fastboot, mtools, mkbootimg, GNU AArch64 toolchain,
clang/lld, QEMU. XNU собирается на macOS через GitHub Actions с Xcode 15.

## Настоящий root iOS через UEFI

Для первого запуска системные файлы iPhone X 20H392 копируются в HFS+ root
размером 12 ГиБ. Root хранится в выделенном linux; UEFI читает его в RAM
и проверяет CRC каждого блока 4 МиБ. XNU использует md0. Изменения в таком
RAM-root сохраняются только до перезагрузки; драйвер UFS SM8550 — отдельный этап.

- tools/prepare_ios_root.py проверяет BuildManifest/ZIP CRC, создаёт root и root.json.
- tools/make_profile.py --large-ram требует успешную пробу выделения RAM из EFI v2
  и проверяет всю область по DT, EFI memory map и списку резервов.
- tools/build_boot.py --ios-userland --external-ramdisk-base PA --external-ramdisk-size SIZE
  подготавливает native Image с резервом для root. Он требует предварительной
  загрузки root через UEFI; прямой fastboot boot такого образа не используется.
- tools/build_efi_boot.py создаёт полный ESP из резервной копии, native Image
  и EFI-загрузчика. Никаких записей на телефон эта сборка не делает.
- tools/install_ios_root.py записывает проверенный root только в linux из recovery
  через BusyBox и проверяет SHA-256 чтением всего записанного диапазона.
- tools/probe_device.py install --prepared-image PATH устанавливает готовый ESP.
  tools/probe_device.py restore --output PATH сохраняет текущий ESP и возвращает оригинал.

Boot/root/ESP образы и Apple-компоненты исключены из git.
