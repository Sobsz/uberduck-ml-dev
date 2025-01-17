# 🦆 Uberduck TTS ![](https://img.shields.io/github/forks/uberduck-ai/uberduck-ml-dev) ![](https://img.shields.io/github/stars/uberduck-ai/uberduck-ml-dev) ![](https://img.shields.io/github/issues/uberduck-ai/uberduck-ml-dev)

<h1>Table of Contents<span class="tocSkip"></span></h1>
<div class="toc">
   <ul class="toc-item">
      <li>
         <span><a href="#🦆-Uberduck-TTS---" data-toc-modified-id="🦆-Uberduck-TTS----1"><span class="toc-item-num">1&nbsp;&nbsp;</span>🦆 Uberduck TTS <img src="https://img.shields.io/github/forks/uberduck-ai/uberduck-ml-dev" alt=""> <img src="https://img.shields.io/github/stars/uberduck-ai/uberduck-ml-dev" alt=""> <img src="https://img.shields.io/github/issues/uberduck-ai/uberduck-ml-dev" alt=""></a></span>
         <ul class="toc-item">
            <li><span><a href="#Overview" data-toc-modified-id="Overview-1.0"><span class="toc-item-num">1.0&nbsp;&nbsp;</span>Overview</a></span></li>
            <li><span><a href="#Installation" data-toc-modified-id="Installation-1.1"><span class="toc-item-num">1.1&nbsp;&nbsp;</span>Installation</a></span></li>
            <li><span><a href="#Usage" data-toc-modified-id="Usage-1.2"><span class="toc-item-num">1.2&nbsp;&nbsp;</span>Usage</a></span></li>
            <li>
               <span><a href="#Development" data-toc-modified-id="Development-1.3"><span class="toc-item-num">1.3&nbsp;&nbsp;</span>Development</a></span>
               <ul class="toc-item">
                  <li><span><a href="#🚩-Testing" data-toc-modified-id="🚩-Testing-1.2.0"><span class="toc-item-num">1.2.0&nbsp;&nbsp;</span>🚩 Testing</a></span></li>
               </ul>
               <ul class="toc-item">
                  <li><span><a href="#🔧-Troubleshooting-Tips" data-toc-modified-id="🔧-Troubleshooting-Tips-1.2.1"><span class="toc-item-num">1.2.1&nbsp;&nbsp;</span>🔧 Troubleshooting Tips</a></span></li>
               </ul>
            </li>
         </ul>
      </li>
   </ul>
</div>

[**Uberduck**](https://uberduck.ai/) is a tool for fun and creativity with audio machine learning, currently focused on voice cloning and neural text-to-speech. This repository includes development tools to get started with creating your own speech synthesis model. For more information on the state of this repo, please see the [**Wiki**](https://github.com/uberduck-ai/uberduck-ml-dev/wiki).

## Overview

An overview of the subpackages in this library:

`models`: TTS model implementations. All models descend from `models.base.TTSModel`.

`trainer`: A trainer has logic for training a model.

`exec`: Contains entrypoint scripts for running training jobs. Executed via a command like
`python -m uberduck_ml_dev.exec.train_tacotron2 --your-args here`

## Installation

```
conda create -n 'uberduck-ml-dev' python=3.8
source activate uberduck-ml-dev
pip install git+https://github.com/uberduck-ai/uberduck-ml-dev.git
```

## Usage

### Training

1. Download torchmoji models if training with Torchmoji GST.

   ```bash
   wget "https://github.com/johnpaulbin/torchMoji/releases/download/files/pytorch_model.bin" -O pytorch_model.bin
   wget "https://raw.githubusercontent.com/johnpaulbin/torchMoji/master/model/vocabulary.json" -O vocabulary.json
   ```
2. Create your training config. Use the training configs in the `configs` directory as a starting point, e.g. [this one](https://github.com/uberduck-ai/uberduck-ml-dev/blob/master/configs/tacotron2_config.json).
3. Start training. Example invocation for Tacotron2 training:
   ```bash
   python -m uberduck_ml_dev.exec.train_tacotron2 --config tacotron2_config.json
   ```

### Inference

#### Tacotron2 Inference

1. No GST

    ```python
    from uberduck_ml_dev.data_loader import prepare_input_sequence
    from uberduck_ml_dev.models.tacotron2 import Tacotron2, DEFAULTS
    
    model = Tacotron2(DEFAULTS)
    inputs, input_lengths = prepare_input_sequence(["This is a test voice message"], cpu_run=True, arpabet=True)
    speaker_ids = torch.tensor([0])
    model.eval()
    with torch.no_grad():
        output = model.inference(inputs, input_lengths, speaker_ids, None)
    ```

2. Using Torchmoji as GST

   First, download torchmoji weights to your local filesystem from [here](https://github.com/huggingface/torchMoji). Then:
   
   ```python
   from uberduck_ml_dev.models.torchmoji import TorchMojiInterface
   
   torchmoji_model = TorchMojiInterface("path/to/vocab.json", "path/to/torchmoji_weights.bin")
   
   gsts = torch.tensor(torchmoji_model.encode_texts(["This is a test."]))
   gsts_repeated = gsts.repeat(1, 1).unsqueeze(1)
   # sequences, input_lengths, speaker_ids instantiation not shown here.
   output = tacotron2.inference(sequences, input_lengths, speaker_ids, gsts_repeated)
   ```

## Development

To start contributing, install the required development dependencies in a virtual environment:

```bash
pip install pre-commit black
```

Clone the repository:

```bash
git clone git@github.com:uberduck-ai/uberduck-ml-dev.git
```

Install required Git hooks:

```bash
pre-commit install
```

Install the library:

```bash
python setup.py develop
```

### 🚩 Testing

```bash
python -m pytest
```

### 🔧 Troubleshooting

- It is important for you to spell the name of your user and repo correctly in `settings.ini`. If you change the name of the repo, you have to make the appropriate changes in `settings.ini`
