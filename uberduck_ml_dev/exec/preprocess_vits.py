__all__ = ["batch", "flatten"]


import argparse
from functools import reduce

from ..text.util import batch_clean_text, clean_text
from ..utils.utils import load_filepaths_and_text


def batch(arr, batch_size):
    for i in range(0, len(arr), batch_size):
        yield arr[i : i + batch_size]


def flatten(arr):
    """Flatten list of lists.

    Only works for depth of 1.
    """
    return reduce(lambda a, b: a + b, arr)


try:
    from nbdev.imports import IN_NOTEBOOK
except:
    IN_NOTEBOOK = False

if __name__ == "__main__" and not IN_NOTEBOOK:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out_extension", default="cleaned")
    parser.add_argument("--text_index", default=1, type=int)
    parser.add_argument(
        "--filelists",
        nargs="+",
        default=[
            "filelists/ljs_audio_text_val_filelist.txt",
            "filelists/ljs_audio_text_test_filelist.txt",
        ],
    )
    parser.add_argument(
        "--text_cleaners", nargs="+", default=["english_cleaners_phonemizer"]
    )

    args = parser.parse_args()

    for filelist in args.filelists:
        print("START:", filelist)
        filepaths_and_text = load_filepaths_and_text(filelist)
        text_batches = batch([fat[args.text_index] for fat in filepaths_and_text], 100)
        cleaned_text_batch = flatten(
            [batch_clean_text(batch, args.text_cleaners) for batch in text_batches]
        )

        for i in range(len(filepaths_and_text)):
            filepaths_and_text[i][args.text_index] = cleaned_text_batch[i]

        new_filelist = filelist + "." + args.out_extension
        with open(new_filelist, "w", encoding="utf-8") as f:
            f.writelines(["|".join(x) + "\n" for x in filepaths_and_text])
