from datetime import datetime, timezone, timedelta
from omegaconf import OmegaConf, open_dict
from pathlib import Path
from typing import Sequence

import forecast_ar
import argparse
import logging
import re
import os

from appa.config.hydra import compose
from appa.config.hydra import compose
from appa.save import safe_load
from appa.nn.triggers import skip_init
from appa.nn.autoencoder import AutoEncoder

from latents import compute_and_save_latents
from decode_trajectory import decode_to_zarr

import constants

def main() -> None:
    parser = argparse.ArgumentParser(
        description=('Runs a (autoregressive) weather forecast using the APPA model'
                    ' and the latest available weather data in the provided directory.')
    )
    parser.add_argument('-c',
                        '--config-path',
                        help='Path to the configuration .yaml file',
                        required=True)
    parser.add_argument('-f',
                        '--force',
                        action='store_true',
                        help='If set, skip the processing step.')
    logging.basicConfig(level=logging.INFO)
    args = parser.parse_args()
    logger = logging.getLogger(__name__)
    config = compose(args.config_path)
    
    # Prepare directories
    path_output_dir = Path(config.output_dir_path)
    path_output_dir.mkdir(parents=True, exist_ok=True)
    
    path_temp_dir = Path(config.temp_dir_path)
    path_temp_dir.mkdir(parents=True, exist_ok=True)
    
    path_temp_latent_dir = path_temp_dir / 'latent_data'
    path_temp_latent_dir.mkdir(parents=True, exist_ok=True)
    
    path_temp_forecast_dir = path_temp_dir / 'latent_forecast'
    path_temp_forecast_dir.mkdir(parents=True, exist_ok=True)
    
    # Get latest available data
    path_latest = latest_data_file(config.weather_data_dir_path)
    dt_latest = file_to_datetime(path_latest)
    
    out_filename = f"{dt_latest.strftime('%Y-%m-%dT%HZ')}_PT{config.lead_time}H.zarr"
    path_output = path_output_dir / out_filename
    
    if path_output.exists() and not args.force:
        logger.info(f'A file named {out_filename} already exists. Stopping forecast.')
        logger.info('To force the forecast even if it already exists, run with -f.')
        return
    
    # Load autoencoder
    logger.info('Loading autoencoder. This may take a while.')
    ae_cfg = compose(Path(config.autoencoder_model_path) / 'config.yaml')
    ae_ckpt = safe_load(Path(config.autoencoder_model_path) / 'model_best.pth', map_location="cuda")
    with skip_init():
        autoencoder = AutoEncoder(**ae_cfg.ae)
    autoencoder.cuda()
    autoencoder.load_state_dict(ae_ckpt)
    del ae_ckpt
    autoencoder.eval()
    autoencoder.requires_grad_(False)
    
    logger.info('Saving weather data to latent form')
    latents_path = to_latents(path_latest,
                              dt_latest,
                              path_temp_latent_dir,
                              autoencoder,
                              config.weather_data_stats_path,
                              constants.VARIABLES,
                              constants.CONTEXT_VARIABLES,
                              constants.PRESSURE_LEVELS)
        
    logger.info('Starting forecast')
    forecast(
        latent_data_path=latents_path,
        dt_data=dt_latest,
        config_path=args.config_path,
        target_dir=path_temp_forecast_dir,
        autoencoder=autoencoder
    )
    
    logger.info('Decoding the forecast into .zarr format')
    decode_to_zarr(
        path_ae=config.autoencoder_model_path,
        path_trajectory=path_temp_forecast_dir / 'trajectory.pt',
        path_timestamps=path_temp_forecast_dir / 'timestamps.pt',
        path_latent_stats=config.latent_data_stats_path,
        path_data_stats=config.weather_data_stats_path,
        path_destination=path_output,
        variables=constants.VARIABLES,
        ctx_variables=constants.CONTEXT_VARIABLES,
        pressure_levels=constants.PRESSURE_LEVELS,
        autoencoder=autoencoder
    )
    logger.info(f'Data saved into {path_output}')
    
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

if __name__ == '__main__':
    main()