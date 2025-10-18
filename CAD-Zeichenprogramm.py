#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Viereck CAD - Monolithische PySide6 Datei
Enthält: Quad (Start 340cm x 180cm), Raster an, Einheit cm, Linien, Schnittpunkte,
Drag/Move (ganze Figur), numerische Seiten-/Winkelbearbeitung, Fixier-Mechanik für Seiten + Ecken,
Markierung fixierter Elemente, Screenshot, Zoom, Reset, Hilfe.
Dateiname: main.py
"""
from PySide6 import QtCore, QtGui, QtWidgets
import math, sys, os
import requests
import subprocess

APP_VERSION = "4.0.0"
GITHUB_API = "https://api.github.com/repos/clanmonsterxd-cmd/CAD-Zeichner/releases/latest"

def _fallback_is_newer(latest: str, current: str) -> bool:
    """Compare two semantic-ish versions without relying on packaging."""
    try:
        parts_latest = [int(p) for p in latest.split('.') if p.strip() != '']
        parts_current = [int(p) for p in current.split('.') if p.strip() != '']
    except ValueError:
        return latest != current
    length = max(len(parts_latest), len(parts_current))
    parts_latest.extend([0] * (length - len(parts_latest)))
    parts_current.extend([0] * (length - len(parts_current)))
    return parts_latest > parts_current


def check_for_updates_threaded(parent=None):
    """Runs the GitHub update check in a background thread with graceful fallbacks."""
    import threading
    try:
        from packaging.version import parse as vparse
    except ImportError:
        vparse = None

    def is_newer(latest: str, current: str) -> bool:
        if not latest:
            return False
        if vparse is not None:
            try:
                return vparse(latest) > vparse(current)
            except Exception:
                pass
        return _fallback_is_newer(latest, current)

    def run_check():
        try:
            resp = requests.get(GITHUB_API, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            latest_version = (data.get("tag_name") or "").lstrip("v")
            if not is_newer(latest_version, APP_VERSION):
                return

            exe_path = sys.argv[0]
            exe_dir = os.path.dirname(exe_path)
            updater_path = os.path.join(exe_dir, "updater.exe")

            if parent is not None:
                QtCore.QMetaObject.invokeMethod(
                    parent, "_show_update_dialog",
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(str, latest_version),
                    QtCore.Q_ARG(str, updater_path),
                    QtCore.Q_ARG(str, exe_path)
                )
        except Exception as e:
            print("Update-Check fehlgeschlagen:", e)

    threading.Thread(target=run_check, daemon=True).start()
MARGIN_MM = 30.0
CORNER_RADIUS_MM = 6.0
SNAP_TOL_MM = 8.0
HANDLE_DISPLAY_SCALE = 1.6
FONT_PT = 14
DEFAULT_SIDE_MM = 500.0
MIN_SCALE = 0.05
MAX_SCALE = 20.0

UNIT_TO_MM = {'mm': 1.0, 'cm': 10.0, 'm': 1000.0}
UNIT_LABEL = {'mm': 'mm', 'cm': 'cm', 'm': 'm'}
UNIT_PEN_WIDTH = {'mm': 4, 'cm': 3, 'm': 6}

def mm_to_px(mm, px_per_mm):
    return mm * px_per_mm

def px_to_mm(px, px_per_mm):
    return px / px_per_mm

def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def dot(u,v):
    return u[0]*v[0] + u[1]*v[1]

def angle_between(u,v):
    nu = math.hypot(u[0], u[1])
    nv = math.hypot(v[0], v[1])
    if nu == 0 or nv == 0:
        return 0.0
    cosv = dot(u,v)/(nu*nv)
    cosv = max(-1.0, min(1.0, cosv))
    return math.degrees(math.acos(cosv))

def angle_signed(a,b,c):
    v1 = (a[0]-b[0], a[1]-b[1])
    v2 = (c[0]-b[0], c[1]-b[1])
    ang1 = math.atan2(v1[1], v1[0])
    ang2 = math.atan2(v2[1], v2[0])
    deg = math.degrees(ang2 - ang1)
    while deg < 0:
        deg += 360
    return deg

def project_point_segment(p, a, b):
    vx = b[0]-a[0]; vy = b[1]-a[1]
    wx = p[0]-a[0]; wy = p[1]-a[1]
    denom = vx*vx + vy*vy
    if denom == 0:
        return a, 0.0
    t = (wx*vx + wy*vy)/denom
    if t < 0:
        t = 0.0
    elif t > 1:
        t = 1.0
    proj = (a[0] + t*vx, a[1] + t*vy)
    return proj, t

def intersect_segments(a1,a2,b1,b2):
    x1,y1 = a1; x2,y2 = a2; x3,y3 = b1; x4,y4 = b2
    denom = (y4-y3)*(x2-x1) - (x4-x3)*(y2-y1)
    if abs(denom) < 1e-9:
        return False, None, False, False
    ua = ((x4-x3)*(y1-y3) - (y4-y3)*(x1-x3))/denom
    ub = ((x2-x1)*(y1-y3) - (y2-y1)*(x1-x3))/denom
    xi = x1 + ua*(x2-x1)
    yi = y1 + ua*(y2-y1)
    onA = (ua >= 0.0 and ua <= 1.0)
    onB = (ub >= 0.0 and ub <= 1.0)
    return True, (xi, yi), onA, onB

def clamp(v,a,b): return max(a, min(b, v))

class CADCanvas(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

        screen = QtWidgets.QApplication.primaryScreen()
        dpi = screen.logicalDotsPerInchX() if screen is not None else 96.0
        self.px_per_mm_base = dpi / 25.4
        self.scale = 1.0

        self.unit = 'cm'
        self.grid_mm = 10.0
        self.show_grid = True

        self.quad = None
        self.user_lines = []
        self.intersection_handles = []

        self.fixed_sides = [False, False, False, False]
        self.fixed_corners = [False, False, False, False]
        self.initial_quad = None  # Referenz für Ausrichtung nach Änderungen
        self.side_lengths = [0.0, 0.0, 0.0, 0.0]
        self.angle_values = [90.0, 90.0, 90.0, 90.0]
        self.fixed_side_values_mm = [None, None, None, None]
        self.fixed_side_values_px = [None, None, None, None]
        self.fixed_corner_values_deg = [None, None, None, None]
        self._is_solving_constraints = False
        self._in_reconstruct = False
        self._last_user_lines_signature = None
        self.settings = QtCore.QSettings("clanmonsterxd-cmd", "CAD-Zeichner")
        self.show_debug_overlay = self.settings.value("debug_overlay", False, type=bool)

        self.last_side_idx = None
        self.last_corner_idx = None

        self.drawing_line = False
        self.temp_p1 = None
        self.temp_p2 = None

        self.dragging_side = False
        self.drag_side_idx = None
        self.drag_side_initial = None

        self.dragging_line = False
        self.drag_line_idx = None
        self.drag_line_initial = None

        self.dragging_move_all = False
        self.drag_move_initial = None

        self.dragging_handle = False
        self.drag_handle_info = None

        self.update_scale_dependent_metrics()
        self.font = QtGui.QFont('Arial', FONT_PT)
        self.debug_font = QtGui.QFont('Consolas', 9)
        self.default_side_mm = DEFAULT_SIDE_MM
        self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent)

        QtCore.QTimer.singleShot(0, self.init_quad_default)

    def effective_px_per_mm(self):
        return self.px_per_mm

    def update_scale_dependent_metrics(self):
        self.px_per_mm = self.px_per_mm_base * self.scale
        self.snap_tol_px = mm_to_px(SNAP_TOL_MM, self.px_per_mm)
        self.corner_radius_px = mm_to_px(CORNER_RADIUS_MM, self.px_per_mm)
        self.handle_radius_px = max(5.0, self.corner_radius_px * 0.9)
        self.grid_step_px = mm_to_px(self.grid_mm, self.px_per_mm)

    def has_active_constraints(self) -> bool:
        return any(self.fixed_sides) or any(self.fixed_corners)

    def init_quad_default(self):
        w = max(100, self.width())
        h = max(100, self.height())
        self.update_scale_dependent_metrics()
        gs = self.grid_step_px
        # Zielgröße in cm -> Pixel
        quad_w_mm = 340.0 * UNIT_TO_MM['cm']
        quad_h_mm = 180.0 * UNIT_TO_MM['cm']
        quad_w_px = mm_to_px(quad_w_mm, self.effective_px_per_mm())
        quad_h_px = mm_to_px(quad_h_mm, self.effective_px_per_mm())
        cx = w / 2
        cy = h / 2
        # Position berechnen
        left = cx - quad_w_px / 2
        top = cy - quad_h_px / 2
        right = left + quad_w_px
        bottom = top + quad_h_px
        # Viereck erstellen
        self.quad = [
            (left, top),
            (right, top),
            (right, bottom),
            (left, bottom)
        ]
        # Nur am Raster ausrichten, wenn das Raster aktiv ist
        if self.show_grid and gs > 1:
            # Mittelpunkt des Vierecks
            cx = sum(p[0] for p in self.quad) / 4.0
            cy = sum(p[1] for p in self.quad) / 4.0
            # Nächstgelegenen Raster-Mittelpunkt finden
            cx_snap = round(cx / gs) * gs
            cy_snap = round(cy / gs) * gs
            # Verschiebung berechnen, um Zentrum zu snappen
            dx = cx_snap - cx
            dy = cy_snap - cy
            # Ganze Figur verschieben, statt jede Ecke einzeln
            self.quad = [(p[0] + dx, p[1] + dy) for p in self.quad]

        # Status zurücksetzen
        self.fixed_sides = [False, False, False, False]
        self.fixed_corners = [False, False, False, False]
        self.fixed_side_values_mm = [None, None, None, None]
        self.fixed_side_values_px = [None, None, None, None]
        self.fixed_corner_values_deg = [None, None, None, None]
        self.last_side_idx = None
        self.last_corner_idx = None
        self._last_user_lines_signature = None
        # Aktualisieren
        self._recalc_user_lines()
        self.auto_adjust_scale_if_needed()
        self.initial_quad = [tuple(p) for p in self.quad]
        self.update()

    def center_quad(self):
        if not self.quad:
            return
        cx_widget = self.width()/2.0
        cy_widget = self.height()/2.0
        cx = sum(p[0] for p in self.quad)/4.0
        cy = sum(p[1] for p in self.quad)/4.0
        dx = cx_widget - cx
        dy = cy_widget - cy
        self.quad = [(p[0]+dx, p[1]+dy) for p in self.quad]
        for ln in self.user_lines:
            ln['p1'] = (ln['p1'][0]+dx, ln['p1'][1]+dy)
            ln['p2'] = (ln['p2'][0]+dx, ln['p2'][1]+dy)

    def set_unit(self, unit_name: str):
        if unit_name not in UNIT_TO_MM:
            return
        self.unit = unit_name
        self.update_scale_dependent_metrics()
        self.update()

    def format_length_mm(self, length_mm: float) -> str:
        factor = UNIT_TO_MM.get(self.unit, 1.0)
        val = length_mm / factor
        return f"{int(round(val))} {UNIT_LABEL[self.unit]}"

    def format_angle(self, angle_deg: float) -> str:
        return f"{int(round(angle_deg))}°"

    def paintEvent(self, ev):
        qp = QtGui.QPainter(self)
        qp.setRenderHint(QtGui.QPainter.Antialiasing)
        qp.fillRect(self.rect(), QtGui.QColor('white'))

        if self.show_grid:
            self._paint_grid(qp)

        if self.quad:
            for i in range(4):
                a = self.quad[i]; b = self.quad[(i+1)%4]
                if self.fixed_sides[i]:
                    pen = QtGui.QPen(QtGui.QColor('orange'))
                    pen.setStyle(QtCore.Qt.DashLine)
                    pen.setWidth(UNIT_PEN_WIDTH.get(self.unit, 4))
                else:
                    pen = QtGui.QPen(QtGui.QColor('blue'))
                    pen.setWidth(UNIT_PEN_WIDTH.get(self.unit, 4))
                qp.setPen(pen)
                qp.drawLine(QtCore.QPointF(a[0], a[1]), QtCore.QPointF(b[0], b[1]))

        handle_pen = QtGui.QPen(QtGui.QColor('black'))
        handle_pen.setWidth(2)
        qp.setPen(handle_pen)
        if self.quad:
            for idx, p in enumerate(self.quad):
                if self.fixed_corners[idx]:
                    brush = QtGui.QBrush(QtGui.QColor('orange'))
                else:
                    brush = QtGui.QBrush(QtGui.QColor(200,230,255))
                qp.setBrush(brush)
                r = self.corner_radius_px * HANDLE_DISPLAY_SCALE
                qp.drawEllipse(QtCore.QPointF(p[0], p[1]), r, r)
        qp.setBrush(QtGui.QBrush())

        qp.setFont(self.font)
        text_pen = QtGui.QPen(QtGui.QColor('black'))
        qp.setPen(text_pen)

        if self.quad:
            self._recalc_user_lines()
            for i in range(4):
                a = self.quad[i]; b = self.quad[(i+1)%4]
                mx = (a[0]+b[0])/2; my = (a[1]+b[1])/2
                length_px = dist(a,b)
                length_mm = px_to_mm(length_px, self.effective_px_per_mm())

                txt = self.format_length_mm(length_mm)
                if self.fixed_sides[i] and self.fixed_side_values_mm[i] is not None:
                    txt = self.format_length_mm(self.fixed_side_values_mm[i])

                dx = b[0]-a[0]; dy = b[1]-a[1]
                norm = math.hypot(dx, dy)
                if norm == 0:
                    offx, offy = 6, -6
                else:
                    nx, ny = -dy/norm, dx/norm
                    if i == 0:
                        offx, offy = 0, -18
                    elif i == 1:
                        offx, offy = 18, 0
                    elif i == 2:
                        offx, offy = 0, 24
                    else:
                        offx, offy = -24, 0

                fm = qp.fontMetrics()
                w = fm.horizontalAdvance(txt) + 6
                h = fm.height() + 2
                bg_rect = QtCore.QRectF(mx+offx-3, my+offy- fm.ascent(), w, h)
                qp.setBrush(QtGui.QBrush(QtGui.QColor(255,255,240,230)))
                qp.setPen(QtGui.QPen(QtGui.QColor(200,200,200)))
                qp.drawRect(bg_rect)
                qp.setPen(text_pen)
                qp.drawText(QtCore.QPointF(mx+offx, my+offy), txt)
                qp.setBrush(QtGui.QBrush())

                side_pts = []
                for h in self.intersection_handles:
                    if h.get('kind') == 'side' and h['side'] == i:
                        side_pts.append(h['pt'])

                if side_pts:
                    pts = [a, b] + side_pts
                    pts_sorted = sorted(pts, key=lambda p: (p[0]-a[0])**2 + (p[1]-a[1])**2)
                    for j in range(len(pts_sorted)-1):
                        p1, p2 = pts_sorted[j], pts_sorted[j+1]
                        seg_len = px_to_mm(dist(p1, p2), self.effective_px_per_mm())
                        seg_txt = self.format_length_mm(seg_len)
                        mx2 = (p1[0]+p2[0])/2
                        my2 = (p1[1]+p2[1])/2
                        if norm == 0:
                            offx_in, offy_in = -6, 6
                        else:
                            offx_in, offy_in = -nx*14, -ny*14
                        fm2 = qp.fontMetrics()
                        w2 = fm2.horizontalAdvance(seg_txt) + 4
                        h2 = fm2.height() + 2
                        bg_rect2 = QtCore.QRectF(mx2+offx_in-2, my2+offy_in - fm2.ascent(), w2, h2)
                        qp.setBrush(QtGui.QBrush(QtGui.QColor(240,255,240,220)))
                        qp.setPen(QtGui.QPen(QtGui.QColor(200,200,200)))
                        qp.drawRect(bg_rect2)
                        qp.setPen(text_pen)
                        qp.drawText(QtCore.QPointF(mx2+offx_in, my2+offy_in), seg_txt)
                        qp.setBrush(QtGui.QBrush())

        qp.setPen(text_pen)
        if self.quad:
            for i in range(4):
                prev = self.quad[(i+3)%4]; cur = self.quad[i]; nxt = self.quad[(i+1)%4]
                ang = angle_signed(prev, cur, nxt)
                interior = 360-ang if ang>180 else ang
                if self.fixed_corners[i] and self.fixed_corner_values_deg[i] is not None:
                    txt = self.format_angle(self.fixed_corner_values_deg[i])
                else:
                    txt = self.format_angle(interior)
                qp.drawText(QtCore.QPointF(cur[0]+8, cur[1]+8), txt)

        pen_lines = QtGui.QPen(QtGui.QColor('red'))
        pen_lines.setWidth(2)
        qp.setPen(pen_lines)
        for idx, ln in enumerate(self.user_lines):
            p1 = ln['p1']; p2 = ln['p2']
            qp.drawLine(QtCore.QPointF(p1[0], p1[1]), QtCore.QPointF(p2[0], p2[1]))
            mx = (p1[0]+p2[0])/2; my = (p1[1]+p2[1])/2
            txt = f"{self.format_length_mm(ln['length_mm'])}, {self.format_angle(ln['angle_deg'])}"
            fm = qp.fontMetrics()
            w = fm.horizontalAdvance(txt) + 6
            h = fm.height() + 2
            qp.setBrush(QtGui.QBrush(QtGui.QColor(255,255,230,230)))
            qp.setPen(QtGui.QPen(QtGui.QColor(200,200,200)))
            qp.drawRect(QtCore.QRectF(mx+6, my+6 - fm.ascent(), w, h))
            qp.setPen(text_pen)
            qp.drawText(QtCore.QPointF(mx+6, my+6), txt)
            qp.setBrush(QtGui.QBrush())

        for h in self.intersection_handles:
            pt = h['pt']; kind = h['kind']
            if kind == 'side':
                qp.setPen(QtGui.QPen(QtGui.QColor('darkgreen')))
                qp.setBrush(QtGui.QBrush(QtGui.QColor(180,255,190)))
                hr = self.handle_radius_px
                qp.drawEllipse(QtCore.QPointF(pt[0], pt[1]), hr, hr)
                si = h['side']
                ca = self.quad[si]; cb = self.quad[(si+1)%4]
                side_v = (cb[0]-ca[0], cb[1]-ca[1])
                ln = self.user_lines[h['line_idx']]
                ln_v = (ln['p2'][0]-ln['p1'][0], ln['p2'][1]-ln['p1'][1])
                side_ang = angle_between(side_v, ln_v)
                label = f"{int(round(side_ang))} Grad zur Seite"
                fm = qp.fontMetrics(); w = fm.horizontalAdvance(label) + 6; hrect = fm.height() + 4
                qp.setPen(QtGui.QPen(QtGui.QColor('black')))
                qp.setBrush(QtGui.QBrush(QtGui.QColor(255,255,220)))
                qp.drawRect(QtCore.QRectF(pt[0]+6, pt[1]+6, w, hrect))
                qp.drawText(QtCore.QPointF(pt[0]+8, pt[1]+6 + fm.ascent()), label)
                qp.setBrush(QtGui.QBrush())
            elif kind == 'line':
                qp.setPen(QtGui.QPen(QtGui.QColor('darkorange')))
                qp.setBrush(QtGui.QBrush(QtGui.QColor(255,230,180)))
                hr = self.handle_radius_px
                qp.drawEllipse(QtCore.QPointF(pt[0], pt[1]), hr, hr)
                label = "Linien-Schnitt"
                fm = qp.fontMetrics(); w = fm.horizontalAdvance(label) + 6; hrect = fm.height() + 4
                qp.setPen(QtGui.QPen(QtGui.QColor('black')))
                qp.setBrush(QtGui.QBrush(QtGui.QColor(255,255,240)))
                qp.drawRect(QtCore.QRectF(pt[0]+6, pt[1]+6, w, hrect))
                qp.drawText(QtCore.QPointF(pt[0]+8, pt[1]+6 + fm.ascent()), label)
                qp.setBrush(QtGui.QBrush())

        if self.show_debug_overlay:
            qp.save()
            qp.setFont(self.debug_font)
            fixed_side_entries = [
                f"S{i+1}={self.format_length_mm(self.fixed_side_values_mm[i])}"
                for i, flag in enumerate(self.fixed_sides)
                if flag and self.fixed_side_values_mm[i] is not None
            ]
            fixed_corner_entries = [
                f"E{i+1}={self.format_angle(self.fixed_corner_values_deg[i])}"
                for i, flag in enumerate(self.fixed_corners)
                if flag and self.fixed_corner_values_deg[i] is not None
            ]
            overlay_lines = [
                "Fixierte Seiten:",
                "  " + (", ".join(fixed_side_entries) if fixed_side_entries else "-"),
                "Fixierte Ecken:",
                "  " + (", ".join(fixed_corner_entries) if fixed_corner_entries else "-"),
            ]
            fm = qp.fontMetrics()
            width = max(fm.horizontalAdvance(line) for line in overlay_lines) + 12
            height = fm.height() * len(overlay_lines) + 10
            rect = QtCore.QRectF(
                self.width() - width - 12,
                self.height() - height - 12,
                width,
                height
            )
            qp.setBrush(QtGui.QColor(255, 255, 240, 235))
            qp.setPen(QtGui.QPen(QtGui.QColor(180, 180, 180)))
            qp.drawRect(rect)
            qp.setPen(QtGui.QPen(QtGui.QColor(30, 30, 30)))
            y = rect.top() + fm.ascent() + 5
            for line in overlay_lines:
                qp.drawText(rect.left() + 6, y, line)
                y += fm.height()
            qp.restore()

        if self.drawing_line and self.temp_p1 and self.temp_p2:
            pen_tmp = QtGui.QPen(QtGui.QColor('red'))
            pen_tmp.setStyle(QtCore.Qt.DashLine)
            pen_tmp.setWidth(2)
            qp.setPen(pen_tmp)
            qp.drawLine(QtCore.QPointF(self.temp_p1[0], self.temp_p1[1]),
                        QtCore.QPointF(self.temp_p2[0], self.temp_p2[1]))

        if self.dragging_side and self.drag_side_initial:
            i = self.drag_side_idx
            a_cur = self.quad[i]; b_cur = self.quad[(i+1)%4]
            pen_p = QtGui.QPen(QtGui.QColor('green'))
            pen_p.setWidth(3); pen_p.setStyle(QtCore.Qt.DashLine)
            qp.setPen(pen_p)
            qp.drawLine(QtCore.QPointF(a_cur[0], a_cur[1]), QtCore.QPointF(b_cur[0], b_cur[1]))

        if self.dragging_line and self.drag_line_initial:
            idx = self.drag_line_idx
            p1 = self.user_lines[idx]['p1']; p2 = self.user_lines[idx]['p2']
            pen_p = QtGui.QPen(QtGui.QColor('darkred'))
            pen_p.setWidth(2); pen_p.setStyle(QtCore.Qt.DashLine)
            qp.setPen(pen_p)
            qp.drawLine(QtCore.QPointF(p1[0], p1[1]), QtCore.QPointF(p2[0], p2[1]))

    def _paint_grid(self, qp: QtGui.QPainter):
        step_px = max(0.1, self.grid_step_px)
        draw_step = step_px
        while draw_step < 6:
            draw_step *= 2
        max_lines = 1200
        w = self.width()
        h = self.height()
        while draw_step > 0 and ((w / draw_step) > max_lines or (h / draw_step) > max_lines):
            draw_step *= 2
        if draw_step <= 0 or draw_step > 1e6:
            return
        pen = QtGui.QPen(QtGui.QColor(230, 230, 230))
        pen.setWidth(1)
        qp.setPen(pen)
        x = 0.0
        lines_drawn = 0
        while x <= w:
            qp.drawLine(int(x), 0, int(x), h)
            x += draw_step
            lines_drawn += 1
            if lines_drawn > max_lines:
                break
        y = 0.0
        lines_drawn = 0
        while y <= h:
            qp.drawLine(0, int(y), w, int(y))
            y += draw_step
            lines_drawn += 1
            if lines_drawn > max_lines:
                break

    def mousePressEvent(self, ev: QtGui.QMouseEvent):
        x = ev.position().x(); y = ev.position().y()
        pos = (x,y)

        if ev.button() == QtCore.Qt.MiddleButton:
            h = self._find_intersection_handle(pos)
            if h:
                self.dragging_handle = True
                self.drag_handle_info = dict(h)
                self.setCursor(QtCore.Qt.SizeAllCursor)
                return

            lidx = self._find_user_line_index(pos)
            if lidx is not None:
                self.dragging_line = True
                self.drag_line_idx = lidx
                ln = self.user_lines[lidx]
                self.drag_line_initial = {'p1': ln['p1'], 'p2': ln['p2'], 'mouse0': pos,
                                        'p1snap': self._point_snapped_to_side(ln['p1']),
                                        'p2snap': self._point_snapped_to_side(ln['p2'])}
                self.setCursor(QtCore.Qt.SizeAllCursor)
                return

            if self._point_in_quad(pos):  # cleaned version
                self.dragging_move_all = True
                self.drag_move_initial = {
                    'mouse0': pos,
                    'quad0': list(self.quad),
                    'lines0': [dict(p1=ln['p1'], p2=ln['p2']) for ln in self.user_lines]
                }
                self.setCursor(QtCore.Qt.ClosedHandCursor)
                return
            return

        if ev.button() == QtCore.Qt.LeftButton:
            cidx = self._find_corner_index(pos)
            if cidx is not None:
                self.last_corner_idx = cidx
                self._edit_corner_angle(cidx)
                return
            sidx, t = self._find_side_index(pos, return_t=True)
            if sidx is not None:
                self.last_side_idx = sidx
                self._edit_side_length(sidx, t, pos)
                return
            return

        if ev.button() == QtCore.Qt.RightButton:
            self.drawing_line = True
            self.temp_p1 = pos
            snap_pt, snapped = self._snap_to_any(pos)
            if snapped:
                self.temp_p1 = snap_pt
            if self.show_grid:
                self.temp_p1 = self._snap_to_grid(self.temp_p1)
            self.temp_p2 = pos
            self.update()
            return

    def mouseMoveEvent(self, ev: QtGui.QMouseEvent):
        x = ev.position().x(); y = ev.position().y()
        pos = (x,y)

        if self.drawing_line:
            snap_pt, snapped = self._snap_to_any(pos)
            if snapped:
                self.temp_p2 = snap_pt
            else:
                self.temp_p2 = self._snap_to_grid(pos) if self.show_grid else pos
            self.update()
            return

        if self.dragging_handle and self.drag_handle_info:
            info = self.drag_handle_info
            if info.get('kind') == 'side':
                ln = self.user_lines[info['line_idx']]
                proj_pt, side_idx, t_side = self._project_point_to_perimeter(pos)
                if proj_pt is None:
                    return
                if info['which'] == 'p1':
                    ln['p1'] = proj_pt
                else:
                    ln['p2'] = proj_pt
                info['pt'] = proj_pt
                info['side'] = side_idx
                info['t'] = t_side
                ln['length_mm'] = px_to_mm(dist(ln['p1'], ln['p2']), self.effective_px_per_mm())
                ang = math.degrees(math.atan2(ln['p2'][1]-ln['p1'][1], ln['p2'][0]-ln['p1'][0]))
                if ang < 0: ang += 360
                ln['angle_deg'] = ang
                self.update()
                return
            elif info.get('kind') == 'line':
                ln = self.user_lines[info['line_idx']]
                other = self.user_lines[info['other_line_idx']]
                proj, tproj = project_point_segment(pos, other['p1'], other['p2'])
                if info['which'] == 'p1':
                    ln['p1'] = proj
                else:
                    ln['p2'] = proj
                info['pt'] = proj
                ln['length_mm'] = px_to_mm(dist(ln['p1'], ln['p2']), self.effective_px_per_mm())
                ang = math.degrees(math.atan2(ln['p2'][1]-ln['p1'][1], ln['p2'][0]-ln['p1'][0]))
                if ang < 0: ang += 360
                ln['angle_deg'] = ang
                self.update()
                return

        if self.dragging_line and self.drag_line_initial:
            idx = self.drag_line_idx
            ln = self.user_lines[idx]
            mouse0 = self.drag_line_initial['mouse0']
            dx = pos[0] - mouse0[0]; dy = pos[1] - mouse0[1]
            p1snap = self.drag_line_initial.get('p1snap')
            p2snap = self.drag_line_initial.get('p2snap')
            if p1snap is not None or p2snap is not None:
                snapinfo = p1snap if p1snap is not None else p2snap
                side_idx = snapinfo['side']
                ca = self.quad[side_idx]; cb = self.quad[(side_idx+1)%4]
                sv = (cb[0]-ca[0], cb[1]-ca[1])
                sv_len = math.hypot(sv[0], sv[1])
                if sv_len != 0:
                    ux, uy = sv[0]/sv_len, sv[1]/sv_len
                    move = dx*ux + dy*uy
                    ln['p1'] = (self.drag_line_initial['p1'][0] + ux*move, self.drag_line_initial['p1'][1] + uy*move)
                    ln['p2'] = (self.drag_line_initial['p2'][0] + ux*move, self.drag_line_initial['p2'][1] + uy*move)
                    ln['length_mm'] = px_to_mm(dist(ln['p1'], ln['p2']), self.effective_px_per_mm())
                    ang = math.degrees(math.atan2(ln['p2'][1]-ln['p1'][1], ln['p2'][0]-ln['p1'][0]))
                    if ang < 0: ang += 360
                    ln['angle_deg'] = ang
            else:
                ln['p1'] = (self.drag_line_initial['p1'][0] + dx, self.drag_line_initial['p1'][1] + dy)
                ln['p2'] = (self.drag_line_initial['p2'][0] + dx, self.drag_line_initial['p2'][1] + dy)
                ln['length_mm'] = px_to_mm(dist(ln['p1'], ln['p2']), self.effective_px_per_mm())
                ang = math.degrees(math.atan2(ln['p2'][1]-ln['p1'][1], ln['p2'][0]-ln['p1'][0]))
                if ang < 0: ang += 360
                ln['angle_deg'] = ang
            self.drag_line_initial['p1snap'] = self._point_snapped_to_side(ln['p1'])
            self.drag_line_initial['p2snap'] = self._point_snapped_to_side(ln['p2'])
            self.update()
            return

        if self.dragging_move_all and hasattr(self, 'drag_move_initial'):
            mouse0 = self.drag_move_initial['mouse0']
            dx = pos[0] - mouse0[0]; dy = pos[1] - mouse0[1]
            quad0 = self.drag_move_initial['quad0']
            self.quad = [(p[0] + dx, p[1] + dy) for p in quad0]
            lines0 = self.drag_move_initial['lines0']
            for ln_idx, ln0 in enumerate(lines0):
                self.user_lines[ln_idx]['p1'] = (ln0['p1'][0] + dx, ln0['p1'][1] + dy)
                self.user_lines[ln_idx]['p2'] = (ln0['p2'][0] + dx, ln0['p2'][1] + dy)
                self.user_lines[ln_idx]['length_mm'] = px_to_mm(dist(self.user_lines[ln_idx]['p1'], self.user_lines[ln_idx]['p2']), self.effective_px_per_mm())
            self.update()
            return

        if self._find_corner_index(pos) is not None:
            self.setCursor(QtCore.Qt.PointingHandCursor)
        elif self._find_side_index(pos) is not None:
            self.setCursor(QtCore.Qt.IBeamCursor)
        elif self._find_user_line_index(pos) is not None:
            self.setCursor(QtCore.Qt.OpenHandCursor)
        elif self._find_intersection_handle(pos) is not None:
            self.setCursor(QtCore.Qt.SizeAllCursor)
        elif self._point_in_quad(pos):
            self.setCursor(QtCore.Qt.SizeAllCursor)
        else:
            self.setCursor(QtCore.Qt.ArrowCursor)

    def mouseReleaseEvent(self, ev: QtGui.QMouseEvent):
        x = ev.position().x(); y = ev.position().y()
        pos = (x,y)

        if ev.button() == QtCore.Qt.RightButton and self.drawing_line:
            self.drawing_line = False
            p1 = self.temp_p1; p2 = self.temp_p2
            p1_snap, s1 = self._snap_to_any(p1)
            p2_snap, s2 = self._snap_to_any(p2)
            if s1: p1 = p1_snap
            if s2: p2 = p2_snap
            if self.show_grid:
                p1 = self._snap_to_grid(p1)
                p2 = self._snap_to_grid(p2)
            length_mm = px_to_mm(dist(p1,p2), self.effective_px_per_mm())
            ang = math.degrees(math.atan2(p2[1]-p1[1], p2[0]-p1[0]))
            if ang < 0: ang += 360
            entry = {'p1':p1, 'p2':p2, 'length_mm':length_mm, 'angle_deg':ang}
            self.user_lines.append(entry)
            self.temp_p1 = None; self.temp_p2 = None
            self.auto_adjust_scale_if_needed()
            self._recalc_user_lines()
            self.update()
            return

        if ev.button() == QtCore.Qt.MiddleButton:
            if self.dragging_line:
                self.dragging_line = False
                self.drag_line_idx = None
                self.drag_line_initial = None
                self.setCursor(QtCore.Qt.ArrowCursor)
                self._recalc_user_lines()
                self.update()
            if self.dragging_move_all:
                self.dragging_move_all = False
                self.drag_move_initial = None
                self.setCursor(QtCore.Qt.ArrowCursor)
                self.update()
            if self.dragging_handle:
                self.dragging_handle = False
                self.drag_handle_info = None
                self.setCursor(QtCore.Qt.ArrowCursor)
                self._recalc_user_lines()
                self.update()

    def _find_corner_index(self, pos):
        if not self.quad:
            return None
        for i,p in enumerate(self.quad):
            if dist(pos,p) <= self.corner_radius_px*HANDLE_DISPLAY_SCALE + 4:
                return i
        return None

    def _find_side_index(self, pos, return_t=False):
        if not self.quad:
            return (None, None) if return_t else None
        for i in range(4):
            a = self.quad[i]; b = self.quad[(i+1)%4]
            proj, t = project_point_segment(pos, a, b)
            d = dist(proj, pos)
            if d <= self.snap_tol_px:
                if return_t:
                    return i, t
                return i
        if return_t:
            return None, None
        return None

    def _snap_to_sides(self, p):
        if not self.quad:
            return p, False
        for i in range(4):
            a = self.quad[i]; b = self.quad[(i+1)%4]
            proj, t = project_point_segment(p, a, b)
            if dist(proj, p) <= self.snap_tol_px:
                return proj, True
        return p, False

    def _snap_to_lines(self, p):
        best = None; best_d = float('inf')
        for i, ln in enumerate(self.user_lines):
            proj, t = project_point_segment(p, ln['p1'], ln['p2'])
            d = dist(proj, p)
            if d <= self.snap_tol_px and d < best_d:
                best = proj; best_d = d
        if best is not None:
            return best, True
        return p, False

    def _snap_to_any(self, p):
        sp, ss = self._snap_to_sides(p)
        if ss:
            return sp, True
        lp, ls = self._snap_to_lines(p)
        if ls:
            return lp, True
        return p, False

    def _snap_to_grid(self, p):
        if not self.show_grid: return p
        step_px = self.grid_step_px
        if step_px <= 1: return p
        x = round(p[0]/step_px) * step_px
        y = round(p[1]/step_px) * step_px
        return (x,y)

    def _find_user_line_index(self, pos):
        for i, ln in enumerate(self.user_lines):
            proj, t = project_point_segment(pos, ln['p1'], ln['p2'])
            if dist(proj, pos) <= max(6, self.snap_tol_px/2):
                return i
        return None

    def _point_snapped_to_side(self, p):
        for si in range(4):
            a = self.quad[si]; b = self.quad[(si+1)%4]
            proj, t = project_point_segment(p, a, b)
            if dist(proj, p) <= self.snap_tol_px:
                return {'side': si, 't': t, 'point': proj}
        return None

    def _point_in_quad(self, p):
        if not self.quad:
            return False
        x,y = p
        inside = False
        for i in range(4):
            x1,y1 = self.quad[i]; x2,y2 = self.quad[(i+1)%4]
            if ((y1>y) != (y2>y)) and (x < (x2-x1)*(y-y1)/(y2-y1+1e-12)+x1):
                inside = not inside
        return inside

    def _find_intersection_handle(self, pos):
        for h in self.intersection_handles:
            if dist(pos, h['pt']) <= self.handle_radius_px + 3:
                return h
        for idx, ln in enumerate(self.user_lines):
            for si in range(4):
                ca = self.quad[si]; cb = self.quad[(si+1)%4]
                ok, pt, onA, onB = intersect_segments(ln['p1'], ln['p2'], ca, cb)
                if ok and pt is not None and onA and onB:
                    if dist(pos, pt) <= self.handle_radius_px + 3:
                        d1 = dist(pt, ln['p1']); d2 = dist(pt, ln['p2'])
                        which = 'p1' if d1 <= d2 else 'p2'
                        _, t = project_point_segment(pt, ca, cb)
                        return {'pt': pt, 'line_idx': idx, 'side': si, 'which': which, 't': t, 'kind': 'side'}
        for i in range(len(self.user_lines)):
            for j in range(i+1, len(self.user_lines)):
                a1 = self.user_lines[i]['p1']; a2 = self.user_lines[i]['p2']
                b1 = self.user_lines[j]['p1']; b2 = self.user_lines[j]['p2']
                ok, pt, onA, onB = intersect_segments(a1,a2,b1,b2)
                if ok and pt is not None and onA and onB:
                    if dist(pos, pt) <= self.handle_radius_px + 3:
                        d1 = dist(pt, a1); d2 = dist(pt, a2)
                        which_i = 'p1' if d1 <= d2 else 'p2'
                        d3 = dist(pt, b1); d4 = dist(pt, b2)
                        which_j = 'p1' if d3 <= d4 else 'p2'
                        return {'pt':pt, 'line_idx': i, 'kind': 'line', 'which': which_i, 'other_line_idx': j}
        return None

    def _project_point_to_perimeter(self, p):
        if not self.quad:
            return None, None, None
        best = None; best_d = float('inf'); best_info = (None, None)
        for si in range(4):
            a = self.quad[si]; b = self.quad[(si+1)%4]
            proj, t = project_point_segment(p, a, b)
            d = dist(proj, p)
            if d < best_d:
                best_d = d; best = proj; best_info = (si, t)
        if best is None:
            return None, None, None
        return best, best_info[0], best_info[1]

    def _edit_corner_angle(self, idx):
        prev, cur, nxt = self.quad[(idx+3)%4], self.quad[idx], self.quad[(idx+1)%4]
        ang = angle_signed(prev, cur, nxt)
        interior = 360 - ang if ang > 180 else ang

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Winkel an Ecke {idx+1}")
        layout = QtWidgets.QVBoxLayout(dlg)

        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.1, 179.9)
        spin.setDecimals(1)
        spin.setValue(interior)
        layout.addWidget(QtWidgets.QLabel("Winkel in Grad:"))
        layout.addWidget(spin)

        cb = QtWidgets.QCheckBox("Fixieren")
        cb.setChecked(self.fixed_corners[idx])
        layout.addWidget(cb)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        layout.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)

        if dlg.exec():
            val = round(spin.value())

            was_fixed = self.fixed_corners[idx]
            is_fixed = cb.isChecked()

            parent = self.parentWidget()
            show_status = getattr(parent, "show_status_message", None) if parent is not None else None

            if was_fixed and is_fixed:
                if callable(show_status):
                    show_status(f"Ecke {idx+1} ist fixiert und wurde nicht geaendert.", 3000)
            else:
                if was_fixed and not is_fixed:
                    self.fixed_corners[idx] = False
                    self.fixed_corner_values_deg[idx] = None

                self._apply_corner_angle_change(idx, val)
                self.angle_values[idx] = val

                self.fixed_corners[idx] = is_fixed
                if is_fixed:
                    self.fixed_corner_values_deg[idx] = val
                else:
                    self.fixed_corner_values_deg[idx] = None

                if was_fixed != is_fixed and callable(show_status):
                    msg = (f"Ecke {idx+1} fixiert ({self.format_angle(val)})"
                           if is_fixed else f"Ecke {idx+1} gelöst")
                    show_status(msg, 3000)

            self.update()

    def _edit_side_length(self, idx, t, pos):
        a, b = self.quad[idx], self.quad[(idx+1)%4]
        length_px = dist(a, b)
        length_mm = px_to_mm(length_px, self.effective_px_per_mm())
        length_cm = length_mm / 10.0

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Seite {idx+1}")
        layout = QtWidgets.QVBoxLayout(dlg)

        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.1, 9999.0)
        spin.setDecimals(1)
        spin.setValue(length_cm)
        layout.addWidget(QtWidgets.QLabel("Laenge in cm:"))
        layout.addWidget(spin)

        cb = QtWidgets.QCheckBox("Fixieren")
        cb.setChecked(self.fixed_sides[idx])
        layout.addWidget(cb)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        layout.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)

        if dlg.exec():
            val_cm = round(spin.value())
            val_mm = val_cm * 10.0

            was_fixed = self.fixed_sides[idx]
            is_fixed = cb.isChecked()

            parent = self.parentWidget()
            show_status = getattr(parent, "show_status_message", None) if parent is not None else None

            if was_fixed and is_fixed:
                if callable(show_status):
                    show_status(f"Seite {idx+1} ist fixiert und wurde nicht geaendert.", 3000)
                return

            if was_fixed and not is_fixed:
                self.fixed_sides[idx] = False
                self.fixed_side_values_mm[idx] = None
                self.fixed_side_values_px[idx] = None

            # Änderung durchführen
            self._apply_side_length_change(idx, val_mm)
            self.side_lengths[idx] = val_mm
            current_len_px = dist(self.quad[idx], self.quad[(idx+1)%4])

            # Fixstatus übernehmen
            self.fixed_sides[idx] = is_fixed

            if is_fixed:
                self.fixed_side_values_mm[idx] = val_mm
                self.fixed_side_values_px[idx] = current_len_px
            else:
                self.fixed_side_values_mm[idx] = None
                self.fixed_side_values_px[idx] = None

            if was_fixed != is_fixed and callable(show_status):
                msg = (f"Seite {idx+1} fixiert ({self.format_length_mm(val_mm)})"
                       if is_fixed else f"Seite {idx+1} gelöst")
                show_status(msg, 3000)

            self.solve_constraints()

    def _make_quad_consistent_after_side_change(self, side_idx):
        if not self.quad:
            return

        # Mittelpunkt vor Änderung (Referenz)
        cx_ref = sum(p[0] for p in self.quad) / 4.0
        cy_ref = sum(p[1] for p in self.quad) / 4.0

        cx_now = sum(p[0] for p in self.quad) / 4.0
        cy_now = sum(p[1] for p in self.quad) / 4.0

        dx = cx_ref - cx_now
        dy = cy_ref - cy_now

        # Nur verschieben, wenn die Seite nicht fixiert ist
        for i in range(4):
            if self.fixed_sides[i]:
                continue
            self.quad[i] = (self.quad[i][0] + dx, self.quad[i][1] + dy)

    def _make_quad_consistent_after_corner_change(self, corner_idx):
        if not self.quad:
            return

        # Mittelpunkt vor Änderung (Referenz)
        cx_ref = sum(p[0] for p in self.quad) / 4.0
        cy_ref = sum(p[1] for p in self.quad) / 4.0

        cx_now = sum(p[0] for p in self.quad) / 4.0
        cy_now = sum(p[1] for p in self.quad) / 4.0

        dx = cx_ref - cx_now
        dy = cy_ref - cy_now

        # Nur verschieben, wenn die Ecke nicht fixiert ist
        for i in range(4):
            if self.fixed_corners[i]:
                continue
            self.quad[i] = (self.quad[i][0] + dx, self.quad[i][1] + dy)

    def _recalc_user_lines(self):
        quad_sig = None
        if self.quad:
            quad_sig = tuple((round(p[0], 3), round(p[1], 3)) for p in self.quad)
        line_sig = tuple(
            (round(ln['p1'][0], 3), round(ln['p1'][1], 3),
             round(ln['p2'][0], 3), round(ln['p2'][1], 3))
            for ln in self.user_lines
        )
        signature = (round(self.effective_px_per_mm(), 6), quad_sig, line_sig)
        if signature == self._last_user_lines_signature:
            return
        self._last_user_lines_signature = signature

        for ln in self.user_lines:
            ln['length_mm'] = px_to_mm(dist(ln['p1'], ln['p2']), self.effective_px_per_mm())
            ang = math.degrees(math.atan2(ln['p2'][1]-ln['p1'][1], ln['p2'][0]-ln['p1'][0]))
            if ang < 0: ang += 360
            ln['angle_deg'] = ang
        handles = []
        for idx, ln in enumerate(self.user_lines):
            for si in range(4):
                ca = self.quad[si]; cb = self.quad[(si+1)%4]
                ok, pt, onA, onB = intersect_segments(ln['p1'], ln['p2'], ca, cb)
                if ok and pt is not None and onA and onB:
                    d1 = dist(pt, ln['p1']); d2 = dist(pt, ln['p2'])
                    which = 'p1' if d1 <= d2 else 'p2'
                    _, t = project_point_segment(pt, ca, cb)
                    handles.append({'pt':pt, 'line_idx': idx, 'side': si, 'which': which, 't': t, 'kind': 'side'})
        seen_pairs = set()
        for i in range(len(self.user_lines)):
            for j in range(i+1, len(self.user_lines)):
                a1 = self.user_lines[i]['p1']; a2 = self.user_lines[i]['p2']
                b1 = self.user_lines[j]['p1']; b2 = self.user_lines[j]['p2']
                ok, pt, onA, onB = intersect_segments(a1,a2,b1,b2)
                if ok and pt is not None and onA and onB:
                    pair = (i,j)
                    if pair in seen_pairs: continue
                    seen_pairs.add(pair)
                    d1 = dist(pt, a1); d2 = dist(pt, a2)
                    which_i = 'p1' if d1 <= d2 else 'p2'
                    d3 = dist(pt, b1); d4 = dist(pt, b2)
                    which_j = 'p1' if d3 <= d4 else 'p2'
                    handles.append({'pt':pt, 'line_idx': i, 'kind': 'line', 'which': which_i, 'other_line_idx': j})
                    handles.append({'pt':pt, 'line_idx': j, 'kind': 'line', 'which': which_j, 'other_line_idx': i})
        uniq = []
        for h in handles:
            key = (round(h['pt'][0],2), round(h['pt'][1],2), h.get('kind'))
            if not any((round(x['pt'][0],2), round(x['pt'][1],2), x.get('kind')) == key for x in uniq):
                uniq.append(h)
        self.intersection_handles = uniq

    def auto_adjust_scale_if_needed(self, enforce_constraints: bool = True):
        if not self.quad:
            return False
        margin_px = mm_to_px(MARGIN_MM, self.effective_px_per_mm())
        left = min(p[0] for p in self.quad)
        right = max(p[0] for p in self.quad)
        top = min(p[1] for p in self.quad)
        bottom = max(p[1] for p in self.quad)
        w = self.width(); h = self.height()
        need_fit = (left < margin_px or top < margin_px or right > w - margin_px or bottom > h - margin_px)
        if not need_fit:
            return False
        quad_w = right - left; quad_h = bottom - top
        if quad_w <= 0 or quad_h <= 0:
            return False
        avail_w = max(10, w - 2*margin_px)
        avail_h = max(10, h - 2*margin_px)
        sx = avail_w / quad_w; sy = avail_h / quad_h
        s = min(sx, sy) * 0.95
        cx = (left + right)/2; cy = (top + bottom)/2
        new_quad = []
        for p in self.quad:
            nx = cx + (p[0]-cx)*s
            ny = cy + (p[1]-cy)*s
            new_quad.append((nx, ny))
        for ln in self.user_lines:
            ln['p1'] = (cx + (ln['p1'][0]-cx)*s, cy + (ln['p1'][1]-cy)*s)
            ln['p2'] = (cx + (ln['p2'][0]-cx)*s, cy + (ln['p2'][1]-cy)*s)
        self.quad = new_quad
        self.scale *= s
        self.scale = clamp(self.scale, MIN_SCALE, MAX_SCALE)
        self.update_scale_dependent_metrics()
        self._last_user_lines_signature = None
        self._recalc_user_lines()
        if (enforce_constraints and self.has_active_constraints()
                and not self._is_solving_constraints):
            self.solve_constraints()
        return True

    def scale_about_center(self, factor, enforce_constraints: bool = True):
        if factor <= 0:
            return
        w = self.width(); h = self.height()
        cx, cy = w/2.0, h/2.0
        new_quad = []
        for p in self.quad:
            nx = cx + (p[0]-cx) * factor
            ny = cy + (p[1]-cy) * factor
            new_quad.append((nx, ny))
        self.quad = new_quad
        for ln in self.user_lines:
            ln['p1'] = (cx + (ln['p1'][0]-cx) * factor, cy + (ln['p1'][1]-cy) * factor)
            ln['p2'] = (cx + (ln['p2'][0]-cx) * factor, cy + (ln['p2'][1]-cy) * factor)
        self.scale *= factor
        self.scale = clamp(self.scale, MIN_SCALE, MAX_SCALE)
        self.update_scale_dependent_metrics()
        self._last_user_lines_signature = None
        self._recalc_user_lines()
        if (enforce_constraints and self.has_active_constraints()
                and not self._is_solving_constraints):
            self.solve_constraints()
        self.update()

    def reset(self):
        self.init_quad_default()
        self.user_lines = []
        self.intersection_handles = []
        self._last_user_lines_signature = None
        self.update_scale_dependent_metrics()
        self.update()

    def pan_view(self, dx_px, dy_px):
        if not self.quad: return
        self.quad = [(p[0]+dx_px, p[1]+dy_px) for p in self.quad]
        for ln in self.user_lines:
            ln['p1'] = (ln['p1'][0]+dx_px, ln['p1'][1]+dy_px)
            ln['p2'] = (ln['p2'][0]+dx_px, ln['p2'][1]+dy_px)
        self.update()

    def _make_point_string(self, p): 
        return f"({int(round(p[0]))}, {int(round(p[1]))})"

    def toggle_fix_side(self):
        idx = self.last_side_idx
        if idx is None:
            QtWidgets.QMessageBox.information(self, "Seite fixieren", "Keine Seite ausgewaehlt. Klicke zuerst auf eine Seite (Linksklick).")
            return
        parent = self.parentWidget()
        show_status = getattr(parent, "show_status_message", None) if parent is not None else None
        if not self.fixed_sides[idx]:
            a = self.quad[idx]
            b = self.quad[(idx + 1) % 4]
            length_mm = px_to_mm(dist(a, b), self.effective_px_per_mm())
            length_mm = round(length_mm)
            self.fixed_side_values_mm[idx] = length_mm
            self.fixed_side_values_px[idx] = dist(a, b)
            self.fixed_sides[idx] = True
            if callable(show_status):
                show_status(f"Seite {idx + 1} fixiert ({self.format_length_mm(length_mm)})", 4000)
        else:
            self.fixed_sides[idx] = False
            self.fixed_side_values_mm[idx] = None
            self.fixed_side_values_px[idx] = None
            if callable(show_status):
                show_status(f"Seite {idx + 1} gelöst", 3000)
        self.solve_constraints()

    def toggle_fix_corner(self):
        idx = self.last_corner_idx
        if idx is None:
            QtWidgets.QMessageBox.information(self, "Ecke fixieren", "Keine Ecke ausgewaehlt. Klicke zuerst auf eine Ecke (Linksklick).")
            return
        parent = self.parentWidget()
        show_status = getattr(parent, "show_status_message", None) if parent is not None else None
        if not self.fixed_corners[idx]:
            prev = self.quad[(idx + 3) % 4]
            cur = self.quad[idx]
            nxt = self.quad[(idx + 1) % 4]
            ang = angle_signed(prev, cur, nxt)
            interior = 360 - ang if ang > 180 else ang
            interior = round(interior)
            self.fixed_corner_values_deg[idx] = interior
            self.fixed_corners[idx] = True
            if callable(show_status):
                show_status(f"Ecke {idx + 1} fixiert ({self.format_angle(interior)})", 4000)
        else:
            self.fixed_corners[idx] = False
            self.fixed_corner_values_deg[idx] = None
            if callable(show_status):
                show_status(f"Ecke {idx + 1} gelöst", 3000)
        self.solve_constraints()

    def toggle_debug_overlay(self, state: bool | None = None):
        if state is None:
            self.show_debug_overlay = not self.show_debug_overlay
        else:
            self.show_debug_overlay = bool(state)
        self.settings.setValue("debug_overlay", self.show_debug_overlay)
        parent = self.parentWidget()
        show_status = getattr(parent, "show_status_message", None) if parent is not None else None
        if callable(show_status):
            msg = "Debug-Overlay aktiviert" if self.show_debug_overlay else "Debug-Overlay deaktiviert"
            show_status(msg, 2500)
        self.update()

    def _apply_side_length_change(self, idx, new_len_mm):
        if self.fixed_sides[idx]:
            return
        a, b = self.quad[idx], self.quad[(idx + 1) % 4]
        vec = (b[0] - a[0], b[1] - a[1])
        old_len = math.hypot(*vec)
        if old_len == 0:
            return
        scale = (new_len_mm * self.px_per_mm) / old_len
        b_new = (a[0] + vec[0] * scale, a[1] + vec[1] * scale)
        self.quad[(idx + 1) % 4] = b_new
        self.solve_constraints()

    def _apply_corner_angle_change(self, idx, new_angle_deg):
        if self.fixed_corners[idx]:
            return
        prev = self.quad[(idx + 3) % 4]
        cur = self.quad[idx]
        nxt = self.quad[(idx + 1) % 4]
        v_prev = (prev[0] - cur[0], prev[1] - cur[1])
        v_next = (nxt[0] - cur[0], nxt[1] - cur[1])
        len_prev = math.hypot(*v_prev)
        len_next = math.hypot(*v_next)
        if len_prev == 0 or len_next == 0:
            return
        current_signed = angle_signed(prev, cur, nxt)
        current_interior = 360 - current_signed if current_signed > 180 else current_signed
        delta = math.radians(new_angle_deg - current_interior)
        sign = -1.0 if current_signed > 180 else 1.0
        cosd = math.cos(sign * delta)
        sind = math.sin(sign * delta)
        rx = v_next[0] * cosd - v_next[1] * sind
        ry = v_next[0] * sind + v_next[1] * cosd
        new_nxt = (cur[0] + rx, cur[1] + ry)
        self.quad[(idx + 1) % 4] = new_nxt
        self.solve_constraints()
        self._realign_to_initial_position()

    def _interior_angle(self, a, b, c):
        v1 = (a[0] - b[0], a[1] - b[1])
        v2 = (c[0] - b[0], c[1] - b[1])
        n1 = math.hypot(*v1)
        n2 = math.hypot(*v2)
        if n1 == 0 or n2 == 0:
            return 0.0
        dotv = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
        return math.degrees(math.acos(dotv))

    def _rotate_point(self, pivot, p, angle_rad):
        dx, dy = p[0] - pivot[0], p[1] - pivot[1]
        ca, sa = math.cos(angle_rad), math.sin(angle_rad)
        return (pivot[0] + ca * dx - sa * dy, pivot[1] + sa * dx + ca * dy)

    def _align_quad_order(self, new_quad):
        """Return a reordered copy of new_quad whose vertices match the previous numbering."""
        if not self.quad or len(self.quad) != 4 or len(new_quad) != 4:
            return list(new_quad)
        ordered = []
        used = set()
        for prev in self.quad:
            best_idx = None
            best_dist = float('inf')
            for idx, pt in enumerate(new_quad):
                if idx in used:
                    continue
                d = dist(prev, pt)
                if d < best_dist:
                    best_dist = d
                    best_idx = idx
            if best_idx is None:
                return list(new_quad)
            ordered.append(new_quad[best_idx])
            used.add(best_idx)
        return ordered if len(ordered) == 4 else list(new_quad)

    def solve_constraints(self):
        if not self.quad or self._is_solving_constraints:
            return
        self._is_solving_constraints = True
        try:
            self._solve_constraints_impl()
        finally:
            self._is_solving_constraints = False

    def reconstruct_from_constraints(self):
        if self._in_reconstruct:
            return
        self._in_reconstruct = True
        try:
            prev_quad_state = [tuple(p) for p in self.quad] if self.quad else None
            prev_initial_state = [tuple(p) for p in self.initial_quad] if self.initial_quad else None
            prev_side_px = list(self.fixed_side_values_px)
            px_per_mm = self.effective_px_per_mm()
            if px_per_mm <= 0:
                return
            side_values_mm = [self.fixed_side_values_mm[i] if self.fixed_sides[i] and self.fixed_side_values_mm[i] is not None else None for i in range(4)]
            angle_values = [self.fixed_corner_values_deg[i] if self.fixed_corners[i] and self.fixed_corner_values_deg[i] is not None else None for i in range(4)]

            # --- Nur nicht fixierte Winkel berechnen, fixierte unverändert lassen ---
            missing_angles = [i for i, val in enumerate(angle_values) if val is None]
            known_sum = sum(val for val in angle_values if val is not None)
            remaining = 360.0 - known_sum

            # Verteile den Rest gleichmäßig auf unfixierte Winkel
            if missing_angles:
                avg_rest = max(1.0, remaining / len(missing_angles))
                for idx in missing_angles:
                    angle_values[idx] = round(avg_rest)
            else:
                # Falls alle Winkel gesetzt, einfach ganzzahlig runden
                angle_values = [round(a) for a in angle_values]

            headings = [0.0]
            for i in range(3):
                headings.append(headings[-1] + (180.0 - angle_values[i]))
            dirs = [(math.cos(math.radians(h)), math.sin(math.radians(h))) for h in headings[:4]]

            lengths = side_values_mm[:]
            unknown_idx = [i for i, val in enumerate(lengths) if val is None]
            if len(unknown_idx) == 1:
                k = unknown_idx[0]
                sx = -sum((lengths[i] or 0.0) * dirs[i][0] for i in range(4))
                sy = -sum((lengths[i] or 0.0) * dirs[i][1] for i in range(4))
                dx, dy = dirs[k]
                denom = dx * dx + dy * dy
                if denom > 1e-9:
                    lengths[k] = (sx * dx + sy * dy) / denom
            elif len(unknown_idx) == 2:
                i1, i2 = unknown_idx
                sx = -sum((lengths[i] or 0.0) * dirs[i][0] for i in range(4))
                sy = -sum((lengths[i] or 0.0) * dirs[i][1] for i in range(4))
                a11, a12 = dirs[i1][0], dirs[i2][0]
                a21, a22 = dirs[i1][1], dirs[i2][1]
                det = a11 * a22 - a12 * a21
                if abs(det) > 1e-9:
                    L1 = (sx * a22 - a12 * sy) / det
                    L2 = (-sx * a21 + a11 * sy) / det
                    lengths[i1], lengths[i2] = L1, L2

            for i in range(4):
                val = lengths[i]
                if val is None or val <= 0:
                    fallback = self.fixed_side_values_mm[i] if self.fixed_side_values_mm[i] is not None else DEFAULT_SIDE_MM
                    val = fallback
                lengths[i] = round(max(0.1, float(val)), 0)

            pts = [(0.0, 0.0)]
            for i in range(4):
                dx = lengths[i] * dirs[i][0] * px_per_mm
                dy = lengths[i] * dirs[i][1] * px_per_mm
                x, y = pts[-1]
                pts.append((x + dx, y + dy))
            quad = pts[:4]

            closure_vec = (pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
            closure_err = math.hypot(*closure_vec)
            closure_tol_px = mm_to_px(0.25, px_per_mm)
            if closure_err > closure_tol_px:
                quad[3] = (quad[3][0] - closure_vec[0], quad[3][1] - closure_vec[1])
                closure_mm = px_to_mm(closure_err, px_per_mm)
                parent = self.parentWidget()
                show_status = getattr(parent, "show_status_message", None) if parent is not None else None
                if callable(show_status):  # add this
                    show_status(f"Rekonstruktion korrigiert (Abweichung {int(round(closure_mm))} mm)", 6000)


            cx_widget = self.width() / 2.0
            cy_widget = self.height() / 2.0
            min_x = min(p[0] for p in quad)
            max_x = max(p[0] for p in quad)
            min_y = min(p[1] for p in quad)
            max_y = max(p[1] for p in quad)
            quad = [(p[0] + (cx_widget - (min_x + max_x) / 2.0),
                     p[1] + (cy_widget - (min_y + max_y) / 2.0)) for p in quad]

            quad = self._align_quad_order(quad)
            self.quad = [tuple(p) for p in quad]
            self.initial_quad = [tuple(p) for p in self.quad]
            for i in range(4):
                a = self.quad[i]
                b = self.quad[(i + 1) % 4]
                if self.fixed_sides[i]:
                    self.fixed_side_values_px[i] = dist(a, b)
                else:
                    self.fixed_side_values_px[i] = None
            self._last_user_lines_signature = None
            self._recalc_user_lines()
            self.auto_adjust_scale_if_needed(enforce_constraints=False)
            if not self._validate_constraint_accuracy() and prev_quad_state is not None:
                self.quad = prev_quad_state
                self.initial_quad = prev_initial_state
                self.fixed_side_values_px = prev_side_px
                self._last_user_lines_signature = None
                self._recalc_user_lines()
                self.update()
                return
            self.update()
        finally:
            self._in_reconstruct = False

    def _notify_solver_issue(self, side_error_mm: float, angle_error_deg: float):
        msg = ("Fixierungen konnten nicht exakt gelöst werden "
                f"(Seitenfehler {int(round(side_error_mm))} mm, "
                f"Winkelfehler {int(round(angle_error_deg))} Grad).")
        parent = self.parentWidget()
        show_status = getattr(parent, "show_status_message", None) if parent is not None else None
        if callable(show_status):
            show_status(msg, 6000)
        QtWidgets.QMessageBox.warning(self, "Fixierungen inkonsistent", msg)

    def _validate_constraint_accuracy(self, len_tol_mm: float = 0.001, angle_tol_deg: float = 0.01) -> bool:
        """Return True if current quad respects all fixed constraints within tolerance."""
        if not self.quad:
            return True
        px_per_mm = self.effective_px_per_mm()
        worst_len = 0.0
        worst_ang = 0.0
        for i in range(4):
            if self.fixed_sides[i] and self.fixed_side_values_mm[i] is not None:
                actual_len_mm = px_to_mm(dist(self.quad[i], self.quad[(i + 1) % 4]), px_per_mm)
                worst_len = max(worst_len, abs(actual_len_mm - self.fixed_side_values_mm[i]))
            if self.fixed_corners[i] and self.fixed_corner_values_deg[i] is not None:
                prev = self.quad[(i - 1) % 4]
                cur = self.quad[i]
                nxt = self.quad[(i + 1) % 4]
                actual_ang = self._interior_angle(prev, cur, nxt)
                worst_ang = max(worst_ang, abs(actual_ang - self.fixed_corner_values_deg[i]))
        if worst_len > len_tol_mm or worst_ang > angle_tol_deg:
            self._notify_solver_issue(worst_len, worst_ang)
            return False
        return True

    def _solve_constraints_impl(self):
        fixed_side_flags = [self.fixed_sides[i] and self.fixed_side_values_mm[i] is not None for i in range(4)]
        fixed_corner_flags = [self.fixed_corners[i] and self.fixed_corner_values_deg[i] is not None for i in range(4)]
        n_fixed_sides = sum(fixed_side_flags)
        n_fixed_corners = sum(fixed_corner_flags)
        total_constraints = n_fixed_sides + n_fixed_corners

        prev_quad_state = [tuple(p) for p in self.quad] if self.quad else None
        prev_initial_state = [tuple(p) for p in self.initial_quad] if self.initial_quad else None
        prev_side_px = list(self.fixed_side_values_px)

        if total_constraints >= 4:
            self.reconstruct_from_constraints()
            return

        quad = [list(p) for p in self.quad]
        px_per_mm = self.effective_px_per_mm()

        fixed_angles = [self.fixed_corner_values_deg[i] if fixed_corner_flags[i] else None for i in range(4)]
        if sum(val is not None for val in fixed_angles) == 3:
            missing_idx = [i for i, val in enumerate(fixed_angles) if val is None][0]
            total = sum(val for val in fixed_angles if val is not None)
            target = max(1.0, min(179.0, 360.0 - total))
            self.fixed_corners[missing_idx] = True
            self.fixed_corner_values_deg[missing_idx] = target
            fixed_corner_flags[missing_idx] = True

        def edge_length(a, b):
            return math.hypot(b[0] - a[0], b[1] - a[1])

        vertex_locked = [False] * 4
        for v in range(4):
            if fixed_corner_flags[v]:
                vertex_locked[v] = True
        for v in range(4):
            if fixed_side_flags[v] and fixed_side_flags[(v - 1) % 4]:
                vertex_locked[v] = True

        stalled = False
        for _ in range(400):
            changed = False
            total_move = 0.0

            for i in range(4):
                if not fixed_side_flags[i]:
                    continue
                cur = quad[i]
                nxt = quad[(i + 1) % 4]
                target_len_px = mm_to_px(self.fixed_side_values_mm[i], px_per_mm)
                cur_len = edge_length(cur, nxt)
                if cur_len < 1e-9:
                    continue
                err = target_len_px - cur_len
                if px_to_mm(abs(err), px_per_mm) < 0.01:
                    continue

                step_ratio = max(0.05, min(0.35, abs(err) / max(1.0, target_len_px)))
                ratio = 1.0 + step_ratio * (1 if err > 0 else -1)

                if not vertex_locked[i] and not vertex_locked[(i + 1) % 4]:
                    midx = (cur[0] + nxt[0]) * 0.5
                    midy = (cur[1] + nxt[1]) * 0.5
                    ux = (nxt[0] - cur[0]) / cur_len
                    uy = (nxt[1] - cur[1]) / cur_len
                    half = 0.5 * cur_len * ratio
                    new_cur = (midx - ux * half, midy - uy * half)
                    new_nxt = (midx + ux * half, midy + uy * half)
                    total_move += dist(cur, new_cur) + dist(nxt, new_nxt)
                    quad[i] = list(new_cur)
                    quad[(i + 1) % 4] = list(new_nxt)
                    changed = True
                elif not vertex_locked[(i + 1) % 4]:
                    new_nxt = (cur[0] + (nxt[0] - cur[0]) * ratio, cur[1] + (nxt[1] - cur[1]) * ratio)
                    total_move += dist(nxt, new_nxt)
                    quad[(i + 1) % 4] = list(new_nxt)
                    changed = True
                elif not vertex_locked[i]:
                    new_cur = (nxt[0] + (cur[0] - nxt[0]) * ratio, nxt[1] + (cur[1] - nxt[1]) * ratio)
                    total_move += dist(cur, new_cur)
                    quad[i] = list(new_cur)
                    changed = True

            for i in range(4):
                if not fixed_corner_flags[i]:
                    continue

                prev = quad[(i - 1) % 4]
                cur = quad[i]
                nxt = quad[(i + 1) % 4]

                cur_ang = self._interior_angle(prev, cur, nxt)
                target = max(1.0, min(179.0, self.fixed_corner_values_deg[i]))
                err_deg = target - cur_ang
                if abs(err_deg) < 0.01:
                    continue

                step = math.radians(max(0.2, min(5.0, abs(err_deg) * 0.25)))

                candidates = []
                if not vertex_locked[(i + 1) % 4]:
                    candidates.append(((i + 1) % 4, self._rotate_point(cur, nxt, step)))
                    candidates.append(((i + 1) % 4, self._rotate_point(cur, nxt, -step)))
                if not vertex_locked[(i - 1) % 4]:
                    candidates.append(((i - 1) % 4, self._rotate_point(cur, prev, -step)))
                    candidates.append(((i - 1) % 4, self._rotate_point(cur, prev, step)))

                if not candidates:
                    continue

                best_err = float('inf')
                best_apply = None
                for idx_move, new_pt in candidates:
                    test = [list(p) for p in quad]
                    test[idx_move] = list(new_pt)
                    a = test[(i - 1) % 4]
                    b = test[i]
                    c = test[(i + 1) % 4]
                    new_ang = self._interior_angle(a, b, c)
                    e = abs(target - new_ang)
                    if e < best_err:
                        best_err = e
                        best_apply = (idx_move, new_pt)

                if best_apply:
                    idx_move, new_pt = best_apply
                    total_move += dist(quad[idx_move], new_pt)
                    quad[idx_move] = list(new_pt)
                    changed = True

            if not changed or total_move < 0.03:
                stalled = True
                break

        side_error_mm = 0.0
        angle_error_deg = 0.0
        for i in range(4):
            if fixed_side_flags[i]:
                cur_len_mm = px_to_mm(edge_length(quad[i], quad[(i + 1) % 4]), px_per_mm)
                err_mm = abs(cur_len_mm - self.fixed_side_values_mm[i])
                side_error_mm = max(side_error_mm, err_mm)
            if fixed_corner_flags[i]:
                prev = quad[(i - 1) % 4]
                cur = quad[i]
                nxt = quad[(i + 1) % 4]
                cur_ang = self._interior_angle(prev, cur, nxt)
                err_deg = abs(cur_ang - self.fixed_corner_values_deg[i])
                angle_error_deg = max(angle_error_deg, err_deg)

        if stalled and (side_error_mm > 0.05 or angle_error_deg > 0.1):
            if total_constraints >= 4:
                self.reconstruct_from_constraints()
            else:
                self._notify_solver_issue(side_error_mm, angle_error_deg)
            return

        if self.initial_quad:
            quad = self._restore_initial_orientation(quad)
            cx_ref = sum(p[0] for p in self.initial_quad) / 4.0
            cy_ref = sum(p[1] for p in self.initial_quad) / 4.0
            cx = sum(p[0] for p in quad) / 4.0
            cy = sum(p[1] for p in quad) / 4.0
            dx, dy = cx_ref - cx, cy_ref - cy
            quad = [[p[0] + dx, p[1] + dy] for p in quad]

        ordered_quad = self._align_quad_order([tuple(p) for p in quad])
        self.quad = [tuple(p) for p in ordered_quad]
        for i in range(4):
            a = self.quad[i]
            b = self.quad[(i + 1) % 4]
            if self.fixed_sides[i]:
                self.fixed_side_values_px[i] = dist(a, b)
            else:
                self.fixed_side_values_px[i] = None

        self._last_user_lines_signature = None
        self._recalc_user_lines()
        if not self._validate_constraint_accuracy() and prev_quad_state is not None:
            self.quad = prev_quad_state
            self.initial_quad = prev_initial_state
            self.fixed_side_values_px = prev_side_px
            self._last_user_lines_signature = None
            self._recalc_user_lines()
            return
        self.update()
    def _restore_initial_orientation(self, quad):
        if not self.initial_quad or len(quad) != 4:
            return quad
        ref_vec = (self.initial_quad[1][0] - self.initial_quad[0][0],
                   self.initial_quad[1][1] - self.initial_quad[0][1])
        cur_vec = (quad[1][0] - quad[0][0], quad[1][1] - quad[0][1])
        ref_len = math.hypot(*ref_vec)
        cur_len = math.hypot(*cur_vec)
        if ref_len < 1e-9 or cur_len < 1e-9:
            return quad
        ref_angle = math.atan2(ref_vec[1], ref_vec[0])
        cur_angle = math.atan2(cur_vec[1], cur_vec[0])
        delta = cur_angle - ref_angle
        if abs(delta) < 1e-6:
            return quad
        cosd = math.cos(-delta)
        sind = math.sin(-delta)
        cx = sum(p[0] for p in quad) / 4.0
        cy = sum(p[1] for p in quad) / 4.0
        rotated = []
        for x, y in quad:
            dx = x - cx
            dy = y - cy
            rx = cosd * dx - sind * dy
            ry = sind * dx + cosd * dy
            rotated.append([cx + rx, cy + ry])
        return rotated

    def _realign_quad_center(self):
        # Nach jeder Änderung das Viereck zentriert halten.
        if not self.quad:
            return
        cx_ref = self.width()/2
        cy_ref = self.height()/2
        cx = sum(p[0] for p in self.quad)/4
        cy = sum(p[1] for p in self.quad)/4
        dx, dy = cx_ref - cx, cy_ref - cy
        self.quad = [(p[0]+dx, p[1]+dy) for p in self.quad]
        self._recalc_user_lines()

    def _realign_to_initial_position(self):
        # Nach jeder numerischen Änderung das Viereck an ursprünglicher Lage ausrichten.
        if not self.initial_quad:
            self.initial_quad = list(self.quad)
            return
        cx_ref = sum(p[0] for p in self.initial_quad)/4
        cy_ref = sum(p[1] for p in self.initial_quad)/4
        cx_now = sum(p[0] for p in self.quad)/4
        cy_now = sum(p[1] for p in self.quad)/4
        dx, dy = cx_ref - cx_now, cy_ref - cy_now
        self.quad = [(p[0]+dx, p[1]+dy) for p in self.quad]
        self._recalc_user_lines()
        self.update()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        icon_path = r"C:\Users\clanm\Desktop\Zuhause\Programme\Für Papa\Zeichner.png"
        if os.path.exists(icon_path):
            try:
                self.setWindowIcon(QtGui.QIcon(icon_path))
            except Exception:
                pass

        self.setWindowTitle("Viereck CAD")
        self.canvas = CADCanvas(self)
        self.setCentralWidget(self.canvas)
        self._create_toolbar()
        self.show_status_message("Rechtsklick + Ziehen: Linie zeichnen | Links: Ecken/Seiten editieren | Mitte: Ziehen/Bewegen", 6000)

        version_label = QtWidgets.QLabel(f"Version: {APP_VERSION}")
        version_label.setAlignment(QtCore.Qt.AlignCenter)
        version_label.setStyleSheet("color: gray; font-weight: bold;")
        self.statusBar().addPermanentWidget(version_label, 1)

        QtCore.QTimer.singleShot(0, self._go_fullscreen)
        self.show()
        QtCore.QTimer.singleShot(2000, lambda: check_for_updates_threaded(self))

    def _go_fullscreen(self):
        try:
            self.showFullScreen()
        except Exception:
            pass

    def _create_toolbar(self):
        tb = self.addToolBar("Werkzeuge")
        tb.setMovable(False)
        tb.setIconSize(QtCore.QSize(28, 28))
        tb.setStyleSheet("QToolBar { spacing: 8px; } QToolButton { font-size: 12pt; padding: 6px; }")

        act_reset = QtGui.QAction("Zurücksetzen", self)
        act_reset.setToolTip("Viereck und gezeichnete Linien zurücksetzen")
        act_reset.triggered.connect(self._reset_clicked)
        tb.addAction(act_reset)

        act_zoom_in = QtGui.QAction("Vergrößern", self)
        act_zoom_in.triggered.connect(lambda: self._zoom(1.2))
        tb.addAction(act_zoom_in)

        act_zoom_out = QtGui.QAction("Verkleinern", self)
        act_zoom_out.triggered.connect(lambda: self._zoom(1/1.2))
        tb.addAction(act_zoom_out)

        tb.addSeparator()

        unit_menu = QtWidgets.QComboBox(self)
        unit_menu.addItems(['mm', 'cm', 'm'])
        unit_menu.setCurrentText('cm')
        unit_menu.activated.connect(self._unit_changed)
        tb.addWidget(unit_menu)

        act_grid = QtGui.QAction("Raster", self)
        act_grid.setCheckable(True)
        act_grid.setChecked(self.canvas.show_grid)
        act_grid.toggled.connect(self._toggle_grid)
        tb.addAction(act_grid)

        act_debug = QtGui.QAction("Debug", self)
        act_debug.setCheckable(True)
        act_debug.setChecked(self.canvas.show_debug_overlay)
        act_debug.toggled.connect(self._toggle_debug_overlay)
        tb.addAction(act_debug)

        act_screenshot = QtGui.QAction("Screenshot", self)
        act_screenshot.triggered.connect(self._screenshot)
        tb.addAction(act_screenshot)

        act_help = QtGui.QAction("Hilfe", self)
        act_help.triggered.connect(self._show_help)
        tb.addAction(act_help)

        act_close = QtGui.QAction("Schließen", self)
        act_close.triggered.connect(self.close)
        tb.addAction(act_close)

    def show_status_message(self, text: str, timeout: int = 3000):
        self.statusBar().showMessage(text, timeout)

    def _reset_clicked(self):
        self.canvas.reset()
        self.show_status_message("Zurückgesetzt", 3000)

    def _zoom(self, factor):
        self.canvas.scale_about_center(factor)

    def _unit_changed(self, idx):
        cb = self.sender()
        if isinstance(cb, QtWidgets.QComboBox):
            unit = cb.currentText()
            self.canvas.set_unit(unit)

    def _toggle_grid(self, checked):
        self.canvas.show_grid = checked
        self.canvas.update()
        self.show_status_message("Raster an" if checked else "Raster aus", 2000)

    def _toggle_debug_overlay(self, checked):
        self.canvas.toggle_debug_overlay(checked)

    def _toggle_fix_side(self):
        self.canvas.toggle_fix_side()

    def _toggle_fix_corner(self):
        self.canvas.toggle_fix_corner()

    def _screenshot(self):
        pix = self.canvas.grab()
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        fname = os.path.join(desktop, f"screenshot_{QtCore.QDateTime.currentDateTime().toString('yyyy-MM-dd_hh-mm-ss')}.png")
        pix.save(fname, "PNG")
        self.show_status_message(f"Screenshot gespeichert: {fname}", 5000)

    def _show_help(self):
        text = (
            "Kurzbedienung:<br>"
            "- Rechtsklick + Ziehen: neue Linie zeichnen <br>"
            "   (Snap an Seiten / Linien / Raster).<br>"
            "- Mittel-Taste (Klick + Ziehen): Ganze Figur verschieben.<br>"
            "- Linksklick auf Ecke: Winkel numerisch ändern und fixieren.<br>"
            "- Linksklick auf Seite: Seitenlänge numerisch ändern <br>"
            "   und fixieren.<br>"
            "- Um einen fixierten Wert zu ändern, muss die Fixierung zuerst gelöst werden.<br>"
            "<br>"
            "Fixierte Seiten/Ecken sind orange markiert und koennen nicht bewegt werden, solange sie fixiert sind."
        )
        dlg = QtWidgets.QMessageBox(self)
        dlg.setWindowTitle("Hilfe / Bedienung")
        dlg.setTextFormat(QtCore.Qt.TextFormat.RichText)
        dlg.setStyleSheet("QLabel{font-size:13pt;}")
        dlg.setText(text)
        dlg.exec()

    @QtCore.Slot(str, str, str)
    def _show_update_dialog(self, latest_version: str, updater_path: str, exe_path: str):
        if os.path.exists(updater_path):
            QtWidgets.QMessageBox.information(
                self,
                "Update verfuegbar",
                f"Neue Version {latest_version} gefunden!\n\nDas Programm wird geschlossen und der Updater gestartet."
            )
            try:
                subprocess.Popen([updater_path, exe_path], shell=False)
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Fehler beim Starten des Updaters", str(exc))
            QtWidgets.QApplication.quit()
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "Updater fehlt",
                "Updater.exe nicht gefunden. Bitte manuell aktualisieren."
            )

def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.resize(1400, 900)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
