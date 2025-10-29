import sys, cv2, mediapipe as mp, numpy as np, time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame,
    QPushButton, QTextEdit, QShortcut, QSizePolicy
)
from PyQt5.QtGui import QFont, QImage, QPixmap, QKeySequence
from PyQt5.QtCore import Qt, QTimer, QPoint

# ==== Canvas + Gesture Config ====
CANVAS_W, CANVAS_H = 1280, 720
canvas = np.ones((CANVAS_H, CANVAS_W, 3), dtype=np.uint8) * 255

pen_color = (0, 0, 0)
pen_thickness = 5
eraser_thickness = 60
eraser_mode = False
gesture_enabled = True
prev_x, prev_y = 0, 0
alpha = 0.35
last_draw_point = None

# Mediapipe setup
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.6)
cap = cv2.VideoCapture(0)

def fingers_up(hand_landmarks):
    tips_ids = [4, 8, 12, 16, 20]
    up = []
    for tip in tips_ids:
        tip_y = hand_landmarks.landmark[tip].y
        pip_y = hand_landmarks.landmark[tip - 2].y
        up.append(tip_y < pip_y)
    return up

def get_gesture(up):
    # up = [thumb, index, middle, ring, pinky]
    if all(up): return "erase"
    elif up[1] and not up[2] and not up[3] and not up[4]: return "move"
    elif up[1] and up[2] and not up[3] and not up[4]: return "draw"
    else: return None

# ==== PyQt5 Layout ====
class SmartBoardApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smartboard - Virtual Mouse + AI Output")
        self.setGeometry(100, 100, 1200, 700)

        # ===== Main Layout =====
        main_layout = QHBoxLayout()
        right_layout = QVBoxLayout()

        # Left: Smartboard (canvas only)
        self.board = QLabel()
        self.board.setFrameStyle(QFrame.Box)
        self.board.setAlignment(Qt.AlignCenter)
        self.board.setStyleSheet("background-color: white; border: 2px solid black;")

        # Make board expand but we will scale pixmap to it each frame
        self.board.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # set an initial preferred size (won't force growth)
        self.board.setMinimumSize(800, 450)

        # Right: Camera preview
        self.camera = QLabel("CAMERA FEED")
        self.camera.setFrameStyle(QFrame.Box)
        self.camera.setAlignment(Qt.AlignCenter)
        self.camera.setFont(QFont("Arial", 12))
        self.camera.setStyleSheet("background-color: lightgray; border: 2px solid black;")
        self.camera.setFixedHeight(300)

        # Right: AI Output placeholder
        self.output = QLabel("AI OUTPUT")
        self.output.setFrameStyle(QFrame.Box)
        self.output.setAlignment(Qt.AlignCenter)
        self.output.setFont(QFont("Arial", 12))
        self.output.setStyleSheet("background-color: #f0f0f0; border: 2px solid black;")
        self.output.setFixedHeight(150)

        # Toolbar Buttons (optional)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.clear_canvas)
        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self.save_canvas)
        self.btn_gesture = QPushButton("Toggle Gesture")
        self.btn_gesture.clicked.connect(self.toggle_gesture)
        self.btn_eraser = QPushButton("Toggle Eraser")
        self.btn_eraser.clicked.connect(self.toggle_eraser)

        control_layout = QHBoxLayout()
        for b in [self.btn_clear, self.btn_save, self.btn_gesture, self.btn_eraser]:
            b.setFixedHeight(36)
            control_layout.addWidget(b)

        # Status label
        self.status = QLabel("Status: Ready | Gesture ON | Eraser OFF")
        self.status.setFont(QFont("Arial", 11))
        self.status.setStyleSheet("padding: 5px; background: #efefef; border: 1px solid #ccc;")

        right_layout.addWidget(self.camera)
        right_layout.addWidget(self.output)
        right_layout.addLayout(control_layout)
        right_layout.addWidget(self.status)
        right_layout.addStretch()

        main_layout.addWidget(self.board, 3)
        main_layout.addLayout(right_layout, 1)
        self.setLayout(main_layout)

        # Shortcuts
        QShortcut(QKeySequence("C"), self, self.clear_canvas)
        QShortcut(QKeySequence("S"), self, self.save_canvas)
        QShortcut(QKeySequence("G"), self, self.toggle_gesture)
        QShortcut(QKeySequence("E"), self, self.toggle_eraser)

        # Timer to update frames
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frames)
        self.timer.start(20)  # 50 fps-ish

        # Mouse drawing vars (we will draw on the numpy canvas)
        self.mouse_pressed = False
        self.last_mouse_canvas_point = None

    # ---------- Mouse events (mapped to canvas coordinates) ----------
    def mousePressEvent(self, event):
        # Only allow mouse drawing if gesture is OFF and click inside board
        if not gesture_enabled and event.button() == Qt.LeftButton:
            if self._pos_inside_board(event.pos()):
                self.mouse_pressed = True
                self.last_mouse_canvas_point = self._qtpos_to_canvas(event.pos())
                self.status.setText("Status: Drawing (Mouse)")
        elif not gesture_enabled and event.button() == Qt.RightButton:
            if self._pos_inside_board(event.pos()):
                self.mouse_pressed = True
                self.last_mouse_canvas_point = self._qtpos_to_canvas(event.pos())
                self.status.setText("Status: Erasing (Mouse)")

    def mouseMoveEvent(self, event):
        global canvas, pen_color, pen_thickness, eraser_thickness
        if self.mouse_pressed and not gesture_enabled:
            if self._pos_inside_board(event.pos()):
                cur = self._qtpos_to_canvas(event.pos())
                prev = self.last_mouse_canvas_point
                if prev is None:
                    self.last_mouse_canvas_point = cur
                    return
                x1,y1 = prev; x2,y2 = cur
                buttons = event.buttons()
                if buttons & Qt.LeftButton:
                    cv2.line(canvas, (x1,y1), (x2,y2), pen_color, pen_thickness)
                elif buttons & Qt.RightButton:
                    cv2.line(canvas, (x1,y1), (x2,y2), (255,255,255), eraser_thickness)
                self.last_mouse_canvas_point = cur

    def mouseReleaseEvent(self, event):
        if self.mouse_pressed:
            self.mouse_pressed = False
            self.last_mouse_canvas_point = None
            self.status.setText(f"Status: Ready | Gesture {'ON' if gesture_enabled else 'OFF'} | Eraser {'ON' if eraser_mode else 'OFF'}")

    def _pos_inside_board(self, qt_point: QPoint):
        # qt_point is relative to main window. Check if inside board widget geometry.
        board_rect = self.board.geometry()
        return board_rect.contains(qt_point)

    def _qtpos_to_canvas(self, qt_point: QPoint):
        # Map a point in window coords to canvas pixel coords
        # First find point relative to board top-left:
        board_tl = self.board.mapTo(self, self.board.rect().topLeft())  # board top-left in window coords
        # But easier: use mapFromParent / mapFromGlobal - simpler approach:
        local = self.board.mapFromParent(qt_point)  # position inside board widget
        bx = local.x(); by = local.y()
        # clamp inside label
        bw = self.board.width(); bh = self.board.height()
        if bx < 0: bx = 0
        if by < 0: by = 0
        if bx > bw: bx = bw
        if by > bh: by = bh
        # Map label coordinates to canvas (numpy) coordinates
        cx = int(bx * CANVAS_W / bw)
        cy = int(by * CANVAS_H / bh)
        return (cx, cy)

    # ---------- Frame update (gesture + display) ----------
    def update_frames(self):
        global canvas, prev_x, prev_y, last_draw_point, eraser_mode, gesture_enabled

        ret, frame = cap.read()
        if not ret:
            return
        frame = cv2.flip(frame, 1)
        cam_h, cam_w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = hands.process(rgb)

        overlay = canvas.copy()  # draw status and pointer on overlay, then scale to label

        draw_point = None
        if gesture_enabled and res.multi_hand_landmarks:
            for hand_landmarks in res.multi_hand_landmarks:
                mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                index_tip = hand_landmarks.landmark[8]
                x_px = int(index_tip.x * cam_w)
                y_px = int(index_tip.y * cam_h)
                cx = (1 - alpha) * prev_x + alpha * x_px
                cy = (1 - alpha) * prev_y + alpha * y_px
                prev_x, prev_y = cx, cy
                up = fingers_up(hand_landmarks)
                gesture = get_gesture(up)

                canvas_x = int(np.interp(cx, [0, cam_w], [0, CANVAS_W]))
                canvas_y = int(np.interp(cy, [0, cam_h], [0, CANVAS_H]))
                pointer_point = (canvas_x, canvas_y)
                cv2.circle(overlay, pointer_point, 6, (255, 0, 0), 2)

                if gesture == "draw":
                    draw_point = pointer_point
                    eraser_mode = False
                    self.status.setText("Status: Drawing (Gesture) | Gesture ON | Eraser OFF")
                elif gesture == "erase":
                    draw_point = pointer_point
                    eraser_mode = True
                    self.status.setText("Status: Erasing (Gesture) | Gesture ON | Eraser ON")
                else:
                    draw_point = None

        # gesture drawing: write directly to canvas (already persistent)
        if draw_point:
            global last_draw_point
            if last_draw_point is None:
                last_draw_point = draw_point
            lx, ly = last_draw_point
            cxp, cyp = draw_point
            if eraser_mode:
                cv2.line(canvas, (lx, ly), (cxp, cyp), (255, 255, 255), eraser_thickness)
            else:
                cv2.line(canvas, (lx, ly), (cxp, cyp), pen_color, pen_thickness)
            last_draw_point = (cxp, cyp)
        else:
            last_draw_point = None

        # Draw status text on overlay (these coordinates are in canvas pixels)
        cv2.putText(overlay, f"Gesture: {'ON' if gesture_enabled else 'OFF'}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 80, 80), 2)
        cv2.putText(overlay, f"Eraser: {'ON' if eraser_mode else 'OFF'}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 80, 80), 2)

        # Convert overlay to QImage
        rgb_board = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
        qimg_board = QImage(rgb_board.data, rgb_board.shape[1], rgb_board.shape[0], QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg_board)

        # Scale the pixmap to label size (so when full-screen, everything scales proportionally)
        scaled = pixmap.scaled(self.board.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.board.setPixmap(scaled)

        # Camera feed on right panel (scaled to label width)
        qimg_cam = QImage(rgb.data, rgb.shape[1], rgb.shape[0], QImage.Format_RGB888)
        cam_pix = QPixmap.fromImage(qimg_cam).scaled(self.camera.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.camera.setPixmap(cam_pix)

    # ---------- Toolbar actions ----------
    def clear_canvas(self):
        global canvas
        canvas = np.ones((CANVAS_H, CANVAS_W, 3), dtype=np.uint8) * 255
        self.status.setText(f"Status: Canvas Cleared | Gesture {'ON' if gesture_enabled else 'OFF'} | Eraser {'ON' if eraser_mode else 'OFF'}")

    def save_canvas(self):
        global canvas
        filename = f"smartboard_{int(time.time())}.png"
        cv2.imwrite(filename, canvas)
        self.status.setText(f"Status: Saved as {filename} | Gesture {'ON' if gesture_enabled else 'OFF'} | Eraser {'ON' if eraser_mode else 'OFF'}")

    def toggle_gesture(self):
        global gesture_enabled
        gesture_enabled = not gesture_enabled
        self.status.setText(f"Status: Gesture {'Enabled' if gesture_enabled else 'Disabled'} | Eraser {'ON' if eraser_mode else 'OFF'}")

    def toggle_eraser(self):
        global eraser_mode
        eraser_mode = not eraser_mode
        self.status.setText(f"Status: Eraser {'ON' if eraser_mode else 'OFF'} | Gesture {'ON' if gesture_enabled else 'OFF'}")

# ==== Run App ====
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SmartBoardApp()
    win.show()
    sys.exit(app.exec_())
