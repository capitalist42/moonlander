#!/usr/bin/env bash
# One-time compiler, flasher, QMK tree, and the Oryx restore image.
# Does not flash the keyboard.
set -euo pipefail

SHARE="${HOME}/.local/share/omarchy-moonlander"
QMK_HOME="${SHARE}/qmk"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Installing qmk, the ARM toolchain, and dfu-util"
omarchy pkg add qmk arm-none-eabi-gcc arm-none-eabi-newlib dfu-util

if ! command -v zapp >/dev/null 2>&1; then
  echo "Installing zapp from the AUR"
  omarchy pkg aur add zsa-zapp-git
fi

if [[ ! -d ${QMK_HOME}/quantum ]]; then
  echo "Cloning ZSA QMK firmware25 into ${QMK_HOME}"
  mkdir -p "${SHARE}"
  qmk setup -y -H "${QMK_HOME}" -b firmware25 zsa/qmk_firmware
fi

mkdir -p "${SHARE}/restore" "${SHARE}/source"
if [[ ! -f ${SHARE}/restore/Jal4PQ.bin ]]; then
  echo "Downloading the Oryx restore firmware for revision Jal4PQ"
  curl -fL --retry 3 -o "${SHARE}/restore/Jal4PQ.bin" "https://oryx.zsa.io/firmware/Jal4PQ?collate=true"
fi

python3 "${ROOT}/read-layout.py" --draft "${HOME}/.config/omarchy/moonlander/layout.json" >/dev/null
echo "Compiling the current draft to prove the firmware builds. This does not flash."
python3 "${ROOT}/flash.py" compile --draft "${HOME}/.config/omarchy/moonlander/layout.json"
echo "Toolchain ready. Firmware restore image: ${SHARE}/restore/Jal4PQ.bin"
