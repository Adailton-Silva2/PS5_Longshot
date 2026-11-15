# Longshot on the PS5

Private working repository for porting [Longshot](https://git.magicbean.dev/MagicBeanDev/Longshot) (static
recompilation of The Legend of Zelda: Ocarina of Time for Switch 2, the continuation of Hookshot) to the PS5.

Status: **nothing ported yet.** This repository holds the starting points; the port itself has not begun.

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

## Where to start

PS5_Hookshot's port is 18 commits by Mihawk on top of Hookshot `2877284a`, which is an ancestor of Longshot's `main`
(Longshot is 988 commits past it). Against that base the port changes 51 files, about 5,100 added lines: `host/ps5/`,
`ps5/` (build script, tools, tests, `sce_sys`), and edits in `gpu/vk/` and `host/`.

A trial `git merge ref/ps5-hookshot` into `main` on 2026-11-15 added the new folders cleanly and stopped on 13 files:

- `gpu/vk/`: `vk_draw.cpp`, `vk_framegen.cpp`, `vk_jobs.cpp`, `vk_loader.h`, `vk_main.cpp`, `vk_shader.cpp`,
  `vk_texture.cpp`, `vk_texture.h`, `vk_vma.cpp`
- `host/`: `hos_main.c`, `hos_thread.c`, `posix/win32_posix.c`
- `.gitignore`

It also brings back two `.github/workflows` files that Longshot deleted: drop them. The merge was not kept.

PS5_Hookshot's `ps5/build-title.sh` clones PS5_Vulkan and the other projects as sibling folders; point it at the
submodule instead (`PS5_VULKAN=ps5/deps/PS5_Vulkan`).

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
