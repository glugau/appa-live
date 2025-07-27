from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Sequence

from forecast import forecast_ar
from forecast import constants
from forecast import latents
from forecast import decode_trajectory
from forecast import custom_datasets

from forecast.latents import compute_and_save_latents

from appa.config.hydra import compose
from appa.nn.autoencoder import AutoEncoder

import re
import os

def file_to_datetime(file_path: os.PathLike) -> datetime:
    """Obtain the datetime contained in the name of a file, expecting it to be
    in the YYYY-mm-ddTHH:MM:SSZ format.

    Args:
        file_path (os.PathLike): Path to the desired file

    Returns:
        datetime: Datetime object corresponding to the date/time in the file name
    """
    filename = os.path.basename(str(file_path))
    timestamp_str = filename.split(".")[0].rstrip("Z")
    dt = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return dt

def latest_data_file(dir_path: os.PathLike) -> str:
    """Finds the latest available weather data file in the `dir_path` directory.
    This will also look in the `processed/` subdirectory of `dir_path` if no
    file was found in the provided `dir_path`.

    Args:
        dir_path (os.PathLike): Directory in which to look

    Returns:
        str: Path to the latest file, as a string
    """
    pattern = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\.zarr$')

    def find_files(path):
        return [os.path.join(path, f) for f in os.listdir(path) if pattern.match(f)]

    files = find_files(dir_path)

    if not files:
        processed_path = os.path.join(dir_path, "processed")
        if os.path.exists(processed_path) and os.path.isdir(processed_path):
            files = find_files(processed_path)

    return max(files)

def to_latents(
    path_latest: os.PathLike,
    dt_latest: datetime,
    latents_dir: os.PathLike,
    autoencoder: AutoEncoder,
    path_data_statistics: os.PathLike,
    variables: Sequence[str],
    ctx_variables: Sequence[str],
    pressure_levels: Sequence[int]
) -> Path:
    """Save the latest available .zarr weather data file into a latent .h5
    representation.

    Args:
        path_latest (os.PathLike): Path to the latest .zarr weather data file
        dt_latest (datetime): Datetime corresponding to `path_latest`
        latents_dir (os.PathLike): Output folder in which to dump the latent
            representations
        autoencoder (AutoEncoder): Loaded AutoEncoder
        path_data_statistics (os.PathLike): Path to the data .zarr statistics file
        variables (Sequence[str]): Ordered list of variables used in the dataset
        ctx_variables (Sequence[str]): Ordered list of context variables used
        pressure_levels (Sequence[int]): Ordered list of pressure levels used
    Returns:
        Path: Path to the dumped latent representations
    """
    autoencoder.eval()
    autoencoder.requires_grad_(False)

    date_str = dt_latest.strftime("%Y-%m-%d")
    
    output_path = Path(latents_dir) / dt_latest.strftime("%Y-%m-%dT%H:%M:%SZ.h5")

    compute_and_save_latents(
        autoencoder=autoencoder,
        path_data=Path(path_latest),
        path_output=output_path,
        batch_size=1,
        start_date=date_str,
        end_date=date_str,
        path_data_statistics=path_data_statistics,
        variables=variables,
        ctx_variables=ctx_variables,
        pressure_levels=pressure_levels
    )
    
    return output_path

def forecast(
    latent_data_path: os.PathLike,
    dt_data: datetime,
    config_path: os.PathLike,
    target_dir: os.PathLike,
    autoencoder: AutoEncoder
) -> None :
    """Run a forecast, given the latest observation provided in the 
    `latent_data_path` file.

    Args:
        latent_data_path (os.PathLike): Path to the latent data on which to
            condition the forecast
        dt_data (datetime): Datetime of the latent data provided
        config_path (os.PathLike): Configuration file for the forecast
        target_dir (os.PathLike): Target directory for the output trajectory
        autoencoder (AutoEncoder): Loaded AutoEncoder
    """
    autoencoder.eval()
    autoencoder.requires_grad_(False)
    
    latent_data_path = Path(latent_data_path)
    config_path = Path(config_path)
    
    config = compose(config_path)
    denoiser_cfg = compose(Path(config.denoiser_model_path) / "config.yaml")
    
    # The '1' used to be config.assimilation_length but was hardcoded to 1 because
    # this code only supports a single timestep of one hour as initial conditions
    delta_start = timedelta(hours=1 * denoiser_cfg.train.blanket_dt)
    dt_start = dt_data + delta_start
    
    forecast_ar.forecast_ar(
        denoiser_model_path=config.denoiser_model_path,
        autoencoder_model_path=config.autoencoder_model_path,
        latent_data_path=latent_data_path,
        latents_stats_path=config.latent_data_stats_path,
        model_target='best',
        diffusion=config.diffusion,
        assimilation_length=1,
        lead_time=config.lead_time,
        preds_per_step=config.preds_per_step,
        past_window_size=config.past_window_size,
        start_date=dt_start.strftime('%Y-%m-%d'),
        start_hour=dt_start.hour,
        precision=config.precision,
        target_dir=target_dir,
        autoencoder=autoencoder,
    )