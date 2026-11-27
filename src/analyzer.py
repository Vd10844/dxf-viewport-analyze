"""Paper-space viewport analysis for DXF drawings."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import ezdxf
from ezdxf import recover
from ezdxf.document import Drawing
from ezdxf.entities import Viewport
from ezdxf.layouts import Paperspace
from ezdxf.lldxf.const import VSF_LOCK_ZOOM


@dataclass
class ViewportInfo:
    viewport_id: int
    handle: str
    center: tuple[float, float]          # paper-space location of the viewport
    width: float                         # paper-space size
    height: float
    view_center: tuple[float, float]     # model-space point shown at the viewport center
    view_target: tuple[float, float, float]
    view_height: float                   # model-space height shown in the viewport
    scale: str | None                    # e.g. "1:100"; None if it cannot be derived
    twist_angle: float                   # degrees
    locked: bool
    on: bool
    frozen_layers: list[str] = field(default_factory=list)


@dataclass
class LayoutInfo:
    layout: str
    tab_order: int
    viewport_count: int
    viewports: list[ViewportInfo]


@dataclass
class DrawingReport:
    file: str
    dxf_version: str
    recovered: bool                      # True if the file had structure errors and was repaired on load
    layout_count: int
    layouts: list[LayoutInfo]

    def to_dict(self) -> dict:
        return asdict(self)


def load_dxf(path: str | Path) -> tuple[Drawing, bool]:
    """Load a DXF file, falling back to ezdxf's recover mode for damaged files.

    Returns the document and whether recovery was needed.
    Raises FileNotFoundError or ezdxf.DXFStructureError if the file can't be read.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    try:
        return ezdxf.readfile(path), False
    except ezdxf.DXFStructureError:
        doc, _ = recover.readfile(path)
        return doc, True


def _format_scale(vp: Viewport) -> str | None:
    """Express the viewport scale as a ratio string such as '1:100' or '2:1'."""
    if vp.dxf.height <= 0 or vp.dxf.view_height <= 0:
        return None
    ratio = vp.dxf.view_height / vp.dxf.height   # model units per paper unit
    if ratio >= 1:
        return f"1:{ratio:g}" if ratio == round(ratio) else f"1:{ratio:.4g}"
    inverse = 1 / ratio
    return f"{inverse:g}:1" if inverse == round(inverse) else f"{inverse:.4g}:1"


def _viewport_info(vp: Viewport) -> ViewportInfo:
    d = vp.dxf
    return ViewportInfo(
        viewport_id=d.get("id", 0),
        handle=d.handle,
        center=(round(d.center.x, 6), round(d.center.y, 6)),
        width=d.width,
        height=d.height,
        view_center=(round(d.view_center_point.x, 6), round(d.view_center_point.y, 6)),
        view_target=tuple(round(v, 6) for v in d.view_target_point),
        view_height=d.view_height,
        scale=_format_scale(vp),
        twist_angle=d.get("view_twist_angle", 0.0),
        locked=bool(d.get("flags", 0) & VSF_LOCK_ZOOM),
        on=d.get("status", 1) != 0,
        frozen_layers=list(vp.frozen_layers),
    )


def analyze_layout(layout: Paperspace) -> LayoutInfo:
    # Every activated paper-space layout has an "overall" viewport (ID 1) that
    # represents the sheet itself. It is not a user viewport, so skip it.
    main = layout.main_viewport()
    main_handle = main.dxf.handle if main is not None else None

    viewports = [
        _viewport_info(vp)
        for vp in layout.query("VIEWPORT")
        if vp.dxf.handle != main_handle and vp.dxf.get("id", 0) != 1
    ]
    viewports.sort(key=lambda v: v.viewport_id)

    return LayoutInfo(
        layout=layout.name,
        tab_order=layout.dxf.get("taborder", 0),
        viewport_count=len(viewports),
        viewports=viewports,
    )


def analyze_dxf(path: str | Path) -> DrawingReport:
    """Analyze every paper-space layout in a DXF file and return a report."""
    doc, recovered = load_dxf(path)

    layouts = [
        analyze_layout(layout)
        for layout in doc.layouts
        if not layout.is_modelspace
    ]
    layouts.sort(key=lambda lay: lay.tab_order)

    return DrawingReport(
        file=str(Path(path).name),
        dxf_version=doc.acad_release,
        recovered=recovered,
        layout_count=len(layouts),
        layouts=layouts,
    )


def format_report(report: DrawingReport, verbose: bool = False) -> str:
    """Render a report as human-readable text."""
    lines = [
        f"File: {report.file}  (DXF {report.dxf_version})",
    ]
    if report.recovered:
        lines.append("  Warning: file had structure errors and was recovered")
    lines.append(f"Layouts Found: {report.layout_count}")

    for lay in report.layouts:
        lines.append("")
        lines.append(f"Layout: {lay.layout}")
        lines.append(f"  Viewports: {lay.viewport_count}")
        for vp in lay.viewports:
            status = []
            status.append("locked" if vp.locked else "UNLOCKED")
            if not vp.on:
                status.append("OFF")
            lines.append(
                f"    #{vp.viewport_id}  scale {vp.scale or '?'}  "
                f"{vp.width:g} x {vp.height:g}  [{', '.join(status)}]"
            )
            if verbose:
                lines.append(f"        handle:       {vp.handle}")
                lines.append(f"        center:       {vp.center}")
                lines.append(f"        view center:  {vp.view_center}")
                lines.append(f"        view target:  {vp.view_target}")
                lines.append(f"        twist:        {vp.twist_angle:g} deg")
                if vp.frozen_layers:
                    lines.append(f"        frozen:       {', '.join(vp.frozen_layers)}")
    return "\n".join(lines)
