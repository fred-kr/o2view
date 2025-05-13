import os
import sys

if not sys.warnoptions:
    import warnings

    warnings.simplefilter("ignore")
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

    # Ensure the process doesn't show warnings
    p = Process(target=start_dash, args=(host, port, server_is_started))
    p.start()

    terminate_when_process_dies(p)

    with server_is_started:
        server_is_started.wait()

    time.sleep(0.2)

    webview.settings["ALLOW_DOWNLOADS"] = True
    display: webview.Screen = webview.screens[0]
    dw = display.width
    dh = display.height
    min_size = (min(dw, 800), min(dh, 600))
    maximize = False
    if min_size == (dw, dh):
        maximize = True

    webview.create_window(
        "O2View",
        f"http://{host}:{port}",
        width=min(1600, dw),
        height=min(1000, dh),
        min_size=min_size,
        maximized=maximize,
    )
    webview.start()

    # Reached only when the window is closed
    p.terminate()
    sys.exit(0)


if __name__ == "__main__":
    start()
