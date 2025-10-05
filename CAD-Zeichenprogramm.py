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

APP_VERSION = "2.0.0"
GITHUB_API = "https://api.github.com/repos/clanmonsterxd-cmd/CAD-Zeichner/releases/latest"

def check_for_updates_and_run_updater():
    try:
        resp = requests.get(GITHUB_API, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        latest_version = data["tag_name"].lstrip("v")

        if latest_version > APP_VERSION:
            exe_path = sys.argv[0]
            exe_dir = os.path.dirname(exe_path)
            updater_path = os.path.join(exe_dir, "updater.exe")

            if os.path.exists(updater_path):
                QtWidgets.QMessageBox.information(
                    None, "Update verfügbar",
                    f"Neue Version {latest_version} gefunden!\n\n"
                    "Das Programm wird geschlossen und der Updater gestartet."
                )
                subprocess.Popen([updater_path, exe_path], shell=True)
                QtWidgets.QApplication.quit()
            else:
                QtWidgets.QMessageBox.warning(
                    None, "Updater fehlt",
                    "Updater.exe nicht gefunden. Bitte manuell aktualisieren."
                )
    except Exception as e:
        print("Update-Check fehlgeschlagen:", e)

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
        self.fixed_corner_values_deg = [None, None, None, None]

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
        self.fixed_corner_values_deg = [None, None, None, None]
        self.last_side_idx = None
        self.last_corner_idx = None
        # Aktualisieren
        self._recalc_user_lines()
        self.auto_adjust_scale_if_needed()
        self.initial_quad = list(self.quad)
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
        if self.unit == 'mm':
            return f"{val:.1f} {UNIT_LABEL[self.unit]}"
        elif self.unit == 'cm':
            return f"{val:.2f} {UNIT_LABEL[self.unit]}"
        else:
            return f"{val:.4f} {UNIT_LABEL[self.unit]}"

    def format_angle(self, angle_deg: float) -> str:
        return f"{angle_deg:.1f}°"

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
                label = f"{side_ang:.1f}° zur Seite"
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
        step_px = self.grid_step_px
        draw_step = step_px
        if draw_step < 6:
            draw_step = step_px * 5
        pen = QtGui.QPen(QtGui.QColor(230,230,230))
        pen.setWidth(1)
        qp.setPen(pen)
        w = self.width(); h = self.height()
        x = 0
        while x <= w:
            qp.drawLine(x, 0, x, h)
            x += draw_step
        y = 0
        while y <= h:
            qp.drawLine(0, y, w, y)
            y += draw_step

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
                self.drag_line_initial = {'p1':ln['p1'], 'p2':ln['p2'], 'mouse0': pos,
                                          'p1snap': self._point_snapped_to_side(ln['p1']),
                                          'p2snap': self._point_snapped_to_side(ln['p2'])}
                self.setCursor(QtCore.Qt.SizeAllCursor)
                return

            sidx, t = self._find_side_index(pos, return_t=True)
            if sidx is not None:
                self.last_side_idx = sidx
                if self.fixed_sides[sidx]:
                    if self.parentWidget() is not None:
                        self.parentWidget().statusBar().showMessage("Seite ist fixiert (orange) — zum Bewegen zuerst lösen.", 4000)
                    return
                self.dragging_side = True
                self.drag_side_idx = sidx
                a = self.quad[sidx]; b = self.quad[(sidx+1)%4]
                proj, tproj = project_point_segment(pos, a, b)
                self.drag_side_initial = {'a':a, 'b':b, 'click_t': tproj}
                self.setCursor(QtCore.Qt.ClosedHandCursor)
                return

            if ev.button() == QtCore.Qt.MiddleButton and self._point_in_quad(pos):
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

        if self.dragging_side and self.drag_side_initial:
            i = self.drag_side_idx
            if self.fixed_sides[i]:
                return
            a0 = self.drag_side_initial['a']; b0 = self.drag_side_initial['b']
            vx = b0[0]-a0[0]; vy = b0[1]-a0[1]
            seg_len = math.hypot(vx,vy)
            if seg_len == 0:
                return
            ux, uy = vx/seg_len, vy/seg_len
            proj, tclick = project_point_segment(pos, a0, b0)
            click_param = self.drag_side_initial['click_t']
            orig_proj = (a0[0] + click_param*vx, a0[1] + click_param*vy)
            delta = ((proj[0]-orig_proj[0])*ux + (proj[1]-orig_proj[1])*uy)
            s1 = -delta * (1 - click_param)
            s2 = delta * click_param
            new_a = (a0[0] + s1*ux, a0[1] + s1*uy)
            new_b = (b0[0] + s2*ux, b0[1] + s2*uy)
            self.quad[i] = new_a
            self.quad[(i+1)%4] = new_b
            self._make_quad_consistent_after_side_change(i)
            self._recalc_user_lines()
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
            if self.dragging_side:
                self.dragging_side = False
                self.drag_side_idx = None
                self.drag_side_initial = None
                self.setCursor(QtCore.Qt.ArrowCursor)
                self._recalc_user_lines()
                self.update()
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
        layout.addWidget(QtWidgets.QLabel("Winkel in °:"))
        layout.addWidget(spin)

        cb = QtWidgets.QCheckBox("Fixieren")
        cb.setChecked(self.fixed_corners[idx])
        layout.addWidget(cb)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        layout.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)

        if dlg.exec():
            val = spin.value()

            # Änderung immer übernehmen
            self._apply_corner_angle_change(idx, val)
            self.angle_values[idx] = val

            # Fixierstatus übernehmen
            was_fixed = self.fixed_corners[idx]
            is_fixed = cb.isChecked()
            self.fixed_corners[idx] = is_fixed

            if is_fixed:
                self.fixed_corner_values_deg[idx] = val
            else:
                self.fixed_corner_values_deg[idx] = None

            # Feedback
            if was_fixed != is_fixed and self.parentWidget() is not None:
                msg = (f"Ecke {idx+1} fixiert ({val:.1f}°)"
                    if is_fixed else f"Ecke {idx+1} gelöst")
                self.parentWidget().statusBar().showMessage(msg, 3000)

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
        layout.addWidget(QtWidgets.QLabel("Länge in cm:"))
        layout.addWidget(spin)

        cb = QtWidgets.QCheckBox("Fixieren")
        cb.setChecked(self.fixed_sides[idx])
        layout.addWidget(cb)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        layout.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)

        if dlg.exec():
            val_cm = spin.value()
            val_mm = val_cm * 10.0

            # Änderung IMMER übernehmen
            self._apply_side_length_change(idx, val_mm)
            self.side_lengths[idx] = val_mm

            # Jetzt Fixierstatus übernehmen
            was_fixed = self.fixed_sides[idx]
            is_fixed = cb.isChecked()
            self.fixed_sides[idx] = is_fixed

            if is_fixed:
                self.fixed_side_values_mm[idx] = val_mm
            else:
                self.fixed_side_values_mm[idx] = None

            # Feedback
            if was_fixed != is_fixed and self.parentWidget() is not None:
                msg = (f"Seite {idx+1} fixiert ({self.format_length_mm(val_mm)})"
                    if is_fixed else f"Seite {idx+1} gelöst")
                self.parentWidget().statusBar().showMessage(msg, 3000)

            self.update()

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

    def auto_adjust_scale_if_needed(self):
        if not self.quad: return
        margin_px = mm_to_px(MARGIN_MM, self.effective_px_per_mm())
        left = min(p[0] for p in self.quad)
        right = max(p[0] for p in self.quad)
        top = min(p[1] for p in self.quad)
        bottom = max(p[1] for p in self.quad)
        w = self.width(); h = self.height()
        need_fit = (left < margin_px or top < margin_px or right > w - margin_px or bottom > h - margin_px)
        if not need_fit:
            return
        quad_w = right - left; quad_h = bottom - top
        if quad_w <= 0 or quad_h <= 0:
            return
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
        self._recalc_user_lines()

    def scale_about_center(self, factor):
        if factor <= 0: return
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
        self._recalc_user_lines()
        self.update()

    def reset(self):
        self.init_quad_default()
        self.user_lines = []
        self.intersection_handles = []
        self.update_scale_dependent_metrics()
        self.update()

    def pan_view(self, dx_px, dy_px):
        if not self.quad: return
        self.quad = [(p[0]+dx_px, p[1]+dy_px) for p in self.quad]
        for ln in self.user_lines:
            ln['p1'] = (ln['p1'][0]+dx_px, ln['p1'][1]+dy_px)
            ln['p2'] = (ln['p2'][0]+dx_px, ln['p2'][1]+dy_px)
        self.update()

    def _make_point_string(self, p): return f"({p[0]:.1f}, {p[1]:.1f})"

    def toggle_fix_side(self):
        idx = self.last_side_idx
        if idx is None:
            QtWidgets.QMessageBox.information(self, "Seite fixieren", "Keine Seite ausgewählt. Klicke zuerst auf eine Seite (Linksklick).")
            return
        if not self.fixed_sides[idx]:
            a = self.quad[idx]; b = self.quad[(idx+1)%4]
            length_mm = px_to_mm(dist(a,b), self.effective_px_per_mm())
            self.fixed_side_values_mm[idx] = length_mm
            self.fixed_sides[idx] = True
            if self.parentWidget() is not None:
                self.parentWidget().statusBar().showMessage(f"Seite {idx+1} fixiert ({self.format_length_mm(length_mm)})", 4000)
        else:
            self.fixed_sides[idx] = False
            self.fixed_side_values_mm[idx] = None
            if self.parentWidget() is not None:
                self.parentWidget().statusBar().showMessage(f"Seite {idx+1} gelöst", 3000)
        self.update()

    def toggle_fix_corner(self):
        idx = self.last_corner_idx
        if idx is None:
            QtWidgets.QMessageBox.information(self, "Ecke fixieren", "Keine Ecke ausgewählt. Klicke zuerst auf eine Ecke (Linksklick).")
            return
        if not self.fixed_corners[idx]:
            prev = self.quad[(idx+3)%4]; cur = self.quad[idx]; nxt = self.quad[(idx+1)%4]
            ang = angle_signed(prev, cur, nxt)
            interior = 360-ang if ang>180 else ang
            self.fixed_corner_values_deg[idx] = interior
            self.fixed_corners[idx] = True
            if self.parentWidget() is not None:
                self.parentWidget().statusBar().showMessage(f"Ecke {idx+1} fixiert ({interior:.1f}°)", 4000)
        else:
            self.fixed_corners[idx] = False
            self.fixed_corner_values_deg[idx] = None
            if self.parentWidget() is not None:
                self.parentWidget().statusBar().showMessage(f"Ecke {idx+1} gelöst", 3000)
        self.update()

    def _apply_side_length_change(self, idx, new_len_mm):
        if self.fixed_sides[idx]:
            return  # keine Änderung erlaubt
        a, b = self.quad[idx], self.quad[(idx+1)%4]
        vec = (b[0]-a[0], b[1]-a[1])
        old_len = math.hypot(*vec)
        if old_len == 0:
            return
        scale = (new_len_mm * self.px_per_mm) / old_len
        # Seitenrichtung beibehalten
        b_new = (a[0] + vec[0]*scale, a[1] + vec[1]*scale)
        self.quad[(idx+1)%4] = b_new
        self._realign_to_initial_position()

    def _apply_corner_angle_change(self, idx, new_angle_deg):
        if self.fixed_corners[idx]:
            return
        # Nachbarn und aktueller Winkel
        prev = self.quad[(idx + 3) % 4]
        cur = self.quad[idx]
        nxt = self.quad[(idx + 1) % 4]
        # aktuelle Vektoren
        v_prev = (prev[0] - cur[0], prev[1] - cur[1])
        v_next = (nxt[0] - cur[0], nxt[1] - cur[1])
        len_prev = math.hypot(*v_prev)
        len_next = math.hypot(*v_next)
        if len_prev == 0 or len_next == 0:
            return
        # aktueller Innenwinkel
        current_signed = angle_signed(prev, cur, nxt)
        current_interior = 360 - current_signed if current_signed > 180 else current_signed
        # Zielwinkel
        target = new_angle_deg
        delta = math.radians(target - current_interior)
        # Drehrichtung bestimmen (links/rechts)
        sign = 1.0
        if current_signed > 180:  # Reflexwinkel
            sign = -1.0
        # Rotation auf v_next anwenden
        cosd = math.cos(sign * delta)
        sind = math.sin(sign * delta)
        rx = v_next[0] * cosd - v_next[1] * sind
        ry = v_next[0] * sind + v_next[1] * cosd
        new_nxt = (cur[0] + rx, cur[1] + ry)
        self.quad[(idx + 1) % 4] = new_nxt
        # Nach Änderung an ursprüngliche Lage ausrichten
        self._realign_to_initial_position()

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
        self.statusBar().showMessage("Rechtsklick + Ziehen: Linie zeichnen | Links: Ecken/Seiten editieren | Mitte: Ziehen/Bewegen")
        QtCore.QTimer.singleShot(0, self._go_fullscreen)
        self.show()
        QtCore.QTimer.singleShot(2000, check_for_updates_and_run_updater)

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
        unit_menu.addItems(['mm','cm','m'])
        unit_menu.setCurrentText('cm')
        unit_menu.activated.connect(self._unit_changed)
        tb.addWidget(unit_menu)

        act_grid = QtGui.QAction("Raster", self)
        act_grid.setCheckable(True)
        act_grid.setChecked(True)
        act_grid.toggled.connect(self._toggle_grid)
        tb.addAction(act_grid)

        act_screenshot = QtGui.QAction("Screenshot", self)
        act_screenshot.triggered.connect(self._screenshot)
        tb.addAction(act_screenshot)

        act_help = QtGui.QAction("Hilfe", self)
        act_help.triggered.connect(self._show_help)
        tb.addAction(act_help)

        act_close = QtGui.QAction("Schließen", self)
        act_close.triggered.connect(self.close)
        tb.addAction(act_close)

    def _reset_clicked(self):
        self.canvas.reset()
        self.statusBar().showMessage("Zurückgesetzt", 3000)

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

    def _toggle_fix_side(self):
        self.canvas.toggle_fix_side()

    def _toggle_fix_corner(self):
        self.canvas.toggle_fix_corner()

    def _screenshot(self):
        pix = self.canvas.grab()
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        fname = os.path.join(desktop, f"screenshot_{QtCore.QDateTime.currentDateTime().toString('yyyy-MM-dd_hh-mm-ss')}.png")
        pix.save(fname, "PNG")
        self.statusBar().showMessage(f"Screenshot gespeichert: {fname}", 5000)

    def _show_help(self):
        text = (
            "Kurzbedienung:<br>"
            "- Rechtsklick + Ziehen: neue Linie zeichnen <br>"
            "   (snap an Seiten/anderen Linien/ Raster).<br>"
            "- Mittel-Taste (Klick + Ziehen): Ganze Figur verschieben.<br>"
            "- Linksklick auf Ecke: Winkel numerisch ändern und fixieren.<br>"
            "- Linksklick auf Seite: Seitenlänge numerisch ändern <br>"
            "   und fixieren.<br>"
            "- Ist ein Wert ersteinmal fixiert muss mann, <br>"
            "   um Ihn zu ändern, die Fixierung erst aufheben.<br>"
            "<br>"
            "Fixierte Seiten/Ecken sind orange markiert <br>"
            "und können nicht bewegt werden, solange sie fixiert sind."
        )
        dlg = QtWidgets.QMessageBox(self)
        dlg.setWindowTitle("Hilfe / Bedienung")
        dlg.setTextFormat(QtCore.Qt.TextFormat.RichText)
        dlg.setStyleSheet("QLabel{font-size:13pt;}")
        dlg.setText(text)
        dlg.exec()

def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.resize(1400, 900)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()