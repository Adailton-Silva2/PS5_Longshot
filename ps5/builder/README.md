# Longshot PS5 Builder

A desktop tool: a player chooses their own game file and gets the PS5 title folder (`PPSA99025`) to copy to
`/data/homebrew` on the console. Nothing has to be installed: the package carries its own Python, compiler and kit.

| File | What it is |
|---|---|
| `make_kit.py` | Collects everything of the title that is not made from the game, compiled already, into `dist/kit` (after a whole `ps5/build.py` build). No game content. |
| `pipeline.py` | The build: the game's program read out of the `.nup`, translated to C, compiled, linked with the kit, signed, laid out. Python only, the same on every system. `--game --out [--jobs]`. |
| `app.py` | The window (PyQt6): game file, output folder, Build, the five steps, a progress bar, the log, Stop, and Send to PS5 over FTP. Runs `pipeline.py` as a process. |
| `package.py` | The package for a system: python-build-standalone, llvm-mingw's LLVM (its clang has the PS5 target), `ps5-native-tool`, the kit. `dist/builder/LongshotPS5Builder-<system>.tar.xz`. |

```
PS5_VULKAN=... PS5_MIHAWKGEN=... python3 -I ps5/build.py            # the whole title, once
PS5_VULKAN=... PS5_MIHAWKGEN=... python3 -I ps5/builder/make_kit.py
PS5_VULKAN=... python3 -I ps5/builder/package.py --system linux-x64
dist/builder/linux-x64/LongshotPS5Builder/longshot-ps5-builder      # the window; --cli --game F --out D without it
```

## State (2026-11-16)

- **Linux x64**: packaged (193 MB, 1 GB unpacked). A clean build through `pipeline.py` with this PC's clang 19 made a
  title that was sent with the window's FTP sender and played into Kokiri Forest on the console at 32 fps. A clean
  build with the package itself (its Python, its clang 23.1.5: 36 minutes of compiling at 6 jobs) made a title too;
  that one has **not** run on the console yet. The window was driven headless with a stand-in build (success and
  failure); not by hand on a desktop.
- **Reading a `.nup`** was not exercised here: the tests gave the folder with the game's `exefs`, which the game field
  takes as well (`--game <folder>`).
- **Windows x64, macOS**: not packaged. `package.py` names their downloads; `ps5-native-tool` has to be built for each
  (llvm-mingw can cross-build the Windows one; the Mac one needs a Mac or zig), and `liba64emit` (the lifter's helper,
  `third_party/a64-kit/lift/build_emit.py`) is in the kit for Linux only.
- The kit is made on Linux from a finished build; `kit.json` names the revisions it came from.
