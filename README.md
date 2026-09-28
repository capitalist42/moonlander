# Moonlander

Omarchy bar plugin for the ZSA Moonlander Mark I plugged into this machine.

It reads the layout id from the keyboard's USB serial, fetches that revision from Oryx, and draws it. Edits stay in `~/.config/omarchy/moonlander/layout.json`. Compile turns the draft into a QMK keymap and builds `zsa/moonlander/reva` firmware. Flash writes that firmware with Zapp after you press the reset pinhole, or the Reset key on layer 2. Nothing is written back to the Oryx account.

The shell loads plugins from `~/.config/omarchy/plugins/`. This repo is the source. Link it once:

```bash
ln -s ~/Projects/moonlander ~/.config/omarchy/plugins/capitalist42.moonlander
omarchy plugin enable capitalist42.moonlander right
```

The compiler, Zapp, the QMK tree, and the Jal4PQ restore image live under `~/.local/share/omarchy-moonlander/`. Set those up with `scripts/setup-toolchain.sh`. That script does not flash the keyboard.

Restore, from the panel or the command line, puts the Oryx revision back:

```bash
python flash.py restore --yes
```

You still have to press the reset pinhole when Zapp asks.
