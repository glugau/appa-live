import xarray as xr
import subprocess
import importlib
import argparse
import tempfile
import logging
import dotenv
import boto3
import json
import os
import io

from pathlib import Path

from appa.nn.autoencoder import AutoEncoder
from appa.nn.triggers import skip_init
from appa.config.hydra import compose
from appa.save import safe_load

from fetcher import processing
from fetcher.custom_data.solar_radiation import xarray_integrated_toa_solar_radiation
from fetcher.data_sources import imerg_early

import forecast
import tiler

logger = logging.getLogger(__name__)
dotenv.load_dotenv()

def main():
    args = parse_args()
    # Disable the internal logger of ECMWF, which causes duplicate logs.
    logging.getLogger('ecmwf.datastores.legacy_client').propagate = False
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        force=True
    )
    
    with tempfile.TemporaryDirectory(dir=args.temp_dir) as temp_dir:
        try:
            #Make paths
            weather_data_dir = os.path.join(temp_dir, 'weather_data')
            Path(weather_data_dir).mkdir(parents=True, exist_ok=True)
            forecast_output_dir = os.path.join(temp_dir, 'forecast')
            Path(forecast_output_dir).mkdir(parents=True, exist_ok=True)
            tiles_output_dir = os.path.join(temp_dir, 'tiles')
            Path(tiles_output_dir).mkdir(parents=True, exist_ok=True)
            
            logger.info('Fetching weather data')
            fetch_data(weather_data_dir)
            
            logger.info('Starting the forecasting step')
            forecast_zarr_path = run_forecast(args.config_path,
                         forecast_output_dir,
                         weather_data_dir,
                         temp_dir)
            
            logger.info('Generating tiles')
            ds = xr.open_zarr(forecast_zarr_path)
            tiler.dataset_to_tiles(
                ds,
                output_dir=tiles_output_dir,
                zoom_min=tiler.constants.ZOOM_MIN,
                zoom_max=tiler.constants.ZOOM_MAX,
                cmap_mappings=tiler.constants.CMAP_MAPPINGS,
                cmap_default=tiler.constants.CMAP_DEFAULT,
                temp_dir=temp_dir,
                pmtiles=True,
                qmin=0.01,
                qmax=0.99
            )
            
            logger.info('Computing color-value mappings')
            colormaps = tiler.colormap.get_legends(
                ds,
                0.01,
                0.99,
                tiler.constants.CMAP_MAPPINGS,
                tiler.constants.CMAP_DEFAULT
            )
            
            logger.info('Uploading tiles')
            upload_data(tiles_output_dir, f'tiles/{forecast_zarr_path.stem}')
            
            metadata = {}
            metadata['latest'] = forecast_zarr_path.stem
            metadata['variables'] = {}
            metadata['colormaps'] = colormaps
            for variable in ds.data_vars:
                is_level = 'level' in ds[variable].dims
                units = ds[variable].attrs.get('units')
                long_name = ds[variable].attrs.get('long_name', variable)
                metadata['variables'][variable] = {
                    'is_level': is_level,
                    'units': units,
                    'long_name': long_name
                }
            # metadata['latitudes'] = list(ds['latitude'].to_numpy())
            # metadata['longitudes'] = list(ds['longitude'].to_numpy())
            metadata['levels'] = ds['level'].to_numpy().astype(int).tolist()
            writefile('metadata.json', json.dumps(metadata, indent=2))
                    
        except Exception:
            # This makes sure the temp dir is deleted in the end, even if there
            # is an exception.
            logger.exception('Fatal exception')
    
def parse_args() -> argparse.Namespace:
    """Parse command line arguments into a argparse.Namespace object. Individual
    arguments can then be retrieved by `args.argument_name`, where `args` is the
    return value of this function.

    Returns:
        argparse.Namespace: Launch arguments
    """
    parser = argparse.ArgumentParser(
        description=('Runs the full pipeline to generate a forecast using APPA.'
                    ' This means fetching data, forecasting, generating web tiles,'
                    ' and uploading those tiles (and the zarr file) to the cloud.')
    )
    parser.add_argument('-c',
                        '--config-path',
                        help='Path to a forecast configuration .yaml file',
                        required=True)
    parser.add_argument('--temp-dir',
                        default=tempfile.gettempdir(),
                        help=('Specify the root of the temporary directories that '
                              'will be used. This directory must exist before '
                              'running this code. Files generated inside '
                              'this directory will be deleted when finished.'))
    return parser.parse_args()

def fetch_data(target_dir: os.PathLike):
    """Fetch the latest weather data, storing raw files into a temporary directory
    so they are cleaned up after processing automatically.

    Args:
        target_dir (os.PathLike): Target directory for the processed/data.zarr
    """
    SOURCES = ['ifs', 'era5']
    RAW_SUFFIX = '_raw' # for the naming of the folders containing unprocessed data
    
    with tempfile.TemporaryDirectory(dir=target_dir) as target_raw_dir:

        ifs_datetime = None

        for source in SOURCES:
            target = os.path.join(target_raw_dir, f'{source}{RAW_SUFFIX}')
            logger.info(f'Fetching the latest data from {source} into {target}')
            if not os.path.exists(target):
                os.makedirs(target)
            data_source = importlib.import_module(f'fetcher.data_sources.{source}')
            datetime = data_source.download_latest(target)
            logger.info(f'Successfuly downloaded data from timestamp {datetime}')
            if source == 'ifs':
                ifs_datetime = datetime
        
        imerg_target = os.path.join(target_raw_dir, f'imerg{RAW_SUFFIX}')
        if not os.path.exists(imerg_target): os.makedirs(imerg_target)
        imerg_early.get_total_precipitation(ifs_datetime, imerg_target)
                
        logger.info('All files downloaded')
        logger.info('Computing TOA radiation')
        toa_radiation = xarray_integrated_toa_solar_radiation(ifs_datetime, 1)
        logger.info('Processing the data')
        processing.process_data(
            os.path.join(target_raw_dir, f'era5{RAW_SUFFIX}'),
            os.path.join(target_raw_dir, f'ifs{RAW_SUFFIX}'),
            imerg_target,
            toa_radiation,
            target_dir
        )

def run_forecast(config_path: os.PathLike,
                 output_dir: os.PathLike,
                 weather_data_dir: os.PathLike,
                 temp_dir: os.PathLike) -> Path:
    """Run a weather forecast based on the given config file and input weather
    data.

    Args:
        config_path (os.PathLike): Path to the config .yaml file
        output_dir (os.PathLike): Path to the output directory
        weather_data_dir (os.PathLike): Path to the input weather data directory
        temp_dir (os.PathLike): Path to the temporary directory
    Returns:
        Path: Path to the output .zarr file
    """
    
    config = compose(config_path)
    
    # Prepare directories
    path_output_dir = Path(output_dir)
    path_output_dir.mkdir(parents=True, exist_ok=True)
    
    with tempfile.TemporaryDirectory(dir=temp_dir) as path_temp_dir:
        path_temp_dir = Path(path_temp_dir)
        path_temp_latent_dir = path_temp_dir / 'latent_data'
        path_temp_latent_dir.mkdir(parents=True, exist_ok=True)
        
        path_temp_forecast_dir = path_temp_dir / 'latent_forecast'
        path_temp_forecast_dir.mkdir(parents=True, exist_ok=True)
        
        path_latest = forecast.latest_data_file(weather_data_dir)
        dt_latest = forecast.file_to_datetime(path_latest)
        
        out_filename = f"{dt_latest.strftime('%Y-%m-%dT%HZ')}_PT{config.lead_time}H.zarr"
        path_output = path_output_dir / out_filename
        
        if path_output.exists():
            logger.info(f'A file named {out_filename} already exists. Stopping forecast.')
            logger.info('Delete this file if you want to re-run a forecast.')
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
        latents_path = forecast.to_latents(path_latest,
                                dt_latest,
                                path_temp_latent_dir,
                                autoencoder,
                                config.weather_data_stats_path,
                                forecast.constants.VARIABLES,
                                forecast.constants.CONTEXT_VARIABLES,
                                forecast.constants.PRESSURE_LEVELS)
            
        logger.info('Starting forecast')
        forecast.forecast(
            latent_data_path=latents_path,
            dt_data=dt_latest,
            config_path=config_path,
            target_dir=path_temp_forecast_dir,
            autoencoder=autoencoder
        )
        
        logger.info('Decoding the forecast into .zarr format')
        forecast.decode_trajectory.decode_to_zarr(
            path_ae=config.autoencoder_model_path,
            path_trajectory=path_temp_forecast_dir / 'trajectory.pt',
            path_timestamps=path_temp_forecast_dir / 'timestamps.pt',
            path_latent_stats=config.latent_data_stats_path,
            path_data_stats=config.weather_data_stats_path,
            path_destination=path_output,
            variables=forecast.constants.VARIABLES,
            ctx_variables=forecast.constants.CONTEXT_VARIABLES,
            pressure_levels=forecast.constants.PRESSURE_LEVELS,
            autoencoder=autoencoder
        )
        logger.info(f'Data saved into {path_output}')
        return path_output

def upload_data(
    src_path: os.PathLike,
    dst_path: os.PathLike,
):
    """Upload a directory into an s3 bucket.

    Args:
        src_path (os.PathLike): Directory to upload
        dst_path (os.PathLike): Destination directory name, in the bucket
    """
    
    bucket_path = f's3://{os.environ['S3_BUCKET_NAME']}/{Path(dst_path).as_posix().lstrip('/')}'
    cmd = [
        'aws', 's3', 'sync',
        src_path,
        bucket_path,
        '--endpoint-url', os.environ['S3_ENDPOINT'],
        '--region', 'auto'
    ]

    env = {
        **subprocess.os.environ,
        "AWS_ACCESS_KEY_ID": os.environ['S3_ACCESS_KEY_ID'],
        "AWS_SECRET_ACCESS_KEY": os.environ['S3_SECRET_ACCESS_KEY']
    }

    subprocess.run(cmd, check=True, env=env)
                
def writefile(file_key: str, contents: str):
    s3 = boto3.client(
        service_name='s3',
        endpoint_url = os.environ['S3_ENDPOINT'],
        aws_access_key_id = os.environ['S3_ACCESS_KEY_ID'],
        aws_secret_access_key = os.environ['S3_SECRET_ACCESS_KEY'],
        region_name='auto'
    )
    
    s3.put_object(
        Bucket=os.environ['S3_BUCKET_NAME'],
        Key=file_key,
        Body=contents.encode('utf-8')
    )

if __name__ == '__main__':
    main()