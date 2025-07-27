from pathlib import Path

from forecast import file_to_datetime, latest_data_file, to_latents, forecast
from forecast import constants
from forecast.decode_trajectory import decode_to_zarr

from appa.config.hydra import compose
from appa.save import safe_load
from appa.nn.triggers import skip_init
from appa.nn.autoencoder import AutoEncoder

import argparse
import logging
import tempfile


def main() -> None:
    parser = argparse.ArgumentParser(
        description=('Runs a (autoregressive) weather forecast using the APPA model'
                    ' and the latest available weather data in the provided directory.')
    )
    parser.add_argument('-c',
                        '--config-path',
                        help='Path to the configuration .yaml file',
                        required=True)
    parser.add_argument('-d',
                        '--weather-data-dir',
                        help='Directory containing the weather data to use',
                        required=True)
    parser.add_argument('-o',
                        '--output-dir',
                        help='Output directory',
                        required=True)
    parser.add_argument('--temp-dir',
                        help='Temporary directory root',
                        required=False,
                        default=tempfile.gettempdir())
    parser.add_argument('-f',
                        '--force',
                        action='store_true',
                        help='Force the forecast even if one with the same name already exists.')
    logging.basicConfig(level=logging.INFO)
    args = parser.parse_args()
    logger = logging.getLogger(__name__)
    config = compose(args.config_path)
    
    # Prepare directories
    path_output_dir = Path(args.output_dir)
    path_output_dir.mkdir(parents=True, exist_ok=True)
    
    with tempfile.TemporaryDirectory(dir=args.temp_dir) as path_temp_dir:
        path_temp_dir = Path(path_temp_dir)
        path_temp_latent_dir = path_temp_dir / 'latent_data'
        path_temp_latent_dir.mkdir(parents=True, exist_ok=True)
        
        path_temp_forecast_dir = path_temp_dir / 'latent_forecast'
        path_temp_forecast_dir.mkdir(parents=True, exist_ok=True)
        
        # Get latest available data
        path_latest = latest_data_file(args.weather_data_dir)
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

if __name__ == '__main__':
    main()