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

    def add(self, files, file_lists, packages, is_glob=True):
        def ensuere_one_endl(s):
            return s.rstrip("\n") + "\n"

        def write_globs(is_glob, source, dl_file):
            if is_glob:
                for file in glob.glob(source.rstrip("\n")):
                    dl_file.write(ensuere_one_endl(file))
            else:
                dl_file.write(ensuere_one_endl(source))

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
                        dl_file.write(ensuere_one_endl(filename))

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
        help="clean before add",
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
        dl.add(args.files, args.file_lists, args.packages, args.glob)
    elif args.subparser_name == "tar":
        dl.tar(args.outfile, args.regexes)
    elif args.subparser_name == "clean":
        dl.clean()


if __name__ == "__main__":
    main()

# vim: colorcolumn=89
