# Longshot on the PS5

Private working repository for porting [Longshot](https://git.magicbean.dev/MagicBeanDev/Longshot) (static
recompilation of The Legend of Zelda: Ocarina of Time for Switch 2, the continuation of Hookshot) to the PS5.

Status (2026-11-15): PS5_Hookshot's port is merged onto Longshot, the title builds, and it runs on the console: the
game's logos, the opening movie and the title screen at 60 fps for two runs of 110 and 150 s, ended cleanly. Not tried
yet: starting a game, play, saves, sound by ear. `ps5/build-title.sh` is still PS5_Hookshot's (see "Building").

The title is **PPSA99025, Longshot**, so PS5_Hookshot's PPSA99024 on a console is left alone.

## Branches

| Branch | What it is |
|---|---|
| `main` | The port. Starts at Longshot `ceccd963` (2026-11-15) plus this folder. |
| `upstream-main` | Longshot's `main`, untouched. Update it with `git fetch upstream && git push origin upstream/main:upstream-main`, then merge into `main`. |
| `ref/ps5-hookshot` | mihawk-99's PS5_Hookshot at `ps5-v0.1.0-beta.2` (`275b9873`): Hookshot as a native PS5 title. Reference only. Its GitHub repository is gone (404 on 2026-11-15), so this branch is a copy to keep. |

Remotes on the working clone: `origin` (this repository), `upstream` (Longshot on magicbean.dev).

## Vulkan driver

[PS5_Vulkan](https://github.com/mihawk-99/PS5_Vulkan) is a submodule at `ps5/deps/PS5_Vulkan`, pinned at
`7f492b4c` (its `main` on 2026-11-15, and the revision PS5_Hookshot beta.2 built against).

```
git submodule update --init ps5/deps/PS5_Vulkan
```

PS5_Vulkan builds RADV from PS5_Mesa and needs the payload SDK. PS5_Hookshot beta.2 pinned these beside it:

| Project | Revision |
|---|---|
| PS5_Mesa | `0f86253f674c425052948eb3cb116c81e646a734` |
| PS5_PayloadSDK | `55a2de04e3364f0a6c8d6c337dc95436cf091ef0` |
| PS5_MihawkGen (frame generation) | `c57232a9f16bcb6df5fe07c9bb631518f2b1cc0e` |

Headers `gpu/vk` was compiled with there: Vulkan-Headers `v1.4.345`, SPIRV-Headers `vulkan-sdk-1.4.341.0`,
VMA `v3.3.0`.

## What the merge decided

`git merge ref/ps5-hookshot` stopped on 13 files. What was not a plain "both sides":

- `gpu/vk/vk_progcache.cpp`: Longshot moved the program cache out of `vk_shader.cpp`. The port's held writes during the
  preparation (`kDiskHold`: a write into the title folder costs ~60 ms) are here now, and every reader flushes first.
- `gpu/vk/vk_texture.cpp`: the port aged textures in milliseconds; Longshot's compaction reads the age in presents. The
  age stays in presents, 30 on the console (about the port's one second) and 60 elsewhere.
- `gpu/vk/vk_draw.cpp`: Longshot's pipeline cache save is kept; the port's lines timing the save are left out.
- `gpu/vk/vk_framegen.cpp`: PS5_MihawkGen's frames come first, before FSR 3.1's.
- `host/posix/win32_posix.c`: a new thread takes the process's affinity through `scePthreadSetaffinity`.
- `host/ps5/win32_ps5.h`: a small `std::atomic_ref`, which the SDK's C++ library lacks and Longshot's back end uses.
- `host/ps5/hos_sdl_ps5.c`: stand-ins for the calls `hos_sdl.h` gained (text input, clipboard, Steam pads).
- The game is looked for in `/data/eglantineps5/roms` first, under the name the dump has.

## Building

`ps5/build-title.sh` is still PS5_Hookshot's (it clones sibling projects and names Hookshot); until it is rewritten, the
steps by hand, with the dependencies of an earlier PS5_Hookshot build linked into `.local/`:

```
export PS5_VULKAN=<a built PS5_Vulkan at 7f492b4c> PS5_MIHAWKGEN=<PS5_MihawkGen>
LONGSHOT_LIFT_JOBS=1 OOT_WORK=$PWD/work/lift python -I nx2/lift.py --standalone --write --exefs <exefs> --work $PWD/work/lift
python -I ps5/build.py --jobs N
```

The lift holds about 6 GB and more as it writes (it was stopped for want of memory with less than ~10 GB free); each
compile of a lifted chunk about 1.4 GB. The compile took 40 minutes at 6 jobs.

Install and run (the control payload `ps5vkctl` on the console, port 9111):

```
PS5_HOST=192.168.0.190 python3 $PS5_VULKAN/tools/deploy-title-folder.py dist/PPSA99025
PS5_HOST=192.168.0.190 python3 ps5/tools/run.py NAME --seconds 150      # klog in work/runs/NAME.klog
```

## Test console

| What | Where |
|---|---|
| Address | `192.168.0.190` |
| FTP | port `2121` |
| ps5debug-NG | port `744` |
| klogsrv (kernel log) | port `3232` |
| ELF loader | port `9021` |
| Game | `/data/eglantineps5/roms/`, The Legend of Zelda: Ocarina of Time as a `.nup` (program `0400486024DEC000`, update v131072) |

On 2026-11-15 only the ELF loader answered: FTP, ps5debug-NG and klogsrv have to be loaded before a test run.

Notes from the PS5_Hookshot build on this console:

- Its title installed as `/data/homebrew/PPSA99024`.
- `link()` and `symlink()` fail on `/data` (errno 45): a title that wants the game elsewhere needs a real copy (25 GB)
  or to read it in place.
- The FTP server decrypts SELF files on read by default: send `SELF` to switch that off before comparing hashes.

## Rules

- No game files, keys or built titles in this repository: everything a build makes comes from the game copy.
- Longshot is GPL-3.0 (see `LICENSE`); the port keeps that licence.
