import torch

from .studio.src.models.stylegan2 import Generator
from .studio.src.utils import legacy
from .studio.src.utils.style_ops import dnnlib


def load_rosinality2ada(path, blur_scale=4):
    state_dict = torch.load(path)
    state_ros = state_dict["g_ema"]
    state_nv = {}

    state_nv[f"synthesis.b4.const"] = state_ros[f"input.input"].squeeze(0)

    state_nv[f"synthesis.b4.conv1.noise_const"] = state_ros[f"noises.noise_0"].squeeze(0).squeeze(0)

    state_nv[f"synthesis.b4.conv1.weight"] = state_ros[f"conv1.conv.weight"].squeeze(0)
    state_nv[f"synthesis.b4.conv1.bias"] = state_ros[f"conv1.activate.bias"]
    state_nv[f"synthesis.b4.conv1.affine.weight"] = state_ros[f"conv1.conv.modulation.weight"]
    state_nv[f"synthesis.b4.conv1.affine.bias"] = state_ros[f"conv1.conv.modulation.bias"]
    state_nv[f"synthesis.b4.conv1.noise_strength"] = state_ros[f"conv1.noise.weight"].squeeze(0)

    state_nv[f"synthesis.b4.torgb.weight"] = state_ros[f"to_rgb1.conv.weight"].squeeze(0)
    state_nv[f"synthesis.b4.torgb.bias"] = state_ros[f"to_rgb1.bias"].squeeze(-1).squeeze(-1).squeeze(0)
    state_nv[f"synthesis.b4.torgb.affine.weight"] = state_ros[f"to_rgb1.conv.modulation.weight"]
    state_nv[f"synthesis.b4.torgb.affine.bias"] = state_ros[f"to_rgb1.conv.modulation.bias"]
    state_nv[f"synthesis.b4.resample_filter"] = state_ros[f"convs.0.conv.blur.kernel"] / blur_scale
    state_nv[f"synthesis.b4.conv1.resample_filter"] = state_ros[f"convs.0.conv.blur.kernel"] / blur_scale

    max_res, num_map = 4, 1
    for key, val in state_ros.items():
        if key.startswith("style"):
            _, num, weight_or_bias = key.split(".")
            state_nv[f"mapping.fc{int(num) - 1}.{weight_or_bias}"] = val

            if int(num) > num_map:
                num_map = int(num)

        if key.startswith("noises"):
            n = int(key.split("_")[1])
            r = 2 ** (3 + (n - 1) // 2)
            state_nv[f"synthesis.b{r}.conv{(n-1)%2}.noise_const"] = state_ros[f"noises.noise_{n}"].squeeze(0).squeeze(0)

        if key.startswith("convs"):
            n = int(key.split(".")[1])
            r = 2 ** (3 + n // 2)
            nv_block = f"synthesis.b{r}"
            ros_name = ".".join(key.split(".")[2:])

            if ros_name == "conv.weight":
                state_nv[f"{nv_block}.conv{n % 2}.weight"] = state_ros[f"convs.{n}.conv.weight"].squeeze(0)
            elif ros_name == "activate.bias":
                state_nv[f"{nv_block}.conv{n % 2}.bias"] = state_ros[f"convs.{n}.activate.bias"]
            elif ros_name == "conv.modulation.weight":
                state_nv[f"{nv_block}.conv{n % 2}.affine.weight"] = state_ros[f"convs.{n}.conv.modulation.weight"]
            elif ros_name == "conv.modulation.bias":
                state_nv[f"{nv_block}.conv{n % 2}.affine.bias"] = state_ros[f"convs.{n}.conv.modulation.bias"]
            elif ros_name == "noise.weight":
                state_nv[f"{nv_block}.conv{n % 2}.noise_strength"] = state_ros[f"convs.{n}.noise.weight"].squeeze(0)
            elif ros_name == "conv.blur.kernel":
                state_nv[f"{nv_block}.conv0.resample_filter"] = state_ros[f"convs.{n}.conv.blur.kernel"] / blur_scale
                state_nv[f"{nv_block}.conv1.resample_filter"] = state_ros[f"convs.{n}.conv.blur.kernel"] / blur_scale
            else:
                raise Exception(f"Key {key} not recognized!")

            if r > max_res:
                max_res = r

        if key.startswith("to_rgbs"):
            n = int(key.split(".")[1])
            r = 2 ** (3 + n)
            nv_block = f"synthesis.b{r}"
            ros_name = ".".join(key.split(".")[2:])

            if ros_name == "conv.weight":
                state_nv[f"{nv_block}.torgb.weight"] = state_ros[f"to_rgbs.{n}.conv.weight"].squeeze(0)
            elif ros_name == "bias":
                state_nv[f"{nv_block}.torgb.bias"] = state_ros[f"to_rgbs.{n}.bias"].squeeze(-1).squeeze(-1).squeeze(0)
            elif ros_name == "conv.modulation.weight":
                state_nv[f"{nv_block}.torgb.affine.weight"] = state_ros[f"to_rgbs.{n}.conv.modulation.weight"]
            elif ros_name == "conv.modulation.bias":
                state_nv[f"{nv_block}.torgb.affine.bias"] = state_ros[f"to_rgbs.{n}.conv.modulation.bias"]
            elif ros_name == "upsample.kernel":
                state_nv[f"{nv_block}.resample_filter"] = state_ros[f"to_rgbs.{n}.upsample.kernel"] / blur_scale
            else:
                raise Exception(f"Key {key} not recognized!")

    if "latent_avg" in state_dict:
        state_nv["mapping.w_avg"] = state_dict["latent_avg"]
    else:
        state_nv["mapping.w_avg"] = torch.zeros(512)  # TODO

    z_dim = 512  # TODO
    w_dim = 512  # TODO
    c_dim = 0  # TODO
    chnls = 3  # TODO

    G = Generator(z_dim, c_dim, w_dim, max_res, chnls, mapping_kwargs=dict(num_layers=num_map))
    G.load_state_dict(state_nv)

    return G


def load_nvidia(path):
    with dnnlib.util.open_url(path) as f:
        G_persistence = legacy.load_network_pkl(f)["G_ema"]

    # create new Generator class to avoid the uninformative errors from NVIDIA's persistence system
    G = Generator(
        G_persistence.mapping.z_dim,
        G_persistence.mapping.c_dim,
        G_persistence.mapping.w_dim,
        G_persistence.img_resolution,
        G_persistence.img_channels,
        mapping_kwargs=dict(num_layers=G_persistence.mapping.num_layers),
    )
    G.load_state_dict(G_persistence.state_dict())

    del G_persistence
    return G


def load_network(path):
    errors = {}

    for name, loader in [
        ("NVIDIA StyleGAN3 loader", load_nvidia),
        ("Rosinality StyleGAN2 to ADA-PT converter", load_rosinality2ada),
    ]:
        try:
            return loader(path)
        except Exception as e:
            errors[name] = e

    error_str = "\n".join([f"{k}: {v}" for k, v in errors.items()])
    raise Exception(f"Error loading checkpoint! None of the converters succeeded:\n{error_str}")
