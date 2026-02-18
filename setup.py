#!usr/bin/env python

import os
import platform
import shutil
import subprocess
import sys
import glob

###########################################################################

# Check Python's version info and exit early if it is too old
if sys.version_info < (3, 7):
    print("This module requires Python >= 3.7")
    sys.exit(0)

###########################################################################

from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext as _build_ext


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DEPS_LIB = os.path.join(ROOT_DIR, "build-deps", "install", "lib")
DEPS_LIB64 = os.path.join(ROOT_DIR, "build-deps", "install", "lib64")
PKG_DIR = os.path.join(ROOT_DIR, "src", "leidenalg_pop")


def build_deps():
    """Build igraph and libleidenalg into build-deps/install/ if not already present."""
    install_dir = os.path.join(ROOT_DIR, "build-deps", "install")

    igraph_lib = os.path.join(install_dir, "lib", "cmake", "igraph")
    if not os.path.isdir(igraph_lib):
        print("Building igraph dependency...")
        script = os.path.join(ROOT_DIR, "scripts", "build_igraph.sh")
        subprocess.check_call(["bash", script], cwd=ROOT_DIR)

    libleiden_lib = os.path.join(install_dir, "lib", "cmake", "libleidenalg")
    if not os.path.isdir(libleiden_lib):
        print("Building libleidenalg dependency...")
        script = os.path.join(ROOT_DIR, "scripts", "build_libleidenalg.sh")
        subprocess.check_call(["bash", script], cwd=ROOT_DIR)


def copy_shared_libs(extra_target_dir=None):
    """Copy shared libraries into the Python package directory so they are
    installed alongside the extension and found at runtime.

    extra_target_dir: if given (the setuptools build_lib directory), also copy
    the libs there so that bdist_wheel picks them up.  bdist_wheel collects
    files from the build directory, not the source tree, so without this the
    bundled libs are absent from the installed wheel on Linux/Windows.
    """
    patterns = ["libigraph*", "liblibleidenalg*"]
    targets = [PKG_DIR]
    if extra_target_dir:
        build_pkg_dir = os.path.join(extra_target_dir, "leidenalg_pop")
        os.makedirs(build_pkg_dir, exist_ok=True)
        targets.append(build_pkg_dir)

    copied = []
    for lib_dir in [DEPS_LIB, DEPS_LIB64]:
        if not os.path.isdir(lib_dir):
            continue
        for pattern in patterns:
            for src in glob.glob(os.path.join(lib_dir, pattern)):
                # Skip cmake config dirs and static libs
                if os.path.isdir(src) or src.endswith(".a"):
                    continue
                for target in targets:
                    dst = os.path.join(target, os.path.basename(src))
                    shutil.copy2(src, dst)  # always overwrite to pick up rebuilds
                    if target == PKG_DIR:
                        copied.append(os.path.basename(src))
    if copied:
        print(f"Bundled shared libs: {copied}")
    if platform.system() == "Darwin":
        for t in targets:
            fix_rpath_in_bundled_libs(t)


def fix_rpath_in_bundled_libs(target_dir=None):
    """On macOS, rewrite the rpath embedded in bundled dylibs so they resolve
    sibling libraries via @loader_path rather than hardcoded build-tree paths.

    cmake typically embeds the build-tree lib directory as an LC_RPATH entry
    (e.g. /Users/foo/.local/lib).  After we copy the dylibs into the wheel /
    editable-install package dir, that path no longer contains the igraph dylib,
    so liblibleidenalg cannot load.  We replace every non-system LC_RPATH with
    @loader_path so the dynamic linker looks next to the dylib itself.
    """
    if target_dir is None:
        target_dir = PKG_DIR
    install_name_tool = shutil.which("install_name_tool")
    if not install_name_tool:
        print("Warning: install_name_tool not found; skipping rpath fix")
        return

    for dylib in glob.glob(os.path.join(target_dir, "*.dylib")):
        if os.path.islink(dylib):
            continue  # only process the actual file, not symlinks
        # Read current rpaths
        result = subprocess.run(
            ["otool", "-l", dylib],
            capture_output=True, text=True
        )
        rpaths = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("path "):
                rpath = line.split()[1]
                if not rpath.startswith("@"):
                    rpaths.append(rpath)
        for old_rpath in rpaths:
            subprocess.run(
                [install_name_tool, "-rpath", old_rpath, "@loader_path", dylib],
                capture_output=True
            )


class build_ext(_build_ext):
    def run(self):
        build_deps()
        # Copy to source dir (editable install) AND build dir (wheel install).
        # bdist_wheel collects from self.build_lib, not the source tree.
        copy_shared_libs(extra_target_dir=self.build_lib)
        # Set rpath so the extension finds bundled libs at runtime
        for ext in self.extensions:
            if platform.system() == "Linux":
                ext.extra_link_args = ext.extra_link_args or []
                ext.extra_link_args.append("-Wl,-rpath,$ORIGIN")
            elif platform.system() == "Darwin":
                ext.extra_link_args = ext.extra_link_args or []
                ext.extra_link_args.append("-Wl,-rpath,@loader_path")
        super().run()


try:
    from wheel.bdist_wheel import bdist_wheel
except ImportError:
    bdist_wheel = None

if bdist_wheel is not None:
    class bdist_wheel_abi3(bdist_wheel):
        def get_tag(self):
            python, abi, plat = super().get_tag()
            if python.startswith("cp"):
                # on CPython, our wheels are abi3 and compatible back to 3.5
                return "cp38", "abi3", plat

            return python, abi, plat
else:
    bdist_wheel_abi3 = None

should_build_abi3_wheel = (
    bdist_wheel_abi3 and
    platform.python_implementation() == "CPython" and
    sys.version_info >= (3, 8)
)

# Define the extension
macros = []
if should_build_abi3_wheel:
    macros.append(("Py_LIMITED_API", "0x03090000"))

cmdclass = {"build_ext": build_ext}

if should_build_abi3_wheel:
    cmdclass["bdist_wheel"] = bdist_wheel_abi3

setup(
    ext_modules = [
        Extension('leidenalg_pop._c_leiden',
                  sources = glob.glob(os.path.join('src', 'leidenalg_pop', '*.cpp')),
                  py_limited_api=should_build_abi3_wheel,
                  define_macros=macros,
                  libraries = ['libleidenalg', 'igraph'],
                  include_dirs=['include', 'build-deps/install/include'],
                  library_dirs=['build-deps/install/lib', 'build-deps/install/lib64'],
        )
    ],
    package_data={"leidenalg_pop": ["libigraph*", "liblibleidenalg*"]},
    cmdclass=cmdclass
)
