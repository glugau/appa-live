# appa-public-inference
This service utilises available data (downloaded by [appa-fetcher](https://github.com/glugau/appa-fetcher)) to then perform inference with the APPA model, and store the results.

## Usage
First, make sure that the APPA source code was properly cloned when cloning this repository. If you have not cloned yet, clone with the `--recurse-submodules` flag.

```
git clone --recurse-submodules 
```

Then, install the required dependencies in your preferred virtual environment

```
pip install --no-deps ./external/appa
pip install -r requirements.txt
```

Copy the [example_config.yaml](example_config.yaml) configuration file and modify it to suit your needs. Modify the [constants.py](constants.py) to match the variables used by the model if required.

Finally, run the script with

```
python main.py [-h] [-f] -c CONFIG_PATH
```

# Arguments
- **-h, --help**: Display an help message
- **-f, --force**: Force the forecast, even if it has already been done.
- **-c, --config-path** _CONFIG_PATH_: Path to a configuration `.yaml` file. A working example is provided in [forecast_ar.yaml](config/forecast_ar.yaml).