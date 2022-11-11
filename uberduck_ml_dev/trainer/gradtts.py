__all__ = ["GradTTSTrainer"]


import json
import os
from pathlib import Path
from pprint import pprint
import numpy as np

import torch
from torch.cuda.amp import autocast, GradScaler
import torch.distributed as dist
from torch.nn import functional as F
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.optim.lr_scheduler import ExponentialLR
from torch.utils.data import DataLoader
from tensorboardX import SummaryWriter
import time

from ..models.common import MelSTFT
from ..utils.plot import (
    plot_attention,
    plot_gate_outputs,
    plot_spectrogram,
    plot_tensor,
)
from ..text.util import text_to_sequence, random_utterance
from ..text.symbols import symbols_with_ipa
from .base import TTSTrainer

from ..data_loader import (
    TextAudioSpeakerLoader,
    TextMelCollate,
    DistributedBucketSampler,
    TextMelDataset,
)
from ..vendor.tfcompat.hparam import HParams
from ..utils.plot import save_figure_to_numpy, plot_spectrogram
from ..utils.utils import slice_segments, clip_grad_value_
from ..text.symbols import SYMBOL_SETS


from tqdm import tqdm
from ..text.util import text_to_sequence, random_utterance
from ..models.gradtts import GradTTS
from ..utils.utils import intersperse


class GradTTSTrainer(TTSTrainer):
    REQUIRED_HPARAMS = [
        "training_audiopaths_and_text",
        "test_audiopaths_and_text",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for param in self.REQUIRED_HPARAMS:
            if not hasattr(self, param):
                raise Exception(f"GradTTSTrainer missing a required param: {param}")
        self.sampling_rate = self.hparams.sampling_rate
        self.checkpoint_path = self.hparams.log_dir

    def sample_inference(self, model, timesteps=10, spk=None):
        with torch.no_grad():
            sequence = text_to_sequence(
                random_utterance(),
                self.text_cleaners,
                1.0,
                symbol_set=self.hparams.symbol_set,
            )
            if self.hparams.intersperse_text:
                sequence = intersperse(
                    sequence, (len(SYMBOL_SETS[self.hparams.symbol_set]))
                )
            x = torch.LongTensor(sequence).cuda()[None]
            x_lengths = torch.LongTensor([x.shape[-1]]).cuda()
            y_enc, y_dec, attn = model(
                x,
                x_lengths,
                n_timesteps=50,
                temperature=1.5,
                stoc=False,
                spk=spk,
                length_scale=0.91,
            )
            if self.hparams.vocoder_algorithm == "hifigan":
                audio = self.sample(
                    y_dec,
                    algorithm=self.hparams.vocoder_algorithm,
                    hifigan_config=self.hparams.hifigan_config,
                    hifigan_checkpoint=self.hparams.hifigan_checkpoint,
                    cudnn_enabled=self.hparams.cudnn_enabled,
                )
            else:
                audio = self.sample(y_dec.cpu()[0])
            return audio

    def train(self, checkpoint=None):
        if self.distributed_run:
            self.init_distributed()

        train_dataset = TextMelDataset(
            self.hparams.training_audiopaths_and_text,
            self.hparams.text_cleaners,
            1.0,
            self.hparams.n_feats,
            self.hparams.sampling_rate,
            self.hparams.mel_fmin,
            self.hparams.mel_fmax,
            self.hparams.filter_length,
            self.hparams.hop_length,
            (self.hparams.filter_length - self.hparams.hop_length) // 2,
            self.hparams.win_length,
            intersperse_text=self.hparams.intersperse_text,
            intersperse_token=(len(SYMBOL_SETS[self.hparams.symbol_set])),
            symbol_set=self.hparams.symbol_set,
        )
        collate_fn = TextMelCollate()

        loader = DataLoader(
            dataset=train_dataset,
            batch_size=self.hparams.batch_size,
            collate_fn=collate_fn,
            drop_last=True,
            num_workers=0,
            shuffle=False,
        )

        test_dataset = TextMelDataset(
            self.hparams.test_audiopaths_and_text,
            self.hparams.text_cleaners,
            1.0,
            self.hparams.n_feats,
            self.hparams.sampling_rate,
            self.hparams.mel_fmin,
            self.hparams.mel_fmax,
            self.hparams.filter_length,
            self.hparams.hop_length,
            (self.hparams.filter_length - self.hparams.hop_length) // 2,
            self.hparams.win_length,
            intersperse_text=self.hparams.intersperse_text,
            intersperse_token=(len(SYMBOL_SETS[self.hparams.symbol_set])),
            symbol_set=self.hparams.symbol_set,
        )

        model = GradTTS(self.hparams)

        if self.hparams.checkpoint:
            model.load_state_dict(torch.load(self.hparams.checkpoint))
        model = model.cuda()

        print(
            "Number of encoder + duration predictor parameters: %.2fm"
            % (model.encoder.nparams / 1e6)
        )
        print("Number of decoder parameters: %.2fm" % (model.decoder.nparams / 1e6))
        print("Total parameters: %.2fm" % (model.nparams / 1e6))

        print("Initializing optimizer...")
        optimizer = torch.optim.Adam(
            params=model.parameters(), lr=self.hparams.learning_rate
        )
        test_batch = test_dataset.sample_test_batch(size=self.hparams.test_size)
        for i, item in enumerate(test_batch):
            text, mel, spk = item
            self.log(
                f"image_{i}/ground_truth",
                0,
                image=plot_tensor(mel.squeeze()),
            )
        iteration = 0
        last_time = time.time()
        for epoch in range(0, self.hparams.n_epochs):
            model.train()
            dur_losses = []
            prior_losses = []
            diff_losses = []
            for batch_idx, batch in enumerate(loader):
                model.zero_grad()
                x, x_lengths, y, _, y_lengths, speaker_ids = batch

                dur_loss, prior_loss, diff_loss = model.compute_loss(
                    x, x_lengths, y, y_lengths, out_size=self.hparams.out_size
                )
                loss = sum([dur_loss, prior_loss, diff_loss])
                loss.backward()

                enc_grad_norm = torch.nn.utils.clip_grad_norm_(
                    model.encoder.parameters(), max_norm=1
                )
                dec_grad_norm = torch.nn.utils.clip_grad_norm_(
                    model.decoder.parameters(), max_norm=1
                )
                optimizer.step()

                self.log("training/duration_loss", iteration, dur_loss.item())
                self.log("training/prior_loss", iteration, prior_loss.item())
                self.log("training/diffusion_loss", iteration, diff_loss.item())
                self.log("training/encoder_grad_norm", iteration, enc_grad_norm)
                self.log("training/decoder_grad_norm", iteration, dec_grad_norm)

                dur_losses.append(dur_loss.item())
                prior_losses.append(prior_loss.item())
                diff_losses.append(diff_loss.item())

                iteration += 1

            log_msg = f"Epoch {epoch}, iter: {iteration}: dur_loss: {np.mean(dur_losses):.4f} | prior_loss: {np.mean(prior_losses):.4f} | diff_loss: {np.mean(diff_losses):.4f} | time: {time.time()-last_time:.2f}s"
            last_time = time.time()
            with open(f"{self.hparams.log_dir}/train.log", "a") as f:
                f.write(log_msg + "\n")
                print(log_msg)

            if epoch % self.log_interval == 0:
                model.eval()
                with torch.no_grad():
                    for i, item in enumerate(test_batch):
                        x, _y, _speaker_id = item
                        x = x.to(torch.long).unsqueeze(0)
                        x_lengths = torch.LongTensor([x.shape[-1]])
                        y_enc, y_dec, attn = model(x, x_lengths, n_timesteps=50)
                        self.log(
                            f"image_{i}/generated_enc",
                            iteration,
                            image=plot_tensor(y_enc.squeeze().cpu()),
                        )
                        self.log(
                            f"image_{i}/generated_dec",
                            iteration,
                            image=plot_tensor(y_dec.squeeze().cpu()),
                        )
                        self.log(
                            f"image_{i}/alignment",
                            iteration,
                            image=plot_tensor(attn.squeeze().cpu()),
                        )
                        self.log(
                            f"audio/inference_{i}",
                            iteration,
                            audio=self.sample_inference(model),
                        )

            if epoch % self.save_every == 0:
                torch.save(
                    model.state_dict(),
                    f=f"{self.hparams.log_dir}/{self.checkpoint_name}_{epoch}.pt",
                )
