/* SPDX-License-Identifier: BSD-2-Clause
 * Read-only UEFI stager: reserve RAM, load/verify native Image and optional
 * raw root image, then ExitBootServices. No Block I/O writes are implemented.
 */
#include <Uefi.h>
#include <Protocol/LoadedImage.h>
#include <Protocol/SimpleFileSystem.h>
#include <Protocol/BlockIo.h>
#include <Protocol/PartitionInfo.h>
#include "loader-config.h"

static EFI_SYSTEM_TABLE *st;
static EFI_GUID loaded_guid = EFI_LOADED_IMAGE_PROTOCOL_GUID;
static EFI_GUID fs_guid = EFI_SIMPLE_FILE_SYSTEM_PROTOCOL_GUID;
static EFI_GUID block_guid = EFI_BLOCK_IO_PROTOCOL_GUID;
static EFI_GUID part_guid = EFI_PARTITION_INFO_PROTOCOL_GUID;
extern VOID enter_native(UINTN image, UINTN fdt) __attribute__((noreturn));

static VOID say(CONST CHAR16 *s) { st->ConOut->OutputString(st->ConOut, (CHAR16 *)s); }
static VOID number(CONST CHAR16 *name, UINT64 n)
{
    CHAR16 value[19] = L"0x0000000000000000";
    CONST CHAR16 digits[] = L"0123456789abcdef";
    for (UINTN i = 0; i < 16; i++) value[2+i] = digits[(n >> ((15-i)*4)) & 15];
    say(name); say(value); say(L"\r\n");
}
static VOID bytes_zero(VOID *p, UINTN n)
{
    volatile UINT8 *b = p;
    while (n--) *b++ = 0;
}
static UINT32 be32(UINT32 n) { return __builtin_bswap32(n); }
static int name_is(CONST CHAR16 *name, CONST CHAR16 *wanted)
{
    for (UINTN i = 0; i < 36; i++) {
        if (name[i] != wanted[i]) return 0;
        if (!wanted[i]) return 1;
    }
    return 0;
}

static EFI_STATUS read_root(EFI_BOOT_SERVICES *bs)
{
    if (!ROOT_BYTES) return EFI_SUCCESS;
    EFI_HANDLE *handles = NULL;
    UINTN count = 0, found = 0;
    EFI_BLOCK_IO_PROTOCOL *selected = NULL;
    EFI_STATUS status = bs->LocateHandleBuffer(ByProtocol, &block_guid, NULL, &count, &handles);
    if (EFI_ERROR(status)) return status;
    for (UINTN i = 0; i < count; i++) {
        EFI_PARTITION_INFO_PROTOCOL *part = NULL;
        EFI_BLOCK_IO_PROTOCOL *block = NULL;
        if (EFI_ERROR(bs->HandleProtocol(handles[i], &part_guid, (VOID **)&part)) ||
            part->Type != PARTITION_TYPE_GPT || !name_is(part->Info.Gpt.PartitionName, ROOT_NAME)) continue;
        if (EFI_ERROR(bs->HandleProtocol(handles[i], &block_guid, (VOID **)&block)) ||
            !block->Media || !block->Media->LogicalPartition || !block->Media->MediaPresent) continue;
        if (block->Media->BlockSize != ROOT_BLOCK_SIZE ||
            block->Media->LastBlock != ROOT_PARTITION_BYTES / ROOT_BLOCK_SIZE - 1 ||
            block->Media->IoAlign > 4096) continue;
        selected = block; found++;
    }
    bs->FreePool(handles);
    if (found != 1) return EFI_NOT_FOUND;
    // Keep storage DMA below 4 GiB. Copy into the reserved high-RAM root using
    // firmware services, then verify the destination rather than assuming the
    // device can DMA into every CPU-addressable physical bank.
    EFI_PHYSICAL_ADDRESS transfer = 0xffffffff;
    status = bs->AllocatePages(AllocateMaxAddress, EfiLoaderData, ROOT_CHUNK / 4096, &transfer);
    if (EFI_ERROR(status)) return status;
    say(L"Reading and checking iOS root into RAM\r\n");
    for (UINTN offset = 0, index = 0; offset < ROOT_BYTES; index++) {
        UINTN length = ROOT_BYTES - offset;
        if (length > ROOT_CHUNK) length = ROOT_CHUNK;
        VOID *destination = (VOID *)(UINTN)(ROOT_BASE + offset);
        status = selected->ReadBlocks(selected, selected->Media->MediaId,
                                     offset / ROOT_BLOCK_SIZE, length, (VOID *)(UINTN)transfer);
        if (EFI_ERROR(status)) break;
        bs->CopyMem(destination, (VOID *)(UINTN)transfer, length);
        UINT32 crc = 0;
        status = bs->CalculateCrc32(destination, length, &crc);
        if (EFI_ERROR(status) || crc != root_crc[index]) { status = EFI_CRC_ERROR; break; }
        offset += length;
        if (!(offset & ((1ULL << 30) - 1)) || offset == ROOT_BYTES)
            number(L"Root bytes verified: ", offset);
    }
    bs->FreePages(transfer, ROOT_CHUNK / 4096);
    return status;
}

EFI_STATUS EFIAPI efi_main(EFI_HANDLE handle, EFI_SYSTEM_TABLE *table)
{
    st = table;
    EFI_BOOT_SERVICES *bs = st->BootServices;
    EFI_STATUS status;
    EFI_LOADED_IMAGE_PROTOCOL *loaded = NULL;
    EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *fs = NULL;
    EFI_FILE_PROTOCOL *root = NULL, *file = NULL;
    EFI_PHYSICAL_ADDRESS ram = RAM_BASE, image = 0xffffffff, fdt = 0xffffffff;
    CONST CHAR16 *stage = L"EL1 check";
    BOOLEAN ram_allocated = FALSE, image_allocated = FALSE, fdt_allocated = FALSE;
    VOID *map = NULL;
    UINTN map_capacity = 0, image_pages = (IMAGE_BYTES + 4095) / 4096;
    say(L"XIGUA / OnePlus Ace 2 Pro / UEFI XNU loader\r\n");
    bs->SetWatchdogTimer(0, 0, 0, NULL);
    UINT64 el;
    __asm__ volatile("mrs %0, CurrentEL" : "=r"(el));
    if (el != 4) { status = EFI_UNSUPPORTED; goto failed; }
    stage = L"RAM reservation";
    status = bs->AllocatePages(AllocateAddress, EfiLoaderData, RAM_BYTES / 4096, &ram);
    if (EFI_ERROR(status)) goto failed;
    ram_allocated = TRUE;
    stage = L"native Image allocation";
    status = bs->AllocatePages(AllocateMaxAddress, EfiLoaderCode, image_pages, &image);
    if (EFI_ERROR(status)) goto failed;
    image_allocated = TRUE;
    stage = L"FDT allocation";
    status = bs->AllocatePages(AllocateMaxAddress, EfiLoaderData, 1, &fdt);
    if (EFI_ERROR(status)) goto failed;
    fdt_allocated = TRUE;
    stage = L"opening ESP Image";
    status = bs->HandleProtocol(handle, &loaded_guid, (VOID **)&loaded);
    if (!EFI_ERROR(status)) status = bs->HandleProtocol(loaded->DeviceHandle, &fs_guid, (VOID **)&fs);
    if (!EFI_ERROR(status)) status = fs->OpenVolume(fs, &root);
    if (!EFI_ERROR(status)) status = root->Open(root, &file, L"\\EFI\\XIGUA\\Image", EFI_FILE_MODE_READ, 0);
    if (EFI_ERROR(status)) goto failed;
    stage = L"reading native Image";
    UINTN received = IMAGE_BYTES;
    status = file->Read(file, &received, (VOID *)(UINTN)image);
    if (EFI_ERROR(status) || received != IMAGE_BYTES) { status = EFI_DEVICE_ERROR; goto failed; }
    UINT8 extra;
    received = 1;
    status = file->Read(file, &received, &extra);
    if (EFI_ERROR(status) || received) { status = EFI_BAD_BUFFER_SIZE; goto failed; }
    file->Close(file); file = NULL;
    root->Close(root); root = NULL;
    stage = L"checking native Image";
    UINT32 crc;
    status = bs->CalculateCrc32((VOID *)(UINTN)image, IMAGE_BYTES, &crc);
    if (EFI_ERROR(status) || crc != IMAGE_CRC) { status = EFI_CRC_ERROR; goto failed; }
    CONST UINT8 *native = (VOID *)(UINTN)image;
    if (native[56] != 'A' || native[57] != 'R' || native[58] != 'M' || native[59] != 0x64 ||
        *(CONST UINT64 *)(native + 16) != IMAGE_BYTES) { status = EFI_LOAD_ERROR; goto failed; }
    stage = L"reading root partition";
    status = read_root(bs);
    if (EFI_ERROR(status)) goto failed;
    // Native shim needs only a bounded FDT range to exclude from RAM copies.
    // Its board parameters come from the hardware-verified embedded profile.
    // Construct a valid, empty FDT in separate low memory; it is not a live DT.
    bytes_zero((VOID *)(UINTN)fdt, 4096);
    UINT32 *dt = (VOID *)(UINTN)fdt;
    dt[0] = be32(0xd00dfeed); dt[1] = be32(72); dt[2] = be32(56);
    dt[3] = be32(72); dt[4] = be32(40); dt[5] = be32(17); dt[6] = be32(16);
    dt[8] = be32(0); dt[9] = be32(16);
    dt[14] = be32(1); dt[15] = 0; dt[16] = be32(2); dt[17] = be32(9);
    number(L"Native Image: ", image); number(L"Reserved RAM: ", ram);
    say(L"Entering native XIGUA loader after ExitBootServices\r\n");
    // A fresh map is obtained on every attempt. No I/O, allocation, logging or
    // protocol operation occurs between successful GetMemoryMap and Exit.
    for (UINTN attempt = 0; attempt < 8; attempt++) {
        UINTN size = map_capacity, key = 0, stride = 0;
        UINT32 version = 0;
        status = bs->GetMemoryMap(&size, map, &key, &stride, &version);
        if (status == EFI_BUFFER_TOO_SMALL) {
            if (map) bs->FreePool(map);
            map = NULL;
            map_capacity = size + 64 * (stride > 40 ? stride : 40);
            status = bs->AllocatePool(EfiLoaderData, map_capacity, &map);
            if (EFI_ERROR(status)) break;
            continue;
        }
        if (EFI_ERROR(status)) break;
        status = bs->ExitBootServices(handle, key);
        if (!EFI_ERROR(status)) enter_native((UINTN)image, (UINTN)fdt);
        // After an Exit attempt, only memory services/Exit may be used.
    }
    // Firmware may already have partially shut down. Do not return into it.
    st->RuntimeServices->ResetSystem(EfiResetCold, status, 0, NULL);
    for (;;) __asm__ volatile("wfe");
failed:
    if (file) file->Close(file);
    if (root) root->Close(root);
    if (map) bs->FreePool(map);
    if (fdt_allocated) bs->FreePages(fdt, 1);
    if (image_allocated) bs->FreePages(image, image_pages);
    if (ram_allocated) bs->FreePages(ram, RAM_BYTES / 4096);
    say(L"XIGUA loader stage: "); say(stage); say(L"\r\n");
    number(L"XIGUA loader stopped; EFI status: ", status);
    say(L"Cold reboot in 20 seconds\r\n");
    bs->Stall(20000000);
    st->RuntimeServices->ResetSystem(EfiResetCold, status, 0, NULL);
    return status;
}
