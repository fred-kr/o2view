import os
import sys
import time
from multiprocessing import Condition, Process

import setproctitle
import webview

from o2view.domino import terminate_when_process_dies
from o2view.server import start_dash


def start() -> None:
    port = os.getenv("O2VIEW_PORT", "8050")
    host = os.getenv("O2VIEW_HOST", "127.0.0.1")

    server_is_started = Condition()
    setproctitle.setproctitle("o2view")

    p = Process(target=start_dash, args=(host, port, server_is_started))
    p.start()

    terminate_when_process_dies(p)

    with server_is_started:
        server_is_started.wait()

    time.sleep(0.2)

    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.create_window(
        "O2View",
        f"http://{host}:{port}",
        width=1600,
        height=1000,
    )
    webview.start()

    # Reached only when the window is closed
    p.terminate()
    sys.exit(0)


if __name__ == "__main__":
    start()
