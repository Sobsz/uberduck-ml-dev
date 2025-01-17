__all__ = []


import argparse
import os
from tempfile import NamedTemporaryFile
from typing import List
import sys
from zipfile import ZipFile


def _gather(filelist, output):
    with open(filelist, "r") as f:
        lines = f.readlines()
    paths = []
    for line in lines:
        path, *_rest = line.split("|")

    paths = [l.split("|")[0] for l in lines]
    common_prefix = os.path.commonpath(paths)
    archive_paths = []
    archive_lines = []
    for line in lines:
        p, txn, *_rest = line.split("|")
        relpath = os.path.relpath(p, common_prefix)
        archive_paths.append(relpath)
        archive_lines.append(f"{relpath}|{txn}|{''.join(_rest)}")
    _, filelist_archive = os.path.split(filelist)
    with NamedTemporaryFile("w") as tempfile:
        for line in archive_lines:
            tempfile.write(line)
        tempfile.flush()
        with ZipFile(output, "w") as zf:
            zf.write(tempfile.name, filelist_archive)
            for path, archive_path in zip(paths, archive_paths):
                zf.write(path, archive_path)


def _parse_args(args: List[str]):
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", help="Path to input filelist")
    parser.add_argument(
        "-o",
        "--output",
        help="Output zipfile",
        default="out.zip",
    )
    return parser.parse_args(args)


try:
    from nbdev.imports import IN_NOTEBOOK
except:
    IN_NOTEBOOK = False

if __name__ == "__main__" and not IN_NOTEBOOK:
    args = _parse_args(sys.argv[1:])
    _gather(args.input, args.output)
