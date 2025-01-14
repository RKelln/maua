import argparse
from pathlib import Path
from typing import Generator

import torch
from PIL import Image
from tqdm import tqdm

from maua.ops.tensor import tensor2img

from .models import bsrgan, latent_diffusion, realesrgan, swinir, waifu

MODEL_MODULES = {
    "latent-diffusion": latent_diffusion,
    "RealESRGAN-x4plus": realesrgan,
    "RealESRGAN-x4plus-anime": realesrgan,
    "RealESRGAN-xsx4-animevideo": realesrgan,
    "RealESRGAN-pbaylies-wikiart": realesrgan,
    "RealESRGAN-pbaylies-hr-paintings": realesrgan,
    "SwinIR-L-DFOWMFC-GAN": swinir,
    "SwinIR-L-DFOWMFC-PSNR": swinir,
    "SwinIR-M-DFO-GAN": swinir,
    "SwinIR-M-DFO-PSNR": swinir,
    "waifu2x-anime-noise0": waifu,
    "waifu2x-anime-noise1": waifu,
    "waifu2x-anime-noise2": waifu,
    "waifu2x-anime-noise3": waifu,
    "waifu2x-photo-noise0": waifu,
    "waifu2x-photo-noise1": waifu,
    "waifu2x-photo-noise2": waifu,
    "waifu2x-photo-noise3": waifu,
    "CARN": waifu,
    "BSRGAN": bsrgan,
    "RealSR": bsrgan,
}
MODEL_NAMES = list(MODEL_MODULES.keys())


def upscale(
    images, model_name, device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
) -> Generator[torch.Tensor, None, None]:

    module = MODEL_MODULES[model_name]
    model = module.load_model(
        model_name.replace("RealESRGAN-", "").replace("SwinIR-", "").replace("waifu2x", "upconv"), torch.device(device)
    )
    for img in module.upscale(images, model):
        yield img


def main(args):
    module = MODEL_MODULES[args.model_name]
    model = module.load_model(
        args.model_name.replace("RealESRGAN-", "").replace("SwinIR-", "").replace("waifu2x", "upconv"),
        torch.device(args.device),
    )
    for img, path in tqdm(zip(module.upscale(args.images, model), args.images), total=len(args.images)):
        tensor2img(img).save(f"{args.out_dir}/{Path(path).stem}_{args.model_name}.png")


def argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("images", nargs="+")
    parser.add_argument("--model_name", default="latent-diffusion", choices=MODEL_NAMES)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--out_dir", default="output/")
    return parser
