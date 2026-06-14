# -*- coding: utf-8 -*-
"""Vykresli vykres s barevne klasifikovanymi rusicimi krizky (validace detekce)."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ezdxf
from ezdxf.addons import odafc
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

import cancellations

ezdxf.options.set("odafc-addon", "win_exec_path",
                  r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe")


def render(path):
    doc = odafc.readfile(path)
    msp = doc.modelspace()
    items = cancellations.detect(msp)

    fig = plt.figure(figsize=(24, 16))
    ax = fig.add_axes([0, 0, 1, 1])
    try:
        Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(msp, finalize=True)
    except Exception as ex:
        print("  varovani render: {}".format(ex))

    devs = set()
    for it in items:
        x, y = it["x"], it["y"]
        if it["typ"].startswith("zruseny HUB"):
            ax.add_patch(plt.Circle((x, y), 11, fill=False, color="red", lw=2.5))
            devs.add(it["prvek"])
        else:
            ax.add_patch(plt.Circle((x, y), 7, fill=False, color="orange", lw=1.8))

    # popisky zrusenych zarizeni
    for it in items:
        if it["typ"].startswith("zruseny HUB"):
            ax.text(it["x"] + 12, it["y"] + 7, it["prvek"], color="red", fontsize=8, weight="bold")

    out = Path(__file__).parent / (Path(path).stem + "_CANCEL.png")
    fig.savefig(str(out), dpi=120)
    plt.close(fig)
    print("[PNG] {}  zarizeni={} spoju={}".format(
        out, len(devs), sum(1 for i in items if i["typ"] == "zruseny spoj")))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        render(p)
