from __future__ import annotations

from pathlib import Path
from typing import Any

from multilevel.numbers import parse_box, parse_number, parse_point


def _fmt(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _bounds(boxes: list[tuple]) -> tuple[float, float, float, float]:
    xs = [float(box[0]) for box in boxes] + [float(box[1]) for box in boxes]
    ys = [float(box[2]) for box in boxes] + [float(box[3]) for box in boxes]
    if not xs:
        return 0.0, 1.0, 0.0, 1.0
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)
    if x1 == x2:
        x2 += 1.0
    if y1 == y2:
        y2 += 1.0
    pad = max(x2 - x1, y2 - y1) * 0.08 + 0.5
    return x1 - pad, x2 + pad, y1 - pad, y2 + pad


class Canvas:
    def __init__(self, bounds: tuple[float, float, float, float], width: int = 900, height: int = 640):
        self.x1, self.x2, self.y1, self.y2 = bounds
        self.width = width
        self.height = height
        self.items: list[str] = []

    def sx(self, x: float) -> float:
        return (x - self.x1) / (self.x2 - self.x1) * self.width

    def sy(self, y: float) -> float:
        return self.height - (y - self.y1) / (self.y2 - self.y1) * self.height

    def rect(self, box, *, fill: str, stroke: str, opacity: float = 0.32, width: float = 1.4) -> None:
        x1, x2, y1, y2 = [float(v) for v in box]
        x = self.sx(x1)
        y = self.sy(y2)
        w = self.sx(x2) - self.sx(x1)
        h = self.sy(y1) - self.sy(y2)
        self.items.append(
            f'<rect x="{_fmt(x)}" y="{_fmt(y)}" width="{_fmt(w)}" height="{_fmt(h)}" '
            f'fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="{width}"/>'
        )

    def line(self, x1: float, y1: float, x2: float, y2: float, *, stroke: str, width: float = 1.8, dash: str | None = None) -> None:
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        self.items.append(
            f'<line x1="{_fmt(self.sx(x1))}" y1="{_fmt(self.sy(y1))}" '
            f'x2="{_fmt(self.sx(x2))}" y2="{_fmt(self.sy(y2))}" '
            f'stroke="{stroke}" stroke-width="{width}"{dash_attr}/>'
        )

    def text(self, x: float, y: float, label: str, *, size: int = 13, fill: str = "#111827") -> None:
        self.items.append(
            f'<text x="{_fmt(self.sx(x))}" y="{_fmt(self.sy(y))}" '
            f'font-size="{size}" font-family="monospace" fill="{fill}">{label}</text>'
        )

    def svg(self, title: str) -> str:
        return "\n".join(
            [
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}">',
                f"<title>{title}</title>",
                '<rect width="100%" height="100%" fill="#ffffff"/>',
                *self.items,
                "</svg>",
                "",
            ]
        )


def render_certificate(cert: dict[str, Any], out_path: str | Path) -> Path:
    schema = cert.get("schema")
    if schema == "misr_certificate_v1":
        svg = render_misr(cert)
    elif schema == "unit_square_stab_certificate_v1":
        svg = render_unit_square(cert)
    elif schema == "guillotine_certificate_v1":
        svg = render_guillotine(cert)
    elif schema == "epsilon_net_certificate_v1":
        svg = render_epsilon_net(cert)
    elif schema == "graph_separation_certificate_v1":
        svg = render_graph_separation(cert)
    else:
        raise ValueError(f"unknown certificate schema: {schema!r}")
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(svg, encoding="utf-8")
    return target


def render_misr(cert: dict[str, Any]) -> str:
    boxes = [parse_box(row) for row in cert["rectangles"]]
    canvas = Canvas(_bounds(boxes))
    chosen = set(cert.get("integer_solution", []))
    for idx, box in enumerate(boxes):
        if idx in chosen:
            canvas.rect(box, fill="#22c55e", stroke="#166534", opacity=0.36, width=2.0)
        else:
            canvas.rect(box, fill="#60a5fa", stroke="#1d4ed8", opacity=0.24)
        canvas.text(float(box[0]), float(box[3]), str(idx), fill="#111827")
    title = f"MISR score={cert.get('score')} alpha_lp={cert.get('alpha_lp')} alpha={cert.get('alpha_int')}"
    return canvas.svg(title)


def render_unit_square(cert: dict[str, Any]) -> str:
    points = [parse_point(row) for row in cert["squares"]]
    side = parse_number(cert.get("side", 1))
    boxes = [(x, x + side, y, y + side) for x, y in points]
    canvas = Canvas(_bounds(boxes))
    for idx, box in enumerate(boxes):
        canvas.rect(box, fill="#fbbf24", stroke="#92400e", opacity=0.32)
        canvas.text(float(box[0]), float(box[3]), str(idx), fill="#111827")
    selected = set(cert.get("integer_lines", []))
    bounds = canvas.x1, canvas.x2, canvas.y1, canvas.y2
    for line in cert.get("critical_lines", []):
        if line.get("id") not in selected:
            continue
        coord = float(parse_number(line["coordinate"]))
        if line.get("axis") == "vertical":
            canvas.line(coord, bounds[2], coord, bounds[3], stroke="#dc2626", width=2.4)
        else:
            canvas.line(bounds[0], coord, bounds[1], coord, stroke="#dc2626", width=2.4)
    title = f"Unit-square score={cert.get('score')} tau={cert.get('tau_int')} tau_lp={cert.get('tau_lp')}"
    return canvas.svg(title)


def _draw_strategy(canvas: Canvas, strategy: dict[str, Any], bounds: tuple[float, float, float, float]) -> None:
    if not strategy or strategy.get("type") != "cut":
        return
    coord = float(parse_number(strategy["coordinate"]))
    x1, x2, y1, y2 = bounds
    if strategy.get("axis") == "vertical":
        canvas.line(coord, y1, coord, y2, stroke="#7c3aed", width=1.5, dash="8 5")
        low_bounds = (x1, coord, y1, y2)
        high_bounds = (coord, x2, y1, y2)
    else:
        canvas.line(x1, coord, x2, coord, stroke="#7c3aed", width=1.5, dash="8 5")
        low_bounds = (x1, x2, y1, coord)
        high_bounds = (x1, x2, coord, y2)
    _draw_strategy(canvas, strategy.get("low", {}), low_bounds)
    _draw_strategy(canvas, strategy.get("high", {}), high_bounds)


def render_guillotine(cert: dict[str, Any]) -> str:
    boxes = [parse_box(row) for row in cert["rectangles"]]
    canvas = Canvas(_bounds(boxes))
    for idx, box in enumerate(boxes):
        canvas.rect(box, fill="#38bdf8", stroke="#075985", opacity=0.34)
        canvas.text(float(box[0]), float(box[3]), str(idx), fill="#111827")
    _draw_strategy(canvas, cert.get("optimal_strategy", {}), (canvas.x1, canvas.x2, canvas.y1, canvas.y2))
    title = f"Guillotine score={cert.get('score')} saved={cert.get('saved')} n={cert.get('n')}"
    return canvas.svg(title)


def render_epsilon_net(cert: dict[str, Any]) -> str:
    points = [parse_point(row) for row in cert["points"]]
    boxes = [(x, x, y, y) for x, y in points]
    canvas = Canvas(_bounds(boxes))
    for idx, point in enumerate(points):
        x, y = float(point[0]), float(point[1])
        sx, sy = canvas.sx(x), canvas.sy(y)
        canvas.items.append(f'<circle cx="{_fmt(sx)}" cy="{_fmt(sy)}" r="5" fill="#111827"/>')
        canvas.text(x, y, f" {idx}", fill="#111827")
    witness = cert.get("witnesses", [{}])[0] if cert.get("witnesses") else {}
    if witness:
        nx, ny = [float(v) for v in witness.get("normal", [1.0, 0.0])]
        c = float(witness.get("strict_threshold", 0.0))
        # Draw the witness boundary n.x = c across the canvas.
        x1, x2, y1, y2 = canvas.x1, canvas.x2, canvas.y1, canvas.y2
        pts = []
        if abs(ny) > 1e-9:
            pts.append((x1, (c - nx * x1) / ny))
            pts.append((x2, (c - nx * x2) / ny))
        if abs(nx) > 1e-9:
            pts.append(((c - ny * y1) / nx, y1))
            pts.append(((c - ny * y2) / nx, y2))
        visible = [(x, y) for x, y in pts if x1 - 1 <= x <= x2 + 1 and y1 - 1 <= y <= y2 + 1]
        if len(visible) >= 2:
            canvas.line(visible[0][0], visible[0][1], visible[1][0], visible[1][1], stroke="#dc2626", width=2.0, dash="6 4")
    title = f"Epsilon-net n={cert.get('n')} t={cert.get('threshold')} k={cert.get('k')} score={cert.get('score')}"
    return canvas.svg(title)


def render_graph_separation(cert: dict[str, Any]) -> str:
    boxes = [parse_box(row) for row in cert["rectangles"]]
    canvas = Canvas(_bounds(boxes))
    for idx, box in enumerate(boxes):
        canvas.rect(box, fill="#a78bfa", stroke="#5b21b6", opacity=0.30)
        canvas.text(float(box[0]), float(box[3]), str(idx), fill="#111827")
    title = f"Graph separation bounded status={cert.get('mixed_status')} n={cert.get('n')}"
    return canvas.svg(title)
