# Server

This utility is a python simple http server, modified to allow CORS requests from any domain.

## Usage

```
python -m server [-d DIRECTORY] [--bind ADDRESS] [port]
```

With the default directory being the current working directory the default port being `8000`, and the default bind address being `0.0.0.0` (all interfaces).