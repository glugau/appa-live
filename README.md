# APPA live

## Installing the dependencies

Navigate to your preferred virtual environment, then run

```bash
pip install git+ssh://git@github.com/montefiore-sail/appa.git@v1.0 --no-deps
pip install -r requirements.txt
```

The first line is required because APPA wants older package versions for some things, notably `xarray`.

For generating png tiles, you must also run

```bash
sudo apt-get update && sudo apt install gdal-bin
```

Or equivalent if your package manager is not `apt`. The important requirement here is `gdal2tiles.py`.