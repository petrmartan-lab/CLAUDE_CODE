# -*- coding: utf-8 -*-
"""Vykresli vykres do PNG a cervene zvyrazni dlouhe krizky (rusena spojeni)."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ezdxf
from ezdxf.addons import odafc
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

from crosses_context import diag_lines, find_crosses

ODA_EXE = r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"
ezdxf.options.set("odafc-addon", "win_exec_path", ODA_EXE)


def render(path, outdir):
    doc = odafc.readfile(path)
    msp = doc.modelspace()
    crosses = find_crosses(diag_lines(msp))

    fig = plt.figure(figsize=(22, 15))
    ax = fig.add_axes([0, 0, 1, 1])
    try:
        Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(msp, finalize=True)
    except Exception as ex:
        print("  varovani pri renderu: {}".format(ex))

    for x, y in crosses:
        ax.add_patch(plt.Circle((x, y), 12, fill=False, color="red", lw=2.5))

    name = Path(path).stem + "_KRIZKY.png"
    out = Path(outdir) / name
    fig.savefig(str(out), dpi=120)
    plt.close(fig)
    print("[PNG] {}  (krizku: {})".format(out, len(crosses)))


if __name__ == "__main__":
    outdir = Path(__file__).parent
    for p in sys.argv[1:]:
        render(p, outdir)
