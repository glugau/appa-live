"""
Script for autoregressive forecasting experiments.
Modified from appa/experiments/observations/forecast_ar.py
"""
import math
import torch
import logging
import os

from functools import partial
from omegaconf import open_dict
from pathlib import Path
from tqdm import tqdm

from appa.config.hydra import compose
from appa.date import add_hours, create_trajectory_timestamps
from appa.diffusion import Denoiser, MMPSDenoiser, create_schedule
from appa.grid import num_icosphere_vertices
from appa.nn.autoencoder import AutoEncoder
from appa.nn.triggers import skip_init
from appa.observations import observator_full
from appa.sampling import LMSSampler, PCSampler
from appa.save import load_denoiser, safe_load, safe_save
from custom_datasets import CustomLatentBlanketDataset

def forecast_ar(
    denoiser_model_path: os.PathLike,
    autoencoder_model_path: os.PathLike,
    latent_data_path: os.PathLike,
    latents_stats_path: os.PathLike,
    model_target: str,
    diffusion,
    assimilation_length: int,
    lead_time: int,
    preds_per_step: int,
    past_window_size: int,
    start_date: str,
    start_hour: int,
    precision,
    target_dir: os.PathLike,
    autoencoder: AutoEncoder = None,
):
    r"""Performs autoregressive forecasting.

    Args:
        denoiser_model_path: Path to the denoiser model directory.
        denoiser_model_path: Path to the autoencoder model directory.
        latent_data_path: Path to the latent data on which to condition the forecast.
        latents_stats_path: Path to the stats.pth file
        model_target: Target model to load (best or last).
        diffusion: Diffusion configuration dictionary:
            - num_steps: Number of diffusion steps.
            - mmps_iters: Number of iterations for MMPS.
            - sampler: Sampler configuration dictionary:
                - type: Type of sampler (pc or lms).
                - config: Configuration for the sampler.
        assimilation_length: Length of the assimilation window.
        lead_time: Total number of states to predict.
        preds_per_step: States to save per autoregressive step.
        past_window_size: Size of the sliding conditioning window.
        start_date: Date of the first predicted state (YYYY-MM-DD format).
        start_hour: Hour of the first predicted state (0-23).
        precision: Precision for the computation (e.g., float16).
        target_dir: Directory to save the results in.
        autoencoder: Loaded autoencoder (if desired, to speed up the process).
    """
        
    device = "cuda"
    logger = logging.getLogger(__name__)

    # Model and configs
    denoiser_model_path = Path(denoiser_model_path)
    ae_cfg = compose(Path(autoencoder_model_path) / "config.yaml")
    denoiser_cfg = compose(Path(denoiser_model_path) / "config.yaml")
    precision = getattr(torch, precision)
    use_bfloat16 = precision == torch.bfloat16
    trajectory_dt = denoiser_cfg.train.blanket_dt
    blanket_size = denoiser_cfg.train.blanket_size
    if diffusion.num_steps is None:
        diffusion_steps = denoiser_cfg.valid.denoising_steps
    else:
        diffusion_steps = diffusion.num_steps

    lead_time = lead_time // trajectory_dt

    if preds_per_step == "auto" and past_window_size == "auto":
        past_window_size = blanket_size // 2
        preds_per_step = blanket_size - past_window_size
    elif preds_per_step == "auto":
        preds_per_step = blanket_size - past_window_size
    elif past_window_size == "auto":
        past_window_size = blanket_size - preds_per_step

    start_date_initcond, start_hour_initcond = add_hours(
        start_date, start_hour, -assimilation_length * trajectory_dt
    )
    start_date_initblanket, start_hour_initblanket = add_hours(
        start_date, start_hour, -past_window_size * trajectory_dt
    )
    
    logger.info(f'Loading {latent_data_path}')
    
    latent_ds = CustomLatentBlanketDataset(
        path=Path(latent_data_path),
        latent_stats_path=Path(latents_stats_path),
        start_date=start_date_initcond,
        start_hour=start_hour_initcond,
        end_date=start_date_initcond,
        end_hour=start_hour_initcond,
        blanket_size=blanket_size,
        standardize=True,
        stride=trajectory_dt,
    )
    
    logger.info(f'Loading {latents_stats_path}')
    latent_stats = safe_load(latents_stats_path)
    latent_mean = latent_stats["mean"].cuda()
    latent_std = latent_stats["std"].cuda()
    latent_std = torch.sqrt(latent_std**2 + ae_cfg.ae.noise_level**2)
    cov_z = (ae_cfg.ae.noise_level / latent_std) ** 2
    
    if autoencoder is None:
        ae_model_path = Path(autoencoder_model_path) / 'model_best.pth'
        logger.info(f'Loading {ae_model_path}')
        ae_ckpt = safe_load(ae_model_path, map_location=device)
        with open_dict(ae_cfg):
            ae_cfg.ae.checkpointing = True
            ae_cfg.ae.noise_level = 0.0
        with skip_init():
            autoencoder = AutoEncoder(**ae_cfg.ae)
        autoencoder.decoder.cuda()
        autoencoder.load_state_dict(ae_ckpt)
        del ae_ckpt
    autoencoder.eval()
    autoencoder.requires_grad_(False)

    input_vertices = num_icosphere_vertices(ae_cfg.ae.ico_divisions[-1])
    latent_channels = ae_cfg.ae.latent_channels

    schedule = create_schedule(denoiser_cfg.train).to(device)
    backbone = load_denoiser(
        denoiser_model_path, best=model_target == "best", overrides={"checkpointing": True}
    ).backbone.to(device)
    backbone.requires_grad_(False)

    cond_start_idx = past_window_size - assimilation_length

    z_obs, init_date = latent_ds[0]
    z_obs, init_date = z_obs[:assimilation_length], init_date[:assimilation_length]

    z_obs_cov = cov_z[None][None].expand(*z_obs.shape[:-1], latent_channels)
    z_obs = z_obs.flatten()
    z_obs_cov = z_obs_cov.flatten()

    saved_states = []
    saved_timestamps = []

    current_traj_size = 0

    num_steps = math.ceil(lead_time / preds_per_step)
    max_traj_size = assimilation_length + lead_time

    for step in tqdm(range(num_steps), desc = 'Forecasting'):
        timestamps = create_trajectory_timestamps(
            start_day=start_date_initblanket,
            start_hour=start_hour_initblanket,
            traj_size=blanket_size,
            dt=trajectory_dt,
        )[None]

        def obs_slice_fn(_, cond_start_idx=cond_start_idx):
            return slice(cond_start_idx, past_window_size)

        A = partial(
            observator_full,
            blanket_size=blanket_size,
            num_latent_channels=latent_channels,
            slice_fn=obs_slice_fn,
        )

        denoise = Denoiser(backbone).cuda()
        if use_bfloat16:
            denoise = denoise.to(torch.bfloat16)

        denoise = MMPSDenoiser(
            denoise, A, z_obs.cuda(), z_obs_cov.cuda(), iterations=diffusion.mmps_iters
        )
        denoise = partial(denoise, date=timestamps.cuda())

        with torch.no_grad():
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                if diffusion.sampler.type == "pc":
                    sampler = PCSampler
                elif diffusion.sampler.type == "lms":
                    sampler = LMSSampler
                else:
                    raise ValueError(f"Unknown sampler type: {diffusion.sampler.type}")

                sampler = sampler(
                    denoise,
                    steps=diffusion_steps,
                    schedule=schedule,
                    silent=False,
                    **diffusion.sampler.config,
                )
                x1 = torch.randn(1, blanket_size * input_vertices * latent_channels).cuda()
                samp_start = (x1 * schedule.sigma_tmax().cuda()).flatten(1).cuda()
                sample = (
                    sampler(samp_start)
                    .reshape((-1, blanket_size, input_vertices, latent_channels))
                    .cpu()
                )

        if step == 0:
            saved_states.append(sample[:, cond_start_idx:past_window_size])
            saved_timestamps.append(timestamps[:, cond_start_idx:past_window_size])

        saved_states.append(sample[:, past_window_size : past_window_size + preds_per_step])
        saved_timestamps.append(
            timestamps[:, past_window_size : past_window_size + preds_per_step]
        )

        z_obs = sample[:, cond_start_idx : past_window_size + preds_per_step][
            :, -past_window_size:
        ].cuda()
        z_obs_cov = cov_z[None][None].expand(*z_obs.shape[:-1], latent_channels)
        z_obs = z_obs.flatten()
        z_obs_cov = z_obs_cov.flatten()

        cond_start_idx = max(0, cond_start_idx - preds_per_step)

        start_date_initblanket, start_hour_initblanket = add_hours(
            start_date_initblanket,
            start_hour_initblanket,
            preds_per_step * trajectory_dt,
        )
        total_state = torch.cat(saved_states, dim=1)
        total_timestamps = torch.cat(saved_timestamps, dim=1)

        if total_state.shape[1] >= max_traj_size:
            total_state = total_state[:, :max_traj_size]
            total_timestamps = total_timestamps[:, :max_traj_size]

        safe_save(total_state, Path(target_dir) / "trajectory.pt")
        safe_save(total_timestamps, Path(target_dir) / "timestamps.pt")

        current_traj_size = total_state.shape[1]

        if current_traj_size == max_traj_size:
            return

if __name__ == "__main__":
    pass
