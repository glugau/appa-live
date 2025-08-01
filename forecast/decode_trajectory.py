from appa.config.hydra import compose
from appa.save import safe_load
from appa.nn.triggers import skip_init
from appa.nn.autoencoder import AutoEncoder
from appa.data.transforms import StandardizeTransform

from omegaconf import open_dict
from os import PathLike
from datetime import datetime
from einops import rearrange
from tqdm import tqdm
from typing import Sequence
from pathlib import Path
from forecast import metadata

import torch
import logging
import os
import xarray as xr
import numpy as np

def decode_to_zarr(
    path_ae: PathLike,
    path_trajectory: PathLike,
    path_timestamps: PathLike,
    path_latent_stats: PathLike,
    path_data_stats: PathLike,
    path_destination: PathLike,
    variables: Sequence[str],
    ctx_variables: Sequence[str],
    pressure_levels: Sequence[int],
    batch_size: int = 1,
    autoencoder: AutoEncoder = None,
) -> None :
    """Decode a trajectory provided by the forecasting script into a zarr file
    containing all variables with units attached.

    Args:
        path_ae (PathLike): Path to the autoencoder model data
        path_trajectory (PathLike): Path to the trajectory to decode
        path_timestamps (PathLike): Path to the timestamps file
        path_latent_stats (PathLike): Path to the latent statistics file
        path_data_stats (PathLike): Path to the (.zarr) statistics file
        path_destination (PathLike): Path to the destination .zarr file
        variables (Sequence[str]): Ordered list of the variables present in the
            trajectory to decode.
        ctx_variables (Sequence[str]): Ordered list of the context variables
            used in the dataset.
        pressure_levels (Sequence[int]): Ordered list of the pressure levels
            present in the (multi-pressure-level) variables to be decoded
        batch_size (int, optional): How many timestamps to process at once.
            Defaults to 1.
        autoencoder (AutoEncoder, optional): The loaded autoencoder. If not given,
            it will be loaded here.
    """
    logger = logging.getLogger(__name__)
    path_ae = Path(path_ae)
    
    if autoencoder is None:
        logger.info(f'Loading the autoencoder from {path_ae}')
        autoencoder, noise_level = get_ae(path_ae)
    else:
        ae_cfg = compose(path_ae / 'config.yaml')
        noise_level = ae_cfg.ae.noise_level
    
    logger.info(f'Decoding the data')
    decoded_array, timestamps = decode_to_array(
        ae=autoencoder,
        noise_level=noise_level,
        path_trajectory=path_trajectory,
        path_timestamps=path_timestamps,
        path_latent_stats=path_latent_stats,
        path_data_stats=path_data_stats,
        variables=variables,
        ctx_variables=ctx_variables,
        pressure_levels=pressure_levels,
        batch_size=batch_size
    )
    
    logger.info('Transforming the data into an xarray')
    ds = array_to_dataset(
        decoded_array,
        timestamps,
        variables,
        pressure_levels,
        path_data_stats
    )
    
    logger.info('Converting units and attaching them to the dataset')
    ds = metadata.convert_units(ds)
    ds = metadata.attach_metadata(ds)
    
    logger.info(f'Saving the decoded data in zarr format to {path_destination}')
    ds.to_zarr(path_destination, zarr_format=2, consolidated=True)
    
def get_ae(
    path_ae: PathLike
) -> tuple[AutoEncoder, float] :
    """Loads the autoencoder to be used to decode the trajectory.

    Args:
        path_ae (PathLike): Path to the autoencoder model data

    Returns:
        (ae, noise_level) (tuple[AutoEncoder, float]): A tuple containing the
        loaded autoencoder along with the noise level obtained from the model's
        config file.
    """
    ae_cfg = compose(path_ae / 'config.yaml')
    ae_ckpt = safe_load(path_ae / 'model_best.pth', map_location="cuda")
    noise_level = ae_cfg.ae.noise_level
    with open_dict(ae_cfg):
        ae_cfg.ae.checkpointing = True
        ae_cfg.ae.noise_level = 0.0
    with skip_init():
        ae = AutoEncoder(**ae_cfg.ae)
    ae.cuda()
    ae.load_state_dict(ae_ckpt)
    del ae_ckpt
    ae.eval()
    ae.requires_grad_(False)
    
    return ae, noise_level

def decode_to_array(
    ae: torch.nn.Module,
    noise_level: float,
    path_trajectory: PathLike,
    path_timestamps: PathLike,
    path_latent_stats: PathLike,
    path_data_stats: PathLike,
    variables: Sequence[str],
    ctx_variables: Sequence[str],
    pressure_levels: Sequence[int],
    batch_size: int = 1
) -> tuple[np.ndarray, np.ndarray] :
    """Decodes a latent trajectory into a numpy array.

    Args:
        ae (torch.nn.Module): Autoencoder pytorch module
        noise_level (float): Noise level
        path_trajectory (PathLike): Path to the trajectory to decode
        path_timestamps (PathLike): Path to the timestamps file
        path_latent_stats (PathLike): Path to the latent statistics file
        path_data_stats (PathLike): Path to the (.zarr) data statistics file
        variables (Sequence[str]): Ordered list of the variables present in the
            trajectory to decode.
        ctx_variables (Sequence[str]): Ordered list of the context variables
            used in the dataset.
        pressure_levels (Sequence[int]): Ordered list of the pressure levels
            present in the (multi-pressure-level) variables to be decoded
        batch_size (int, optional): How many timestamps to process at once.
            Defaults to 1.

    Returns:
        (data, timestamps) (tuple[np.ndarray, np.ndarray]): Tuple containing the
            decoded data along with the timestamps. `data` has shape (T Z Lat Lon)
            and `timestamps` has shape (T, 4), where for each entry the time is
            stored as [Year, Month, Day, Hour].
    """
    logger = logging.getLogger(__name__)

    # Load trajectory & timestamps
    logger.info('Loading trajectory and timestamps')
    trajectory = torch.load(path_trajectory, weights_only=False).cuda()
    timestamps = torch.load(path_timestamps, weights_only=False)
    timestamps = timestamps.squeeze(0)
    trajectory = trajectory.squeeze(0)

    # Denormalize the latent data
    latent_stats = torch.load(path_latent_stats, weights_only=False)
    latent_mean = latent_stats["mean"].cuda()
    latent_std = torch.sqrt(latent_stats["std"] ** 2 + noise_level ** 2).cuda()
    latents = trajectory * latent_std + latent_mean # Shape [hrs, 642, 256]

    num_timesteps = latents.shape[0]
    decoded_data = []

    st = StandardizeTransform(
        path_data_stats,
        state_variables=variables,
        context_variables=ctx_variables,
        levels=pressure_levels,
    )

    for i in tqdm(range(0, num_timesteps, batch_size), desc='Decoding latents'):
        batch = latents[i:i+batch_size].cuda()
        with torch.no_grad():
            recon = ae.decode(batch)
        recon = recon.cpu()
        recon = rearrange(recon, "T (Lat Lon) Z -> T Z Lat Lon", Lat=721, Lon=1440)
        unstd = st.unstandardize(recon)[0]
        for sample in unstd:
            decoded_data.append(sample)

    return torch.stack(decoded_data).numpy(), timestamps.numpy()

def array_to_dataset(
    array: np.ndarray,
    timestamps: np.ndarray,
    variables: Sequence[str],
    pressure_levels: Sequence[int],
    path_sample_dataset_zarr: os.PathLike,
) -> xr.Dataset :
    """Transforms an array of data points into an xarray dataset.

    Args:
        array (np.ndarray): Array of variables, with dimension (T, Z, Lat, Lon)
        timestamps (np.ndarray): Array of timestamps, with dimension (T, 4), 
            with each timestamp being ordered as [year, month, day, hour]
        variables (Sequence[str]): List of variable names
        pressure_levels (Sequence[int]): List of pressure levels present in the
            variables
        path_sample_dataset_zarr (os.PathLike): Path to a dataset with similar
            structure to extract information about which variables have pressure
            levels

    Returns:
        xr.Dataset: The output dataset
    """     
    sample_ds = xr.open_zarr(str(path_sample_dataset_zarr))
    
    timestamps_dt = [np.datetime64(datetime(y, m, d, h)) for y, m, d, h in timestamps]
        
    ds = xr.Dataset(coords={
        'time': timestamps_dt,
        'latitude': np.linspace(90, -90, array.shape[2]),
        'longitude': np.linspace(0, 360, array.shape[3], endpoint=False),
        'level': pressure_levels
    })
    
    idx = 0
    for variable in variables:
        is_pressure = 'level' in sample_ds[variable].dims
        indices = len(pressure_levels) if is_pressure else 1
        if not is_pressure:
            data = array[:, idx, :, :]
            ds[variable] = (('time', 'latitude', 'longitude'), data)
        else:
            data = array[:, idx:idx+indices, :, :]
            ds[variable] = (('time', 'level', 'latitude', 'longitude'), data)
        idx += indices
    
    return ds

if __name__ == '__main__':
    pass