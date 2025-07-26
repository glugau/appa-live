from appa.data.datasets import LatentBlanketDataset
from appa.save import safe_load
from pathlib import Path
import torch
import h5py

class CustomLatentBlanketDataset(LatentBlanketDataset):
    r"""Dataset for latent blankets.
    This serves as a wrapper around latent encoded data in h5 format. Modified
    from the original LatentBlanketDataset found in the APPA source code to
    add required modularity.
    Arguments:
        path: Path to the h5 dataset file.
        latents_folder: Path to the model's "latents" folder, containing the `stats.pth` file.
        start_date: Start date of the data split (format: 'YYYY-MM-DD').
        end_date: End date of the data split (format: 'YYYY-MM-DD').
        blanket_size: Size of the blankets.
        start_hour: Start hour of the data split (0-23).
        end_hour: End hour of the data split (0-23).
        standardize: Whether to standardize the data or not.
        stride: Spacing between blanket elements.
        noise_level: Level of noise to add to the data (before standardization).
    """
    def __init__(
        self,
        path: Path,
        latent_stats_path: Path,
        start_date: str,
        end_date: str,
        blanket_size: int,
        start_hour: int = 0,
        end_hour: int = 0,
        standardize: bool = True,
        stride: int = 1,
        noise_level: float = 0.0,
    ):
        self.h5_file = h5py.File(path, "r")
        self.latents = self.h5_file["latents"]
        self.dates = torch.as_tensor(self.h5_file["dates"][...])

        self.blanket_size = blanket_size
        self.standardize = standardize
        self.stride = stride
        self.noise_level = noise_level

        start_date = [int(x) for x in start_date.split("-")] + [start_hour]
        end_date = [int(x) for x in end_date.split("-")] + [end_hour]
        start_date, end_date = torch.as_tensor(start_date), torch.as_tensor(end_date)
        try:
            self.start_idx = (self.dates == start_date).all(dim=-1).nonzero().item()
            self.end_idx = (self.dates == end_date).all(dim=-1).nonzero().item() + 1
        except RuntimeError as e:
            raise ValueError("Start or end date not found in the dataset.") from e

        if standardize:
            if latent_stats_path.exists():
                stats = safe_load(latent_stats_path)
                self.mean = stats["mean"]
                self.std = stats["std"]

                if self.noise_level > 0:
                    self.std = torch.sqrt(torch.as_tensor(self.noise_level) ** 2 + self.std**2)
            else:
                raise ValueError("Statistics are not computed.")