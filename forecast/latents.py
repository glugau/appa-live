"""
Encode ERA5 into latent space with an AE.
Modified from appa/experiments/autoencoder/dump.py
"""

import dask
import h5py
import torch

from einops import rearrange
from pathlib import Path
from tqdm import tqdm
from typing import Sequence

from appa.data.dataloaders import get_dataloader
from appa.data.datasets import ERA5Dataset
from appa.data.transforms import StandardizeTransform
from appa.nn.autoencoder import AutoEncoder


def compute_and_save_latents(
    autoencoder: AutoEncoder,
    path_data: Path,
    path_output: Path,
    path_data_statistics: Path,
    variables: Sequence[str],
    ctx_variables: Sequence[str],
    pressure_levels: Sequence[int],
    batch_size: int,
    start_date: str,
    end_date: str,
    save_every: int = 100,
) -> None:
    r"""Computes the latents for a dataset and saves the results to disk.

    Arguments:
        autoencoder (AutoEncoder): Trained autoencoder used to encode.
        path_data (Path): Path to the dataset.
        path_output (Path): Path to save the final output .h5 file.
        path_data_statistics (Path): Path to .zarr data statistics file.
        variables (Sequence[str]): Ordered list of variables to be saved in
            latent space, excluding the context variables.
        ctx_variables (Sequence[str]): Ordered list of context variables used
            in the dataset
        pressure_levels (Sequence[int]): Ordered list of pressure levels used
            in the dataset
        batch_size (int): Number of samples processed at once.
        start_date (str): Start date in (YYYY-MM-DD) format.
        end_date (str): End date in (YYYY-MM-DD) format.
        save_every (int): Number of batches accumulated before saving.
    """

    dask.config.set(scheduler="synchronous")

    st = StandardizeTransform(
        path_data_statistics,
        state_variables=variables,
        context_variables=ctx_variables,
        levels=pressure_levels,
    )
    dataset = ERA5Dataset(
        path=path_data,
        start_date=start_date,
        end_date=end_date,
        num_samples=None,
        transform=st,
        trajectory_size=1,
        state_variables=variables,
        context_variables=ctx_variables,
        levels=pressure_levels,
    )

    dataloader = get_dataloader(
        dataset,
        batch_size=batch_size,
        num_workers=7,
        prefetch_factor=2,
        shuffle=False,
    )

    latents = []
    dates = []

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    autoencoder = autoencoder.to(device)
    autoencoder.eval()

    current_idx = 0

    with h5py.File(path_output, "w") as f:
        for b, (state, context, date) in enumerate(tqdm(dataloader, ncols=88)):
            with torch.no_grad():
                state = rearrange(
                    state.to(device, non_blocking=True), "B T Z Lat Lon -> (B T) (Lat Lon) Z"
                )
                context = rearrange(
                    context.to(device, non_blocking=True), "B T Z Lat Lon -> (B T) (Lat Lon) Z"
                )
                date = rearrange(date.to(device, non_blocking=True), "B T D -> (B T) D")

                z = autoencoder.encode(state, date, context)

            if b == 0:
                h5_data = f.create_dataset(
                    "latents",
                    shape=(len(dataset), *z.shape[1:]),
                    dtype="float32",
                )
                h5_date = f.create_dataset(
                    "dates",
                    shape=(len(dataset), *date.shape[1:]),
                    dtype="int32",
                )

                h5_data[:batch_size] = z.cpu().numpy()
                h5_date[:batch_size] = date.cpu().numpy()
                current_idx += z.shape[0]
                continue

            latents.append(z.cpu())
            dates.append(date.cpu())

            if (b + 1) % save_every == 0:
                latents = torch.cat(latents)
                dates = torch.cat(dates)

                h5_data[current_idx : current_idx + latents.shape[0]] = latents.numpy()
                h5_date[current_idx : current_idx + dates.shape[0]] = dates.numpy()
                current_idx += latents.shape[0]

                latents = []
                dates = []

        if len(latents) > 0:
            latents = torch.cat(latents)
            dates = torch.cat(dates)

            h5_data[current_idx : current_idx + latents.shape[0]] = latents.numpy()
            h5_date[current_idx : current_idx + dates.shape[0]] = dates.numpy()