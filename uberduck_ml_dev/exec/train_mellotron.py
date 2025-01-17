__all__ = ["run"]


import argparse
import json
import librosa  # NOTE(zach): importing torch before librosa causes LLVM issues for some unknown reason.
import sys

import torch
from torch import multiprocessing as mp

from ..trainer.mellotron import MellotronTrainer
from ..vendor.tfcompat.hparam import HParams
from ..models.mellotron import DEFAULTS as MELLOTRON_DEFAULTS
from ..utils.argparse import parse_args


def run(rank, device_count, hparams):
    trainer = MellotronTrainer(hparams, rank=rank, world_size=device_count)
    try:
        trainer.train()
    except Exception as e:
        print(f"Exception raised while training: {e}")
        # TODO: save state.
        raise e


try:
    from nbdev.imports import IN_NOTEBOOK
except:
    IN_NOTEBOOK = False
if __name__ == "__main__" and not IN_NOTEBOOK:
    args = parse_args(sys.argv[1:])
    config = MELLOTRON_DEFAULTS.values()
    if args.config:
        with open(args.config) as f:
            config.update(json.load(f))
    hparams = HParams(**config)
    if hparams.distributed_run:
        device_count = torch.cuda.device_count()
        mp.spawn(run, (device_count, hparams), device_count)
    else:
        run(None, None, hparams)
