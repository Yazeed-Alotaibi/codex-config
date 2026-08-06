# Oh My Posh terminal configuration

This directory contains the portable pieces of the PowerShell and Windows
Terminal setup used on this machine.

## Installed components

- Oh My Posh, installed through WinGet.
- CascadiaCode Nerd Font, installed by Oh My Posh as `CaskaydiaCove NF`.
- PowerShell 7 profile initialization.
- Windows Terminal Preview font/default-profile overlay.

## Apply the PowerShell profile

Copy `PowerShell_profile.ps1` into the PowerShell 7 profile path:

`$HOME\Documents\PowerShell\Microsoft.PowerShell_profile.ps1`

If the profile already contains other settings, append the Oh My Posh line
instead of replacing the existing file.

## Apply the Windows Terminal settings

Merge `windows-terminal-settings.overlay.jsonc` into the active Windows
Terminal `settings.json`. The PowerShell 7 profile GUID is stable for the
Windows Terminal PowerShell Core profile, but it can be adjusted if a local
installation uses a different GUID.

The complete machine settings file is deliberately not tracked here because
it may contain local SSH profile names and other device-specific preferences.

## Verify

Open a new PowerShell 7 tab and run:

```powershell
oh-my-posh version
```

The prompt should initialize automatically, and the terminal font should be
set to `CaskaydiaCove NF`.
