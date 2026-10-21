/* SPDX-License-Identifier: BSD-2-Clause
 * XIGUA UEFI diagnostics. Boot Services remain active throughout the probe.
 * Writes only xigua-probe-<monotonic count>.txt on its own filesystem.
 */
#include <Uefi.h>
#include <Protocol/GraphicsOutput.h>
#include <Protocol/LoadedImage.h>
#include <Protocol/SimpleFileSystem.h>

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
    add("XIGUA-PROBE version=1\r\n");
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
