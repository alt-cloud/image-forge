#!/usr/bin/python3

# Code is formatted using black with default options

from pathlib import Path

import argparse
import glob
import re
import subprocess
import tarfile


class DL:
    def __init__(self, dl_file):
        self.dl_file = Path(dl_file)

    def add(self, files, file_lists, packages, is_glob=True, follow_symlink=True):
        def write(dl_file, file):
            file = file.rstrip("\n")
            dl_file.write(file + "\n")
            path = Path(file)
            if follow_symlink and path.is_symlink():
                dl_file.write(path.resolve().as_posix() + "\n")

        def write_globs(is_glob, source, dl_file):
            if is_glob:
                for file in glob.glob(source.rstrip("\n")):
                    write(dl_file, file)
            else:
                write(dl_file, file)

        with open(self.dl_file, "a") as dl_file:
            for file in files:
                write_globs(is_glob, file, dl_file)
            for file_list in file_lists:
                with open(file_list) as fl:
                    for line in fl:
                        write_globs(is_glob, line, dl_file)
            for package in packages:
                proc = subprocess.run(["rpm", "-qls", package], stdout=subprocess.PIPE)
                proc.check_returncode()
                for line in proc.stdout.decode().splitlines():
                    state, filename = line.split(maxsplit=1)
                    if state == "normal":
                        write(dl_file, filename)

    def tar(self, outfile, regexes):
        def filter(tarinfo):
            name = f"/{tarinfo.name}"
            if not any(re.match(r, name) for r in regexes):
                return tarinfo

        with tarfile.open(outfile, "w") as tar:
            with open(self.dl_file) as dl_file:
                for path in dl_file:
                    tar.add(path[:-1], recursive=False, filter=filter)

    def clean(self):
        self.dl_file.unlink(missing_ok=True)


def library_files(binaries):
    files = set()
    for binary in binaries:
        ldd = subprocess.run(["ldd", binary], stdout=subprocess.PIPE)
        ldd.check_returncode()
        for line in ldd.stdout.decode().splitlines():
            if match := re.match(r".*=>\s*(?P<file>\S+)", line):
                files.add(match.groupdict()["file"])

    return list(files)


def library_packages(binaries):
    packages = set()
    for file in library_files(binaries):
        rpm = subprocess.run(
            ["rpm", "-qf", file, "--queryformat", r"%{NAME}\n"],
            stdout=subprocess.PIPE,
        )
        rpm.check_returncode()
        packages.add(rpm.stdout.decode().strip())

    return list(packages)


def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dl-file",
        default="dl-file.list",
    )
    subparsers = parser.add_subparsers(dest="subparser_name")
    parser_add = subparsers.add_parser("add", help="add files to the dl-file")
    parser_add.add_argument(
        "--noglob",
        action="store_false",
        default=True,
        dest="glob",
        help="do not expand file names as globs",
    )
    parser_add.add_argument(
        "--no-follow-symlink",
        action="store_false",
        default=True,
        dest="follow_symlink",
        help="do not add symlink destination with symlink",
    )
    parser_add.add_argument(
        "--clean",
        action="store_true",
        help="clean before add",
    )
    parser_add.add_argument(
        "-f",
        "--files",
        nargs="+",
        default=[],
        help="adding files to the dl-file",
    )
    parser_add.add_argument(
        "-l",
        "--file-lists",
        nargs="+",
        default=[],
        help="adding file from file lists to the dl-file",
    )
    parser_add.add_argument(
        "--library-files",
        nargs="+",
        default=[],
        help="adding library files for binaries to the the dl-file",
    )
    parser_add.add_argument(
        "--library-packages",
        nargs="+",
        default=[],
        help="adding library packages for binaries to the the dl-file",
    )
    parser_add.add_argument(
        "-p",
        "--packages",
        nargs="+",
        default=[],
        help="adding file from packages to the dl-file",
    )
    parser_tar = subparsers.add_parser(
        "tar", help="create tar archive from the dl-file"
    )
    parser_tar.add_argument(
        "-o",
        "--outfile",
        help="path of the tar archive",
        default="distroless.tar",
    )
    parser_tar.add_argument(
        "-r",
        "--regexes",
        nargs="+",
        default=[],
        help="list of regexes, any match exclude",
    )
    subparsers.add_parser("clean", help="remove the dl-file")
    args = parser.parse_args()

    return args


def main():
    args = parse_args()
    dl = DL(args.dl_file)
    if args.subparser_name == "add":
        if args.clean:
            dl.clean()
        dl.add(
            args.files + library_files(args.library_files),
            args.file_lists,
            args.packages + library_packages(args.library_packages),
            args.glob,
            args.follow_symlink,
        )
    elif args.subparser_name == "tar":
        dl.tar(args.outfile, args.regexes)
    elif args.subparser_name == "clean":
        dl.clean()


if __name__ == "__main__":
    main()

# vim: colorcolumn=89
