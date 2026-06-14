# -*- coding: utf-8 -*-
"""Zoom render casti vykresu + cervene krizky. Pouziti: py render_zoom.py <dwg> xmin xmax ymin ymax"""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ezdxf
from ezdxf.addons import odafc
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from crosses_context import diag_lines, find_crosses
from pathlib import Path

ezdxf.options.set("odafc-addon", "win_exec_path",
                  r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe")

path = sys.argv[1]
xmin, xmax, ymin, ymax = map(float, sys.argv[2:6])
doc = odafc.readfile(path)
msp = doc.modelspace()
cr = find_crosses(diag_lines(msp), 0.0, 40.0, 3.0)

fig = plt.figure(figsize=(20, 15))
ax = fig.add_axes([0, 0, 1, 1])
Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(msp, finalize=True)
for x, y in cr:
    if xmin <= x <= xmax and ymin <= y <= ymax:
        ax.add_patch(plt.Circle((x, y), 2.5, fill=False, color="red", lw=1.5))
ax.set_xlim(xmin, xmax)
ax.set_ylim(ymin, ymax)
out = Path(__file__).parent / (Path(path).stem + "_ZOOM.png")
fig.savefig(str(out), dpi=150)
print("[PNG]", out)
