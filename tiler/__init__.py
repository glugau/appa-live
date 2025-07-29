from . import gen_tiles, constants
from os import PathLike
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import xarray as xr
import numpy as np
import os

import logging

def dataset_to_tiles(dataset: xr.Dataset,
                     output_dir: PathLike,
                     zoom_min: int = 0,
                     zoom_max: int = 3,
                     cmap_mappings: dict[str, str] = {},
                     cmap_default: str = 'viridis',
                     temp_dir: PathLike = './tmp',
                     pmtiles: bool = False,
                     n_threads: int = None,
                     qmin=0.01,
                     qmax=0.99):
    """Generate all tiles for a given dataset, to be viewed in applications such
    as Leaflet.

    Args:
        dataset (xr.Dataset): Dataset for which to generate the tiles
        output_dir (PathLike): Output directory for the
        zoom_min (int, optional): Minimum zoom. Defaults to 0.
        zoom_max (int, optional): Maximum zoom. Defaults to 3.
        cmap_mappings (dict[str, str], optional): {'variable': 'colormap'} pairs
            that will override `cmap_default`. Defaults to {}.
        cmap_default (str, optional): Default colormap if none was provided in
            `cmap_mappings` for the given variable. Defaults to 'viridis'.
        temp_dir (PathLike, optional): Temporary directory used during tile
            generation. Defaults to './tmp'.
        n_threads (int, optional): Number of threads used for the generation of
            tiles. If `None` is provided, `min(32, os.cpu_count() + 4)` will be
            used. Defaults to `None`.
        qmin (float, optional): Minimum quantile to represent. Defaults to 0.01.
        qmax (float, optional): Maximum quantile to represent. Defaults to 0.99
    """
    logger = logging.getLogger(__name__)
    
    output_dir = Path(output_dir)
    
    lats = dataset['latitude'].to_numpy()  # [90, 89.75, ..., -89.75, -90]
    lons = dataset['longitude'].to_numpy()  # [0, 0.25, ..., 359.5, 359.75]
    
    def process_slice(variable: str, itime: int, ilevel: int, variable_output_dir: Path, cmap: str):
        
        if itime == 0 and (ilevel is None or ilevel <= 0):
            variations = len(dataset['time'].to_numpy())
            if ilevel is not None and ilevel >= 0:
                variations *= len(dataset['level'].to_numpy())
            logger.info(f'Generating tiles for {variations} slices (time x levels) of {variable}')
        
        if ilevel is None or ilevel < 0:
            data = dataset[variable][itime].to_numpy()
        else:
            data = dataset[variable][itime][ilevel].to_numpy()
            
        dims = set(dataset[variable].dims)
        reduce_dims = tuple(d for d in ('time', 'level', 'latitude', 'longitude') if d in dims)
        dqmin = dataset[variable].quantile(qmin, dim=reduce_dims)
        dqmax = dataset[variable].quantile(qmax, dim=reduce_dims)
            
        gen_tiles.gen_tiles(
            data,
            lats,
            lons,
            variable_output_dir,
            dqmin,
            dqmax,
            zoom_min,
            zoom_max,
            cmap,
            temp_dir,
            pmtiles
        )
    
    n_threads = min(32, os.cpu_count() + 4) if n_threads is None else n_threads
    with ThreadPoolExecutor(max_workers=n_threads) as executor:
        futures = []
        for variable in dataset.data_vars:
            cmap = cmap_mappings.get(variable, cmap_default)
            is_level = 'level' in dataset[variable].dims
            
            for itime in range(len(list(dataset['time'].to_numpy()))):
                if is_level:
                    for ilevel in range(len(list(dataset['level'].to_numpy()))):
                        path = output_dir / Path(variable) / Path(f'lvl{ilevel}') / Path(f'h{itime}') 
                        futures.append(
                            executor.submit(
                                process_slice,
                                variable,
                                itime,
                                ilevel,
                                path,
                                cmap
                            )
                        )
                else:
                    path = output_dir / Path(variable) / Path(f'h{itime}')
                    futures.append(
                        executor.submit(
                            process_slice,
                            variable,
                            itime,
                            -1,
                            path,
                            cmap
                        )
                    )

        for future in futures:
            future.result()