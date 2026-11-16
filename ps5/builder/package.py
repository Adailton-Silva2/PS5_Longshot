"""Longshot PS5 Builder, packaged: one folder a player unpacks and starts, with its own Python, compiler and kit.

    PS5_VULKAN=<PS5_Vulkan> python3 -I ps5/builder/package.py --system linux-x64 [--kit dist/kit] [--out dist/builder]

    LongshotPS5Builder/
      longshot-ps5-builder      the launcher (Windows: LongshotPS5Builder.bat; macOS: LongshotPS5Builder.command)
      app/                      the window and the build (app.py, pipeline.py)
      python/                   CPython (python-build-standalone) with PyQt6 and what the lifter imports
      tools/                    clang, ld.lld and llvm-nm (llvm-mingw's LLVM, which has the PS5's target), ps5-native-tool
      kit/                      the title's ready-built part (make_kit.py)

Downloads are kept in --cache and checked by the size and SHA-256 named here. Only linux-x64 is assembled so far; the
table has the other systems' downloads so their turn is the same steps.
"""
import argparse
import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
LLVM = "https://github.com/mstorsjo/llvm-mingw/releases/download/20261104/"
PYTHON = "https://github.com/astral-sh/python-build-standalone/releases/download/20261110/"
SYSTEMS = {
    "linux-x64": {
        "llvm": LLVM + "llvm-mingw-20261104-ucrt-ubuntu-22.04-x86_64.tar.xz",
        "python": PYTHON + "cpython-3.13.18+20261110-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz",
        "llvm_keep": ["bin/clang-23", "bin/clang", "bin/lld", "bin/ld.lld", "bin/llvm-nm", "lib/libclang-cpp.so.23.1",
                      "lib/libLLVM.so.23.1", "lib/clang/23/include", "LICENSE.TXT"],
        "python_exe": "python/bin/python3",
    },
    "windows-x64": {
        "llvm": LLVM + "llvm-mingw-20261104-ucrt-x86_64.zip",
        "python": PYTHON + "cpython-3.13.18+20261110-x86_64-pc-windows-msvc-install_only_stripped.tar.gz",
        "python_exe": "python/python.exe",
    },
    "macos-arm64": {
        "llvm": LLVM + "llvm-mingw-20261104-ucrt-macos-universal.tar.xz",
        "python": PYTHON + "cpython-3.13.18+20261110-aarch64-apple-darwin-install_only_stripped.tar.gz",
        "python_exe": "python/bin/python3",
    },
}
# (what the lifter imports, requirements.txt's pins, and the window)
PACKAGES = ["lz4==4.4.5", "numpy==2.5.4", "capstone==5.0.9", "unicorn==2.1.4", "zstandard==0.25.0", "PyQt6"]


def fetch(url, cache):
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(cache, url.rsplit("/", 1)[1])
    if not os.path.exists(path):
        print("package: downloading", url, flush=True)
        urllib.request.urlretrieve(url, path + ".part")
        os.replace(path + ".part", path)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    print("package: %s  %d bytes  sha256 %s" % (os.path.basename(path), os.path.getsize(path), h.hexdigest()), flush=True)
    return path


def native_tool(vulkan, out):
    """ps5-native-tool (PS5_Vulkan tooling/native): ELF to the console's executable, and its signing. C++20 and zlib,
    its C++ library linked in so it runs on a PC without the compiler's"""
    native = os.path.join(vulkan, "tooling", "native")
    zroot = os.path.join(vulkan, ".deps", "native", "zlib")
    zlib = next((os.path.join(d, f) for d, _, fs in os.walk(zroot) for f in fs if f == "libz.a"), None)
    zinc = next((d for d, _, fs in os.walk(zroot) if "zlib.h" in fs), None)
    if not zlib or not zinc:
        sys.exit("package: PS5_Vulkan's zlib was not found under %s (its tools/build.sh makes it)" % zroot)
    cmd = ["g++", "-std=c++20", "-O2", "-static-libstdc++", "-static-libgcc", "-I", zinc] + \
        [os.path.join(native, f) for f in ("native_app_builder.cpp", "self_container.cpp", "elf_object.cpp", "sce_module_writer.cpp")] + \
        [zlib, "-o", out]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", default="linux-x64", choices=sorted(SYSTEMS))
    ap.add_argument("--kit", default=os.path.join(ROOT, "dist", "kit"))
    ap.add_argument("--out", default=os.path.join(ROOT, "dist", "builder"))
    ap.add_argument("--cache", default=os.path.join(ROOT, ".local", "builder-downloads"))
    a = ap.parse_args()
    if a.system != "linux-x64":
        sys.exit("package: %s is not assembled yet (its downloads are named; the steps are linux-x64's)" % a.system)
    s = SYSTEMS[a.system]
    vulkan = os.environ.get("PS5_VULKAN") or os.path.join(ROOT, "..", "PS5_Vulkan")
    if not os.path.exists(os.path.join(a.kit, "kit.json")):
        sys.exit("package: no kit at %s (ps5/builder/make_kit.py)" % a.kit)
    top = os.path.join(a.out, a.system, "LongshotPS5Builder")
    if os.path.exists(top):
        shutil.rmtree(top)
    os.makedirs(top)

    # ---- Python and its packages ----
    with tarfile.open(fetch(s["python"], a.cache)) as t:
        t.extractall(top, filter="tar")
    py = os.path.join(top, s["python_exe"])
    subprocess.run([py, "-I", "-m", "pip", "install", "--no-warn-script-location", "--disable-pip-version-check", "-q"] + PACKAGES, check=True)
    shutil.rmtree(os.path.join(top, "python", "share"), ignore_errors=True)

    # ---- the compiler ----
    llvm_dir = os.path.join(a.cache, "llvm-" + a.system)
    if not os.path.exists(os.path.join(llvm_dir, "bin")):
        os.makedirs(llvm_dir, exist_ok=True)
        with tarfile.open(fetch(s["llvm"], a.cache)) as t:
            for m in t.getmembers():
                m.name = m.name.split("/", 1)[1] if "/" in m.name else "."
            t.extractall(llvm_dir, filter="tar")
    for rel in s["llvm_keep"]:
        src, dst = os.path.join(llvm_dir, rel), os.path.join(top, "tools", rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isdir(src):
            shutil.copytree(src, dst, symlinks=True)
        else:
            shutil.copy2(src, dst, follow_symlinks=False)
    native_tool(vulkan, os.path.join(top, "tools", "bin", "ps5-native-tool"))

    # ---- the window, the build, the kit ----
    os.makedirs(os.path.join(top, "app"))
    for f in ("app.py", "pipeline.py"):
        shutil.copy2(os.path.join(HERE, f), os.path.join(top, "app", f))
    shutil.copytree(a.kit, os.path.join(top, "kit"))
    shutil.copy2(os.path.join(ROOT, "LICENSE"), os.path.join(top, "LICENSE"))
    launcher = os.path.join(top, "longshot-ps5-builder")
    with open(launcher, "w") as f:
        f.write('#!/bin/sh\n# Longshot PS5 Builder: the window. "--cli ..." runs the build without it (app/pipeline.py\'s options).\n'
                'here=$(cd -- "$(dirname -- "$0")" && pwd)\n'
                'if [ "${1:-}" = "--cli" ]; then shift; exec "$here/python/bin/python3" -I -u "$here/app/pipeline.py" "$@"; fi\n'
                'exec "$here/python/bin/python3" -I "$here/app/app.py" "$@"\n')
    os.chmod(launcher, os.stat(launcher).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    with open(os.path.join(top, "README.txt"), "w") as f:
        f.write("""Longshot PS5 Builder

Builds the PlayStation 5 title folder of Longshot from your own copy of the game.

1. Start longshot-ps5-builder.
2. Choose your game file (.nup) and the folder to build into, then Build.
   The build takes 40 to 70 minutes and wants about 10 GB of free memory and 6 GB of disk.
3. Copy the folder it makes (PPSA99025) to /data/homebrew on the console, or send it from the window over FTP.
   Your game file goes to /data/eglantineps5/roms on the console.

The folder it makes comes from your game: never share it. This builder holds no game files.
What the builder is made of, and the licences: kit/NOTICE.md and LICENSE.
On Linux the window needs the system's libxcb-cursor0 (Debian, Ubuntu: apt install libxcb-cursor0).
Without a window: longshot-ps5-builder --cli --game <file> --out <folder>
""")
    total = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(top) for f in fs if not os.path.islink(os.path.join(d, f)))
    print("package: %s (%d MB)" % (top, total >> 20), flush=True)
    archive = os.path.join(a.out, "LongshotPS5Builder-%s.tar.xz" % a.system)
    subprocess.run(["tar", "-C", os.path.dirname(top), "-cJf", archive, "LongshotPS5Builder"], check=True,
                   env=dict(os.environ, XZ_OPT="-T0 -6"))
    print("package: %s (%d MB)" % (archive, os.path.getsize(archive) >> 20), flush=True)


if __name__ == "__main__":
    sys.exit(main())
