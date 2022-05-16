import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import reduce
import json
from pathlib import Path
import tkinter as tk
from typing import Dict, List, Tuple, Union
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent, EVENT_TYPE_MODIFIED

from queue import Queue
import sys
import subprocess
from fastclasses_json import dataclass_json, JSONMixin


def texcount(file) -> int:
    res = subprocess.check_output(['texcount', '-brief', file]).decode('utf-8')
    return int(res.split('+')[0])


@dataclass_json
@dataclass
class RawWatchFile:
    filename: str
    display: str

    def to_watch_file(self) -> "WatchFile":
        return WatchFile(Path(self.filename), self.display)


@dataclass
class WatchFile:
    path: Path
    display: str


@dataclass_json
@dataclass
class RawConfigs(JSONMixin):
    files: List["RawWatchFile"]
    ddl: str
    show_total: bool = False
    time_format = '%Y-%m-%d %H:%M'

    def to_configs(self) -> "Configs":
        return Configs(
            [f.to_watch_file() for f in self.files],
            datetime.strptime(self.ddl, self.time_format),
            self.show_total
        )

    @classmethod
    def from_json(cls, json_data: Union[str, bytes], *, infer_missing=True) -> "RawConfigs":
        pass


@dataclass
class Configs:
    files: List["WatchFile"]
    ddl: datetime
    show_total: bool = False


def create_label(
    master: tk.Widget,
    display: str,
    count: int,
    stringvar: tk.StringVar,
    font,
):
    stringvar.set(str(count))
    frame = tk.Frame(master)
    frame.pack(fill=tk.X)
    tk.Label(frame, text=f"{display}:", font=font).pack(
        side=tk.LEFT, padx=(10, 30), pady=5)
    tk.Label(frame, textvariable=stringvar, font=font).pack(
        side=tk.RIGHT, padx=(30, 10), pady=5)


class App(object):
    WATCHDOG_EVENT = "<<WatchdogEvent>>"
    TOTAL = "Total"
    TITLE = "Counter"
    FONT = ('Cascadia Code', '16')

    @dataclass
    class CountStringVar:
        count: int
        stringvar: tk.StringVar

    _configs: Configs
    _observers: List[Observer]
    _event_queue: Queue[FileSystemEvent]
    _root: tk.Tk
    _file_to_display: Dict[Path, CountStringVar]
    _total: CountStringVar
    _remain_time: tk.StringVar

    def __init__(self, configs: Configs):
        self._configs = configs
        self._observers = []
        self._event_queue = Queue()
        self._root = tk.Tk()
        self._file_to_display = {}

        self._init_root()
        self._init_view()
        self._init_observer()
        self._init_loop()

    def _init_root(self):
        self._root.bind("<Destroy>", self._stop)
        self._root.bind('<Control-c>', self._quit)
        self._root.attributes('-topmost', True)

    def _init_view(self):
        self._root.title(App.TITLE)
        for file in self._configs.files:
            text = tk.StringVar()
            count = texcount(file.path)
            self._file_to_display[file.path] = App.CountStringVar(count, text)
            create_label(self._root, file.display, count, text, App.FONT)
        self._total = App.CountStringVar(self._get_total(), tk.StringVar())
        create_label(self._root, App.TOTAL,
                     self._total.count, self._total.stringvar, App.FONT)
        self._remain_time = tk.StringVar()
        tk.Label(self._root, textvariable=self._remain_time,
                 font=App.FONT).pack(fill=tk.X, anchor="center")

    def _init_observer(self):
        for folder in set([f.path.parent for f in self._configs.files]):
            handler = CustomHandler(self)
            observer = Observer()
            observer.schedule(handler, folder, recursive=True)
            self._observers.append(observer)
        self._root.bind(App.WATCHDOG_EVENT, self._handle_watchdog_event)
        for observer in self._observers:
            observer.start()

    def _init_loop(self):
        def refresh_remain():
            remaining_time = remain_time(self._configs.ddl)
            self._remain_time.set(remaining_time)
            self._root.after(1000, refresh_remain)
        refresh_remain()

    def _update_total(self):
        new_total = self._get_total()
        self._total.count = new_total
        self._total.stringvar.set(str(new_total))

    def _get_total(self) -> int:
        return sum([x.count for x in self._file_to_display.values()])

    def _handle_watchdog_event(self, event):
        """Called when watchdog posts an event"""
        watchdog_event = self._event_queue.get()
        if watchdog_event.event_type == EVENT_TYPE_MODIFIED:
            event_path = Path(watchdog_event.src_path)
            if event_path in self._file_to_display.keys():
                count = texcount(event_path)
                display_param = self._file_to_display[event_path]
                display_param.count = count
                display_param.stringvar.set(str(count))
                self._update_total()

    def notify(self, event: FileSystemEvent):
        """Forward events from watchdog to GUI"""
        self._event_queue.put(event)
        self._root.event_generate(App.WATCHDOG_EVENT, when="tail")

    def start(self):
        """Start the GUI loop"""
        self._root.mainloop()

    def quit(self):
        self._quit(None)

    def _quit(self, event):
        self._root.quit()
        self.stop()

    def stop(self):
        """Perform safe shutdown when GUI has been destroyed"""
        self._stop(None)

    def _stop(self, event):
        for observer in self._observers:
            observer.stop()
            observer.join()


class CustomHandler(FileSystemEventHandler):
    def __init__(self, app: App):
        FileSystemEventHandler.__init__(self)
        self._app = app

    def on_modified(self, event: FileSystemEvent):
        self._app.notify(event)


def read_config(filename: str) -> Configs:
    """Read config file"""
    return RawConfigs.from_json(open(filename, 'r').read()).to_configs()


def remain_time(ddl: datetime) -> str:
    """Format timedelta to string"""
    now = datetime.now()
    td = ddl - now
    mm, ss = divmod(td.seconds, 60)
    hh, mm = divmod(mm, 60)
    res = "剩余"
    if td.days > 0:
        return res + f"{td.days}天{hh:02d}时{mm:02d}分{ss:02d}秒"
    elif hh > 0:
        return res + f"{hh:02d}时{mm:02d}分{ss:02d}秒"
    elif mm > 0:
        return res + f"{mm:02d}分{ss:02d}秒"
    elif ss > 0:
        return res + f"{ss:02d}秒"
    else:
        return "寄"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Count words in LaTeX files")
    parser.add_argument("config", help="config file")
    args = parser.parse_args()
    app = App(read_config(args.config))
    app.start()
