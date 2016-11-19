#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2016 Christoph Reiter
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.

"""Creates simple Python .exe launchers for gui and cli apps

./create-launcher.py "3.8.0" <target-dir>
"""

import os
import sys
import subprocess
import shlex
import tempfile
import shutil
import struct
from distutils.spawn import find_executable


PY3 = sys.version_info[0] == 3


def build_resource(rc_path, out_path):
    """Raises subprocess.CalledProcessError"""

    def is_64bit():
        return struct.calcsize("P") == 8

    subprocess.check_call(
        ["windres", "-O", "coff", "-F",
         "pe-x86-64" if is_64bit() else "pe-i386", rc_path,
        "-o", out_path])


def get_build_args():
    python_name = os.path.splitext(os.path.basename(sys.executable))[0]
    python_config = os.path.join(
        os.path.dirname(sys.executable), python_name + "-config")

    # under mingw, python-config is a python while python3-config is bash
    if PY3:
        cflags = subprocess.check_output(
            ["sh", python_config, "--cflags"]).strip()
        libs = subprocess.check_output(
            ["sh", python_config, "--libs"]).strip()
    else:
        cflags = subprocess.check_output(
            [python_name, python_config, "--cflags"]).strip()
        libs = subprocess.check_output(
            [python_name, python_config, "--libs"]).strip()

    if PY3:
        cflags = os.fsdecode(cflags)
        libs = os.fsdecode(libs)
    return shlex.split(cflags) + shlex.split(libs)


def build_exe(source_path, resource_path, is_gui, out_path):
    args = ["gcc", "-s"]
    if is_gui:
        args.append("-mwindows")
    args.extend(["-o", out_path, source_path, resource_path])
    args.extend(get_build_args())
    subprocess.check_call(args)


def get_launcher_code(entry_point):
    module, func = entry_point.split(":", 1)

    template = """\
#include "Python.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance,
                   LPSTR lpCmdLine, int nCmdShow)
{
    int result;

    Py_NoUserSiteDirectory = 1;
    Py_IgnoreEnvironmentFlag = 1;
    Py_DontWriteBytecodeFlag = 1;
    Py_Initialize();
    #if PY_MAJOR_VERSION >= 3
    PySys_SetArgvEx(__argc, __wargv, 0);
    #else
    PySys_SetArgvEx(__argc, __argv, 0);
    #endif
    result = PyRun_SimpleString("%s");
    Py_Finalize();
    return result;
}
    """

    launch_code = "import sys; from %s import %s; sys.exit(%s())" % (
        module, func, func)
    return template % launch_code


def get_resouce_code(filename, file_version, file_desc, icon_path,
                     product_name, product_version, company_name):

    template = """\
1 ICON "%(icon_path)s"
1 VERSIONINFO
FILEVERSION     %(file_version_list)s
PRODUCTVERSION  %(product_version_list)s
FILEOS 0x4
FILETYPE 0x1
BEGIN
    BLOCK "StringFileInfo"
    BEGIN
        BLOCK "040904E4"
        BEGIN
            VALUE "CompanyName",      "%(company_name)s"
            VALUE "FileDescription",  "%(file_desc)s"
            VALUE "FileVersion",      "%(file_version)s"
            VALUE "InternalName",     "%(internal_name)s"
            VALUE "OriginalFilename", "%(filename)s"
            VALUE "ProductName",      "%(product_name)s"
            VALUE "ProductVersion",   "%(product_version)s"
        END
    END
    BLOCK "VarFileInfo"
    BEGIN
        VALUE "Translation", 0x409, 1252
    END
END
"""

    def to_ver_list(v):
        return ",".join(map(str, (list(map(int, v.split("."))) + [0] * 4)[:4]))

    file_version_list = to_ver_list(file_version)
    product_version_list = to_ver_list(product_version)

    return template % {
        "icon_path": icon_path, "file_version_list": file_version_list,
        "product_version_list": product_version_list,
        "file_version": file_version, "product_version": product_version,
        "company_name": company_name, "filename": filename,
        "internal_name": os.path.splitext(filename)[0],
        "product_name": product_name, "file_desc": file_desc,
    }


def build_launcher(out_path, icon_path, file_desc, product_name, product_version,
                   company_name, entry_point, is_gui):

    src_ico = os.path.abspath(icon_path)
    target = os.path.abspath(out_path)

    file_version = product_version

    dir_ = os.getcwd()
    temp = tempfile.mkdtemp()
    try:
        os.chdir(temp)
        with open("launcher.c", "w") as h:
            h.write(get_launcher_code(entry_point))
        shutil.copyfile(src_ico, "launcher.ico")
        with open("launcher.rc", "w") as h:
            h.write(get_resouce_code(
                os.path.basename(target), file_version, file_desc,
                "launcher.ico", product_name, product_version, company_name))

        build_resource("launcher.rc", "launcher.res")
        build_exe("launcher.c", "launcher.res", is_gui, target)
    finally:
        os.chdir(dir_)
        shutil.rmtree(temp)


def main():
    argv = sys.argv

    version = argv[1]
    target = argv[2]

    company_name = "The Quod Libet Development Community"
    misc = os.path.dirname(os.path.realpath(__file__))

    build_launcher(
        os.path.join(target, "quodlibet.exe"),
        os.path.join(misc, "quodlibet.ico"), "Quod Libet", "Quod Libet",
        version, company_name, "quodlibet.main:main", True)

    build_launcher(
        os.path.join(target, "quodlibet-cmd.exe"),
        os.path.join(misc, "quodlibet.ico"), "Quod Libet", "Quod Libet",
        version, company_name, "quodlibet.main:main", False)

    build_launcher(
        os.path.join(target, "exfalso.exe"),
        os.path.join(misc, "exfalso.ico"), "Ex Falso", "Quod Libet",
        version, company_name, "quodlibet.exfalso:main", True)

    build_launcher(
        os.path.join(target, "exfalso-cmd.exe"),
        os.path.join(misc, "exfalso.ico"), "Ex Falso", "Quod Libet",
        version, company_name, "quodlibet.exfalso:main", False)

    build_launcher(
        os.path.join(target, "operon.exe"),
        os.path.join(misc, "exfalso.ico"), "Operon", "Quod Libet",
        version, company_name, "quodlibet.operon:main", False)


if __name__ == "__main__":
    main()