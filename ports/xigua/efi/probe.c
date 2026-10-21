/* SPDX-License-Identifier: BSD-2-Clause
 * XIGUA UEFI diagnostics. Boot Services remain active throughout the probe.
 * Writes only xigua-probe-<monotonic count>.txt on its own filesystem.
 */
#include <Uefi.h>
#include <Protocol/GraphicsOutput.h>
#include <Protocol/LoadedImage.h>
#include <Protocol/SimpleFileSystem.h>
#include <Protocol/BlockIo.h>
#include <Protocol/PartitionInfo.h>

static EFI_GUID loaded_guid = EFI_LOADED_IMAGE_PROTOCOL_GUID;
static EFI_GUID fs_guid = EFI_SIMPLE_FILE_SYSTEM_PROTOCOL_GUID;
static EFI_GUID gop_guid = EFI_GRAPHICS_OUTPUT_PROTOCOL_GUID;
static EFI_SYSTEM_TABLE *system_table;
static CHAR8 report[65536];
static UINTN used;

static VOID add(CONST CHAR8 *s)
{
    while (*s && used < sizeof(report) - 1)
        report[used++] = *s++;
}

static VOID hex(UINT64 n)
{
    static CONST CHAR8 digits[] = "0123456789abcdef";
    add("0x");
    for (INTN i = 60; i >= 0; i -= 4) {
        CHAR8 b[2] = {digits[(n >> i) & 15], 0};
        add(b);
    }
}

static VOID field(CONST CHAR8 *s, UINT64 v)
{
    add(s); add("="); hex(v); add("\r\n");
}

static VOID display(CONST CHAR8 *s)
{
    CHAR16 line[192];
    while (*s) {
        UINTN n = 0;
        while (*s && n < 191) line[n++] = (CHAR16)*s++;
        line[n] = 0;
        system_table->ConOut->OutputString(system_table->ConOut, line);
    }
}

#define REGISTER(name) ({ UINT64 r; __asm__ volatile("mrs %0, " #name : "=r"(r)); r; })

static int name_is(CONST CHAR16 *name, CONST CHAR16 *wanted)
{
    for (UINTN i = 0; i < 36; i++) {
        if (name[i] != wanted[i]) return 0;
        if (!wanted[i]) return 1;
    }
    return 0;
}

static VOID storage_probe(EFI_BOOT_SERVICES *bs)
{
    EFI_GUID block_guid = EFI_BLOCK_IO_PROTOCOL_GUID;
    EFI_GUID part_guid = EFI_PARTITION_INFO_PROTOCOL_GUID;
    EFI_HANDLE *handles = NULL;
    UINTN count = 0;
    EFI_STATUS status = bs->LocateHandleBuffer(ByProtocol, &block_guid, NULL, &count, &handles);
    field("block_io_enumeration_status", status);
    if (EFI_ERROR(status)) return;
    field("block_io_handle_count", count);
    for (UINTN i = 0; i < count; i++) {
        EFI_PARTITION_INFO_PROTOCOL *part = NULL;
        EFI_BLOCK_IO_PROTOCOL *block = NULL;
        if (EFI_ERROR(bs->HandleProtocol(handles[i], &part_guid, (VOID **)&part)) ||
            part->Type != PARTITION_TYPE_GPT) continue;
        if (!name_is(part->Info.Gpt.PartitionName, L"esp") &&
            !name_is(part->Info.Gpt.PartitionName, L"installer") &&
            !name_is(part->Info.Gpt.PartitionName, L"linux")) continue;
        add("partition ");
        for (UINTN j = 0; j < 36 && part->Info.Gpt.PartitionName[j]; j++) {
            CHAR8 c[2] = {(CHAR8)part->Info.Gpt.PartitionName[j], 0}; add(c);
        }
        add("\r\n");
        status = bs->HandleProtocol(handles[i], &block_guid, (VOID **)&block);
        field("partition_block_io_status", status);
        if (EFI_ERROR(status) || !block->Media) continue;
        field("partition_block_size", block->Media->BlockSize);
        field("partition_last_block", block->Media->LastBlock);
        field("partition_logical", block->Media->LogicalPartition);
        field("partition_read_only", block->Media->ReadOnly);
        // Only read one block. This probe never writes to Block I/O.
        EFI_PHYSICAL_ADDRESS buffer = 0;
        UINTN bytes = block->Media->BlockSize;
        if (bytes < 512 || bytes > 65536 || block->Media->IoAlign > 4096) continue;
        status = bs->AllocatePages(AllocateAnyPages, EfiLoaderData, (bytes + 4095) / 4096, &buffer);
        if (EFI_ERROR(status)) continue;
        status = block->ReadBlocks(block, block->Media->MediaId, 0, bytes, (VOID *)(UINTN)buffer);
        field("partition_read_status", status);
        if (!EFI_ERROR(status)) {
            CONST UINT8 *b = (VOID *)(UINTN)buffer;
            UINT64 first = 0;
            for (UINTN j = 0; j < 8; j++) first = (first << 8) | b[j];
            field("partition_first_eight_bytes", first);
        }
        bs->FreePages(buffer, (bytes + 4095) / 4096);
    }
    bs->FreePool(handles);
}

static VOID large_ram_probe(EFI_BOOT_SERVICES *bs)
{
    // The previous phone report described this full 13 GiB range as conventional.
    // AllocateAddress must reserve all of it before any page is touched.
    EFI_PHYSICAL_ADDRESS base = 0x8c0000000ULL;
    UINTN bytes = 0x340000000ULL;
    EFI_STATUS status = bs->AllocatePages(AllocateAddress, EfiLoaderData, bytes / 4096, &base);
    field("large_ram_allocate_status", status);
    if (EFI_ERROR(status)) return;
    field("large_ram_base", base); field("large_ram_size", bytes);
    UINTN offsets[] = {0, bytes / 2, bytes - 16384};
    int passed = 1;
    for (UINTN n = 0; n < 3; n++) {
        volatile UINT64 *page = (VOID *)(UINTN)(base + offsets[n]);
        for (UINTN i = 0; i < 16384 / 8; i++) page[i] = 0x5849475541000000ULL ^ offsets[n] ^ i;
        __asm__ volatile("dsb sy" ::: "memory");
        for (UINTN i = 0; i < 16384 / 8; i++)
            if (page[i] != (0x5849475541000000ULL ^ offsets[n] ^ i)) passed = 0;
    }
    field("large_ram_sample_pages_passed", passed);
    bs->FreePages(base, bytes / 4096);
}

EFI_STATUS EFIAPI efi_main(EFI_HANDLE image, EFI_SYSTEM_TABLE *table)
{
    EFI_STATUS status;
    EFI_BOOT_SERVICES *bs = table->BootServices;
    EFI_LOADED_IMAGE_PROTOCOL *loaded = NULL;
    EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *fs = NULL;
    EFI_GRAPHICS_OUTPUT_PROTOCOL *gop = NULL;
    EFI_FILE_PROTOCOL *root = NULL, *file = NULL;
    EFI_MEMORY_DESCRIPTOR *map = NULL;
    UINTN size = 0, key, stride = 0;
    UINT32 version;
    UINT64 count = 0;
    CHAR16 filename[] = L"\\xigua-probe-0000000000000000.txt";
    CONST CHAR16 digits[] = L"0123456789abcdef";
    system_table = table;
    display("XIGUA hardware probe (no ExitBootServices)\r\n");
    add("XIGUA-PROBE version=2\r\n");
    field("current_el", REGISTER(CurrentEL) >> 2);
    if ((REGISTER(CurrentEL) >> 2) < 1) return EFI_UNSUPPORTED;
    field("midr_el1", REGISTER(MIDR_EL1));
    field("mpidr_el1", REGISTER(MPIDR_EL1));
    UINT64 mmfr0 = REGISTER(ID_AA64MMFR0_EL1);
    field("id_aa64mmfr0_el1", mmfr0);
    field("tgran16", (mmfr0 >> 20) & 15);
    field("cntfrq_el0", REGISTER(CNTFRQ_EL0));
    field("sctlr_el1", REGISTER(SCTLR_EL1));
    field("tcr_el1", REGISTER(TCR_EL1));
    field("ctr_el0", REGISTER(CTR_EL0));
    status = bs->LocateProtocol(&gop_guid, NULL, (VOID **)&gop);
    field("gop_status", status);
    if (!EFI_ERROR(status) && gop->Mode && gop->Mode->Info) {
        field("gop_base", gop->Mode->FrameBufferBase);
        field("gop_size", gop->Mode->FrameBufferSize);
        field("gop_width", gop->Mode->Info->HorizontalResolution);
        field("gop_height", gop->Mode->Info->VerticalResolution);
        field("gop_pixels_per_scanline", gop->Mode->Info->PixelsPerScanLine);
        field("gop_pixel_format", gop->Mode->Info->PixelFormat);
        field("gop_red_mask", gop->Mode->Info->PixelInformation.RedMask);
        field("gop_green_mask", gop->Mode->Info->PixelInformation.GreenMask);
        field("gop_blue_mask", gop->Mode->Info->PixelInformation.BlueMask);
    }
    status = bs->GetMemoryMap(&size, NULL, &key, &stride, &version);
    if (status == EFI_BUFFER_TOO_SMALL && stride) {
        size += 32 * stride;
        status = bs->AllocatePool(EfiLoaderData, size, (VOID **)&map);
        if (!EFI_ERROR(status)) status = bs->GetMemoryMap(&size, map, &key, &stride, &version);
    }
    field("memory_map_status", status);
    if (!EFI_ERROR(status) && map && stride >= sizeof(EFI_MEMORY_DESCRIPTOR)) {
        add("memory_map: type base pages attributes\r\n");
        for (UINTN off = 0; off + stride <= size; off += stride) {
            EFI_MEMORY_DESCRIPTOR *d = (VOID *)((CHAR8 *)map + off);
            add("memory "); hex(d->Type); add(" "); hex(d->PhysicalStart);
            add(" "); hex(d->NumberOfPages); add(" "); hex(d->Attribute); add("\r\n");
        }
    }
    if (map) bs->FreePool(map);
    storage_probe(bs);
    large_ram_probe(bs);
    // An independent file avoids truncating or changing any existing boot files.
    status = bs->GetNextMonotonicCount(&count);
    if (EFI_ERROR(status)) return status;
    for (UINTN i = 0; i < 16; i++) filename[13 + i] = digits[(count >> ((15 - i) * 4)) & 15];
    status = bs->HandleProtocol(image, &loaded_guid, (VOID **)&loaded);
    if (!EFI_ERROR(status)) status = bs->HandleProtocol(loaded->DeviceHandle, &fs_guid, (VOID **)&fs);
    if (!EFI_ERROR(status)) status = fs->OpenVolume(fs, &root);
    if (!EFI_ERROR(status)) status = root->Open(root, &file, filename,
        EFI_FILE_MODE_READ | EFI_FILE_MODE_WRITE | EFI_FILE_MODE_CREATE, 0);
    if (!EFI_ERROR(status)) {
        UINTN bytes = used;
        status = file->Write(file, &bytes, report);
        if (!EFI_ERROR(status) && bytes != used) status = EFI_DEVICE_ERROR;
        if (!EFI_ERROR(status)) status = file->Flush(file);
        file->Close(file);
    }
    if (root) root->Close(root);
    report[used] = 0;
    display(report);
    if (EFI_ERROR(status)) {
        display("Probe log could not be saved. Returning to firmware.\r\n");
        return status;
    }
    display("Saved report to ESP as ");
    table->ConOut->OutputString(table->ConOut, filename);
    display("\r\nCold reboot to normal boot in 15 seconds.\r\n");
    bs->Stall(15000000);
    table->RuntimeServices->ResetSystem(EfiResetCold, EFI_SUCCESS, 0, NULL);
    return EFI_SUCCESS;
}
