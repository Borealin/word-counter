from dataclasses import dataclass
from functools import reduce
import json
from pathlib import Path
import tkinter as tk
from typing import Dict, List, Tuple
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent, EVENT_TYPE_MODIFIED

from queue import Queue
import sys
import subprocess
import time


def texcount(file) -> int:
    res = subprocess.check_output(['texcount', '-brief', file]).decode('utf-8')
    return int(res.split('+')[0])

@dataclass
class Config:
    filename: str
    display: str


def create_label(
    master: tk.Widget,
    display: str,
    count: int,
    stringvar: tk.StringVar,
    font=('Cascadia Code', '16'),
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

    def __init__(self, configs: List[Config]):
        path_configs = [(Path(config.filename), config.display)
                        for config in configs]
        folders = set()
        for file, _ in path_configs:
            folder = file.parent
            folders.add(folder)

        self._observers: List[Observer] = []
        for folder in folders:
            handler = CustomHandler(self)
            observer = Observer()
            observer.schedule(handler, folder, recursive=True)
            self._observers.append(observer)

        self._queue = Queue[FileSystemEvent]()
        self._root = tk.Tk()
        self._root.title(App.TITLE)

        self._file_to_display: Dict[Path, Tuple[int, tk.StringVar]] = {}
        for file, display in path_configs:
            text = tk.StringVar()
            count = texcount(file)
            self._file_to_display[file] = (count, text)
            create_label(self._root, display, count, text)
        self._total = (self.get_total(), tk.StringVar())
        create_label(self._root, App.TOTAL, self._total[0], self._total[1])

        self._root.bind("<Destroy>", self._stop)
        self._root.bind(App.WATCHDOG_EVENT, self.handle_watchdog_event)
        self._root.bind('<Control-c>', self._quit)
        self._root.attributes('-topmost', True)
        for observer in self._observers:
            observer.start()

    def handle_watchdog_event(self, event):
        """Called when watchdog posts an event"""
        watchdog_event = self._queue.get()
        if watchdog_event.event_type == EVENT_TYPE_MODIFIED:
            event_path = Path(watchdog_event.src_path)
            if event_path in self._file_to_display.keys():
                count = texcount(event_path)
                display_param = self._file_to_display[event_path]
                display_param[1].set(str(count))
                self._file_to_display[event_path] = (count, display_param[1])
                self.update_total()

    def update_total(self):
        stringvar = self._total[1]
        new_total = self.get_total()
        stringvar.set(str(new_total))
        self._total = (new_total, stringvar)

    def get_total(self) -> int:
        return sum([x[0] for x in self._file_to_display.values()])

    def notify(self, event: FileSystemEvent):
        """Forward events from watchdog to GUI"""
        self._queue.put(event)
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


def read_config(filename: str) -> List[Config]:
    """Read config file"""
    return [Config(x['filename'], x['display']) for x in json.load(open(filename, 'r'))]


app = App(read_config(sys.argv[1]))

try:
    app.start()
except KeyboardInterrupt:
    app.quit()
