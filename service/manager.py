import threading
import json
import logging
log = logging.getLogger(__name__)

from scanner.scanner import Scanner
from scanner.snapshot import SnapshotManager
from config.crypto import Crypto
from client.client import Client
from scanner.event import Event


class Manager:
    def __init__(self, path, url):
        self.path = path

        self.timer = None
        self.timer_lock = threading.Lock()

        self.debounce_seconds = 60 * 60
        self.scanner = Scanner(
            path=self.path,
            callback=self.on_file_changed,
            recursive=True
        )

        self.observer = self.scanner.registrate_observer()

        self.snapshot_manager = SnapshotManager(self.path)
        self.crypto = Crypto()

        self.url = url
        self.client = Client(self.url)

    def on_file_changed(self, event):
        with self.timer_lock:
            if self.timer is not None:
                self.timer.cancel()

            self.timer = threading.Timer(
                self.debounce_seconds,
                self.commit
            )

            self.timer.daemon = True
            self.timer.start()

            log.info(
                f"сommit scheduled %s",
                event.src_path
            )

    def commit(self):

        with self.timer_lock:
            self.timer = None

        current_json = self.snapshot_manager.serialize_snapshot()

        snapshot = json.loads(current_json)

        encrypt_json = self.crypto.encrypt(
            type_event=Event.OBSIDIAN.value,
            snapshot=snapshot
        )

        response_json = self.client.post(encrypt_json)

        if response_json['status'] == 'success':
            log.info("post commit succes")
        else:
            log.exception("post commit not completed!!")
        

    def start(self):
        self.observer.start()

    def stop(self):

        self.observer.stop()
        self.observer.join()

        with self.timer_lock:   
            if self.timer is not None:
                self.timer.cancel()
                self.timer = None