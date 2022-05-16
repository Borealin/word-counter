# Tex Files Text Realtime Counter
## Intro
A simple tkinter program for displaying tex file count and ddl
## Usage
### Prerequisite
Make sure you already install Tex environment and have [TeXcount](https://app.uio.no/ifi/texcount/) package install in your path
### Install deps
```shell
poetry install
```
### Configure Config File
configure config json file as following, multiple files is possible and will be displayed in the order of `configs.files`
```json
{
    "files": [
        {
            "filename": "path_to_tex",
            "display": "display_name"
        },
    ],
    "ddl": "2022-05-23 23:00",
    "time_format": "%Y-%m-%d %H:%M",
    "show_total": false
}
```
### Run Counter
```shell
python counter.py CONFIG_FILE
```
