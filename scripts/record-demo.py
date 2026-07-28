#!/usr/bin/env python
"""Record docs/demo.gif from the running app.

Drives a real Chrome against a real server over the DevTools Protocol and
screenshots what it renders, so the demo shows the actual interface rather than
a mock-up of one. The conversation is invented; see make-demo-store.py.

    ./scripts/record-demo.sh
"""

from __future__ import annotations

import asyncio
import base64
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT / "data" / "demo-frames"
OUTPUT = ROOT / "docs" / "demo.gif"

APP_URL = "http://127.0.0.1:8119/"
DEVTOOLS = "http://127.0.0.1:9222"
# Wide enough for all three columns; the voice panel lives in the right rail and
# a narrower viewport simply crops it out of the recording.
WIDTH, HEIGHT, SCALE = 1600, 900, 2

# Each step: a label, JavaScript to run first, and how many frames to hold the
# result for. Holds give a reader time to actually read the panel.
STEPS: list[tuple[str, str, int]] = [
    ("open", "", 8),
    (
        "tidy-off",
        """(() => {
          const box = [...document.querySelectorAll('.workspace-actions input[type=checkbox]')][0];
          if (box && box.checked) box.click();
        })()""",
        9,
    ),
    (
        "tidy-on",
        """(() => {
          const box = [...document.querySelectorAll('.workspace-actions input[type=checkbox]')][0];
          if (box && !box.checked) box.click();
        })()""",
        9,
    ),
    (
        "voice",
        """(() => {
          const first = document.querySelector('.speaker-summary');
          if (first) first.click();
        })()""",
        12,
    ),
    (
        "collections",
        """(() => {
          const tab = [...document.querySelectorAll('.collection-tab')]
            .find(node => node.textContent.includes('Conversations'));
          if (tab) tab.click();
        })()""",
        8,
    ),
    (
        "models",
        """(() => {
          const trigger = document.querySelector('.model-trigger');
          if (trigger) trigger.click();
        })()""",
        12,
    ),
]


def devtools_target() -> str:
    with urllib.request.urlopen(f"{DEVTOOLS}/json", timeout=10) as response:
        for target in json.load(response):
            if target.get("type") == "page":
                return target["webSocketDebuggerUrl"]
    raise SystemExit("no Chrome page target; is it running with --remote-debugging-port=9222?")


class Session:
    def __init__(self, socket) -> None:
        self.socket = socket
        self.counter = 0

    async def call(self, method: str, **params):
        self.counter += 1
        await self.socket.send(
            json.dumps({"id": self.counter, "method": method, "params": params})
        )
        while True:
            message = json.loads(await self.socket.recv())
            if message.get("id") == self.counter:
                if "error" in message:
                    raise SystemExit(f"{method} failed: {message['error']}")
                return message.get("result", {})


async def record() -> int:
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True)

    async with websockets.connect(devtools_target(), max_size=64 * 1024 * 1024) as socket:
        page = Session(socket)
        await page.call("Page.enable")
        await page.call(
            "Emulation.setDeviceMetricsOverride",
            width=WIDTH,
            height=HEIGHT,
            deviceScaleFactor=SCALE,
            mobile=False,
        )
        await page.call("Page.navigate", url=APP_URL)
        await asyncio.sleep(4)

        index = 0
        for label, script, holds in STEPS:
            if script:
                await page.call("Runtime.evaluate", expression=script, awaitPromise=False)
                await asyncio.sleep(0.9)
            shot = await page.call("Page.captureScreenshot", format="png")
            data = base64.b64decode(shot["data"])
            for _ in range(holds):
                (FRAMES / f"frame-{index:04d}.png").write_bytes(data)
                index += 1
            print(f"  captured {label} ({holds} frames)")
        return index


def encode(frames: int) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    palette = FRAMES / "palette.png"
    common = ["-y", "-framerate", "6", "-i", str(FRAMES / "frame-%04d.png")]
    scale = "scale=1000:-1:flags=lanczos"

    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", *common,
         "-vf", f"{scale},palettegen=max_colors=128", str(palette)],
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", *common, "-i", str(palette),
         "-lavfi", f"{scale}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
         "-loop", "0", str(OUTPUT)],
        check=True,
    )
    size = OUTPUT.stat().st_size / 1_000_000
    print(f"wrote {OUTPUT} from {frames} frames ({size:.1f} MB)")


if __name__ == "__main__":
    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg is required")
    encode(asyncio.run(record()))
