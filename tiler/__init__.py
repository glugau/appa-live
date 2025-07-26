from . import gen_tiles
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
                     temp_dir: PathLike = './tmp'):
    """_summary_

    Args:
        dataset (xr.Dataset): _description_
        output_dir (PathLike): _description_
        zoom_min (int, optional): _description_. Defaults to 0.
        zoom_max (int, optional): _description_. Defaults to 3.
        cmap_mappings (dict[str, str], optional): _description_. Defaults to {}.
        cmap_default (str, optional): _description_. Defaults to 'viridis'.
        temp_dir (PathLike, optional): _description_. Defaults to './tmp'.
    """
    logger = logging.getLogger(__name__)
    
    output_dir = Path(output_dir)
    
    lats = dataset['latitude'].to_numpy()  # [90, 89.75, ..., -89.75, -90]
    lons = dataset['longitude'].to_numpy()  # [0, 0.25, ..., 359.5, 359.75]
    
    def process_slice(variable: str, itime: int, ilevel: int, variable_output_dir: Path, cmap: str):
        
        if itime == 0 and (ilevel is None or ilevel <= 0):
            variations *= len(dataset['time'].to_numpy())
            if ilevel is not None and ilevel >= 0:
                variations *= len(dataset['level'].to_numpy())
            logger.info(f'Generating tiles for {variations} slices (time x levels) of {variable}')
        
        if ilevel is None or ilevel < 0:
            data = dataset[variable][itime].to_numpy()
        else:
            data = dataset[variable][itime][ilevel].to_numpy()
        gen_tiles.gen_tiles(
            data,
            lats,
            lons,
            variable_output_dir,
            zoom_min,
            zoom_max,
            cmap,
            temp_dir
        )
    
    n_threads = min(32, os.cpu_count() + 4)
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
                    
