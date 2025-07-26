import os
from dotenv import load_dotenv
import argparse
import importlib
import logging
import processing
from custom_data.solar_radiation import xarray_integrated_toa_solar_radiation
import shutil

load_dotenv() # development (API keys)

AVAILABLE_SOURCES = ['era5', 'ifs']

parser = argparse.ArgumentParser()
parser.add_argument('-t', '--target-folder',
                    required=False, default='./data',
                    dest='target_folder',
                    help=('Destination output folder of the NetCDF4 files.The'
                          'files will be in a subfolder bearing the name of '
                          'the data source.'))
parser.add_argument('--skip-processing', action='store_true',
                    help='If set, skip the processing step.')
parser.add_argument('--skip-download', action='store_true',
                    help=('If set, skip the download step and use cached files.'
                          ' If none are available, there will be an exception.'))
parser.add_argument('-c', '--cleanup', action='store_true',
                    help=('If set, delete all files only relevant to a single '
                          'dataset, keeping only processed files. Using this '
                          'along with --skip-download will download the files '
                          'then immediately delete them.'))

args = parser.parse_args()

# Disable the internal logger of ECMWF, which causes duplicate logs.
logger = logging.getLogger(__name__)
logging.getLogger('ecmwf.datastores.legacy_client').propagate = False
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    force=True
)

SOURCES = ['ifs', 'era5']
RAW_SUFFIX = '_raw' # for the naming of the folders containing unprocessed data

ifs_datetime = None

if not args.skip_download:
    for source in SOURCES:
        target = os.path.join(args.target_folder, f'{source}{RAW_SUFFIX}')
        logger.info(f'Fetching the latest data from {source} into the folder {target}')
        if not os.path.exists(target):
            os.makedirs(target)
        data_source = importlib.import_module(f'data_sources.{source}')
        datetime = data_source.download_latest(target)
        logger.info(f'Successfuly downloaded data from timestamp {datetime}')
        if source == 'ifs':
            ifs_datetime = datetime
    logger.info('All files downloaded')

if ifs_datetime is None:
    logger.info('Skipping download...')
    ifs_datetime = processing.latest_datetime(
        os.path.join(args.target_folder, f'ifs{RAW_SUFFIX}')
    )
    
logger.info('Computing TOA radiation')
toa_radiation = xarray_integrated_toa_solar_radiation(ifs_datetime, 1)

if not args.skip_processing:
    logger.info('Processing the data')
    processing.process_data(
        os.path.join(args.target_folder, f'era5{RAW_SUFFIX}'),
        os.path.join(args.target_folder, f'ifs{RAW_SUFFIX}'),
        toa_radiation,
        os.path.join(args.target_folder, 'processed')
    )
else:
    logger.info('Skipping the processing step')
    
if args.cleanup:
    logger.info('Removing raw data folders')
    for source in SOURCES:
        shutil.rmtree(os.path.join(args.target_folder, f'{source}{RAW_SUFFIX}'))
        
if not args.skip_processing:
    logger.info(f'Done! Processed data is available in {os.path.join(args.target_folder, 'processed')}')
if not args.cleanup:
    logger.info(('Raw download files are available in folders with the '
                 f'"{RAW_SUFFIX}" suffix, in {args.target_folder}'))