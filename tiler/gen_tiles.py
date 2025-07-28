from rasterio.transform import from_origin
from os import PathLike
from pathlib import Path
from tiler import to_cmap

import tempfile
import numpy as np
import os
import subprocess
import rasterio
import shutil

def gen_tiles(data: np.ndarray,
              latitudes: np.ndarray,
              longitudes: np.ndarray,
              output_dir: PathLike,
              zoom_min: int = 0,
              zoom_max: int = 3,
              cmap: str = 'viridis',
              temp_dir: PathLike = './tmp',
              pmtiles: bool = False):
    """Generate, from 2D grid data, tiles that can be served with Leaflet.
    **This function expects longitude to range from 0 included to 360 excluded**.

    Args:
        data (np.ndarray): 2D (lat, lon) data array
        latitudes (np.ndarray): 1D (lon) latitudes array
        longitudes (np.ndarray): 1D (lat) longitudes array.
        output_dir (PathLike): Output directory of the tiles
        zoom_min (int, optional): Minimum zoom. Defaults to 0.
        zoom_max (int, optional): Maximum zoom. Defaults to 3.
        cmap (str, optional): Colormap available in `matplotlib.cm`. Defaults to 'viridis'.
        temp_dir (PathLike, optional): Temporary directory that will store at most
            a few megabytes. Defaults to './tmp'.
        pmtiles (bool, optional): Whether to save the tiles in pmtiles format. This
            requires mb-util and pmtiles to be installed. The saved output will be
            in the file `output_dir.pmtiles`. Defaults to False.
    """
    data = np.hstack([data, data[:, :1]])
    longitudes = np.append(longitudes, longitudes[-1] + longitudes[-1] - longitudes[-2])

    if np.max(longitudes) > 190:
        data = np.roll(data, shift=-data.shape[1] // 2, axis=1)
        longitudes -= 180
        
    color_data = to_cmap.array_to_rgb_u8(data, cmap)

    lon_min, lon_max = np.min(longitudes), np.max(longitudes)
    lat_min, lat_max = np.min(latitudes), np.max(latitudes)

    # Calculate pixel size
    pixel_width = (lon_max - lon_min) / data.shape[1]
    pixel_height = (lat_max - lat_min) / data.shape[0]

    # GeoTransform: top-left corner origin
    transform = from_origin(lon_min, lat_max, pixel_width, pixel_height)

    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    with tempfile.TemporaryDirectory(dir=temp_dir) as thread_temp_dir:
        tif_path = os.path.join(thread_temp_dir, 'colormap.tif')

        # Save colormap as tif
        with rasterio.open(
            tif_path,
            "w",
            driver="GTiff",
            height=data.shape[0],
            width=data.shape[1],
            count=color_data.shape[0],  # number of bands
            dtype=color_data.dtype,
            crs="EPSG:4326",  # WGS84
            transform=transform,
        ) as dst:
            dst.write(color_data)

        # Generate tiles directly from the RGB image
        output_dir = Path(output_dir)
        subprocess.run([
            'gdal2tiles.py', 
            '-z', f'{zoom_min}-{zoom_max}',  # zoom levels
            '-r', 'near',
            '--webviewer=none',
            tif_path, 
            output_dir.as_posix()
        ], stdout=subprocess.PIPE)
        
        if pmtiles:
            mbtiles_path = output_dir.with_name(output_dir.name + '.mbtiles')
            pmtiles_path = output_dir.with_name(output_dir.name + '.pmtiles')
            
            subprocess.run([
                'mb-util', 
                '--image_format=png',
                str(output_dir),
                str(mbtiles_path)
            ], stdout=subprocess.PIPE)
            
            subprocess.run([
                'pmtiles',
                'convert', 
                str(mbtiles_path),
                str(pmtiles_path)
            ], stdout=subprocess.PIPE)
            
            os.remove(mbtiles_path)
            shutil.rmtree(output_dir)