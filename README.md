# BlackDoc

**BlackDoc** is a red‑team payload builder that injects an evasive macro into a clean Word document. When opened and macros are enabled, it silently exfiltrates documents and images from the target machine via Telegram.

> **⚠️ For authorised security testing only.** Use only on systems you own or have explicit written permission to test. Unauthorised access is illegal.

---

## Features

- ✅ **AMSI/ETW bypass** – patches `amsi.dll` functions (P/Invoke) and disables event tracing.  
- ✅ **Anti‑sandbox** – checks RAM, CPU cores, and system uptime.  
- ✅ **All‑drive scanning** – hunts for documents and images across all user folders.  
- ✅ **Smart exfiltration** – batches small files into 50 MB ZIPs; splits large files (>50 MB) into 10 MB chunks.  
- ✅ **Telegram delivery** – uploads everything via Telegram Bot API.  
- ✅ **Persistence** – installs a scheduled task (runs every 6 hours).  
- ✅ **Fileless** – payload runs in memory; no temporary files written to disk.  
- ✅ **Obfuscated** – VBA and PowerShell are heavily obfuscated to evade static detection.

---

## Stack

| Layer          | Technology                                    |
|----------------|-----------------------------------------------|
| **Trigger**    | VBA macro (`AutoOpen`) inside a `.docm` file  |
| **Bypass**     | C# P/Invoke (compiled on‑the‑fly) patches AMSI|
| **Payload**    | PowerShell (in‑memory execution)              |
| **Exfiltration**| Telegram Bot API (multipart/form‑data)       |
| **Persistence**| Windows Scheduled Task (SYSTEM account)      |

---

## Requirements (Builder Machine)

- Windows (with Microsoft Word installed)  
- Python 3.6+  
- `pywin32` (`pip install pywin32`)

---

## Usage

1. **Clone or download** this repository.  
2. **Install the dependency**:
   ```bash
   pip install pywin32
```

3. Prepare a normal‑looking .docx file (e.g., letter.docx).
4. Create a Telegram bot via @BotFather and obtain your bot token.
5. Get your chat ID – send a message to your bot, then visit:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
   Copy the numeric chat ID from the response.
6. Run the builder:
   ```bash
   python blackdoc_v7.py
   ```
   Follow the prompts for the .docx path, token, and chat ID.
7. The output is BlackDoc.docm – deliver it to your target (email, USB, etc.).

---

On the Target

· Windows with Word: the user must enable macros (social‑engineering required). Once enabled, the payload runs silently.
· Mobile (Android/iOS): macros are not supported – the document opens harmlessly, no data is sent.

---

How It Works

1. The victim opens the .docm and enables macros.
2. The VBA macro decodes and executes a PowerShell wrapper.
3. The wrapper:
   · Patches AMSI and disables ETW.
   · Checks for debugging/sandbox and exits if suspicious.
   · Decodes the main payload from a base64 string.
   · Installs a scheduled task for persistence.
   · Launches a hidden PowerShell instance running the same payload.
4. The main payload:
   · Scans all fixed drives for common document and image extensions.
   · Creates in‑memory ZIP archives (up to 50 MB each).
   · Uploads each batch via Telegram.
   · Splits any single file larger than 50 MB into 10 MB chunks and uploads them.

---

Disclaimer

This tool is provided for educational and authorised security testing purposes only. The author is not responsible for any misuse or damage caused by this software. By using this tool, you agree that you have the necessary permissions to test the target systems and that you will comply with all applicable laws.

---

Credits

Built for red‑team exercises and adversary simulation. Inspired by real‑world APT tradecraft.

---
