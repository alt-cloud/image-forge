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

    def add(self, sources, is_glob=True, file_list=False, package=False):
        def ensuere_one_endl(s):
            return s.rstrip("\n") + "\n"

        def write_globs(is_glob, source, dl_file):
            if is_glob:
                for file in glob.glob(source.rstrip("\n")):
                    dl_file.write(ensuere_one_endl(file))
            else:
                dl_file.write(ensuere_one_endl(source))


        with open(self.dl_file, "a") as dl_file:
            for source in sources:
                if file_list:
                    with open(source) as source_list:
                        for line in source_list:
                            write_globs(is_glob, line, dl_file)
                elif package:
                    proc = subprocess.run(
                        ["rpm", "-ql", source], stdout=subprocess.PIPE
                    )
                    proc.check_returncode()
                    for line in proc.stdout.decode().splitlines():
                        dl_file.write(ensuere_one_endl(line))
                else:
                    write_globs(is_glob, source, dl_file)

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
        "sources",
        nargs="+",
        help="adding source to the dl-file",
    )
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
    add_source_type = parser_add.add_mutually_exclusive_group()
    add_source_type.add_argument(
        "-f",
        "--file-list",
        action="store_true",
        help="treat source as file with list of needed to add files",
    )
    add_source_type.add_argument(
        "-p",
        "--package",
        action="store_true",
        help="treat source as package name and add all its files",
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
        dl.add(args.sources, args.glob, args.file_list, args.package)
    elif args.subparser_name == "tar":
        dl.tar(args.outfile, args.regexes)
    elif args.subparser_name == "clean":
        dl.clean()


if __name__ == "__main__":
    main()

# vim: colorcolumn=89
