import sys, cv2, mediapipe as mp, numpy as np, time
from dotenv import load_dotenv
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QFrame, QPushButton, QSizePolicy
)
from PyQt5.QtGui import QFont, QImage, QPixmap
from PyQt5.QtWidgets import QTextEdit
from PyQt5.QtCore import Qt, QTimer
from groq import Groq
import easyocr
import os
import datetime
import json

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ===== Undo / Redo Stacks =====
undo_stack = []
redo_stack = []
MAX_HISTORY = 20

# ================= Canvas Config =================
CANVAS_W, CANVAS_H = 1280, 720
canvas = np.ones((CANVAS_H, CANVAS_W, 3), dtype=np.uint8) * 255

pen_color = (0, 0, 0)

# 🔥 Increased thickness for better OCR detection
pen_thickness = 12
eraser_thickness = 80

eraser_mode = False
gesture_enabled = True

prev_x, prev_y = 0, 0
alpha = 0.35
last_draw_point = None

typing_mode = False
typed_text = ""
text_position = (100, 100)
# ================= Mediapipe =================
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    min_detection_confidence=0.7,
    min_tracking_confidence=0.6
)

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
    if all(up):
        return "erase"
    elif up[1] and up[2] and not up[3] and not up[4]:
        return "draw"
    elif up[1] and not up[2] and not up[3] and not up[4]:
        return "move"
    return None


# ================= Main App =================
class SmartBoardApp(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Clarion - Smart Blackboard")
        self.setGeometry(100, 100, 1200, 700)
        self.setFocusPolicy(Qt.StrongFocus)

        self.ocr_reader = easyocr.Reader(['en'], gpu=False)

        main_layout = QHBoxLayout()
        right_layout = QVBoxLayout()

        # -------- Board --------
        self.board = QLabel()
        self.board.setFrameStyle(QFrame.Box)
        self.board.setAlignment(Qt.AlignCenter)
        self.board.setStyleSheet(
            "background-color: white; border: 2px solid black;"
        )
        self.board.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self.board.setMinimumSize(800, 450)

        # -------- Camera --------
        self.camera = QLabel()
        self.camera.setFrameStyle(QFrame.Box)
        self.camera.setFixedHeight(300)

        # -------- Output --------
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Arial", 11))
        self.output.setMinimumHeight(250)
        self.output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.output.setStyleSheet("""
            QTextEdit {
                background-color: #f8f8f8;
                border: 1px solid #ccc;
                padding: 8px;
            }
        """)

        # -------- Buttons --------
        self.btn_clear = QPushButton("Clear")
        self.btn_save = QPushButton("Save")
        self.btn_gesture = QPushButton("Toggle Gesture")
        self.btn_eraser = QPushButton("Toggle Eraser")
        self.btn_analyze = QPushButton("Analyze Board")

        self.btn_clear.clicked.connect(self.clear_canvas)
        self.btn_save.clicked.connect(self.save_canvas)
        self.btn_gesture.clicked.connect(self.toggle_gesture)
        self.btn_eraser.clicked.connect(self.toggle_eraser)
        self.btn_analyze.clicked.connect(self.analyze_board)

        controls = QHBoxLayout()
        for b in [self.btn_clear, self.btn_save,
                  self.btn_gesture, self.btn_eraser,
                  self.btn_analyze]:
            controls.addWidget(b)

        self.status = QLabel("Status: Ready")
        self.status.setStyleSheet(
            "padding:5px; background:#efefef;"
        )

        right_layout.addWidget(self.camera)
        right_layout.addWidget(self.output)
        right_layout.addLayout(controls)
        right_layout.addWidget(self.status)
        right_layout.addStretch()

        main_layout.addWidget(self.board, 3)
        main_layout.addLayout(right_layout, 1)

        self.setLayout(main_layout)

        # -------- Timer --------
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frames)
        self.timer.start(20)

        # Mouse
        self.mouse_pressed = False
        self.last_mouse_point = None

    # ================= KEYBOARD =================
    def keyPressEvent(self, event):
        global gesture_enabled, eraser_mode
        global typing_mode, typed_text, text_position

        # Toggle typing mode
        if event.key() == Qt.Key_Q:
            typing_mode = not typing_mode
            self.status.setText(
                f"Typing Mode {'ON' if typing_mode else 'OFF'}"
            )
            return

        if typing_mode:
            if event.key() == Qt.Key_Backspace:
                typed_text = typed_text[:-1]

            elif event.key() == Qt.Key_Return:
                if typed_text.strip():
                    self.save_state()
                    cv2.putText(
                        canvas,
                        typed_text,
                        text_position,
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.5,           # Bigger font
                        (0, 0, 0),
                        3              # Thicker text for OCR
                    )
                typed_text = ""

            else:
                typed_text += event.text()

            return

        # Existing shortcuts
        if event.key() == Qt.Key_C:
            self.clear_canvas()

        elif event.key() == Qt.Key_S:
            self.save_canvas()

        elif event.key() == Qt.Key_G:
            gesture_enabled = not gesture_enabled

        elif event.key() == Qt.Key_E:
            eraser_mode = not eraser_mode
        
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Z:
            self.undo()


    # ================= MOUSE =================
    def mousePressEvent(self, event):
        global text_position

        if event.button() in (Qt.LeftButton, Qt.RightButton):
            if self.board.geometry().contains(event.pos()):
                self.mouse_pressed = True
                self.save_state()
                self.last_mouse_point = self.map_to_canvas(event.pos())
                text_position = self.last_mouse_point

    def mouseMoveEvent(self, event):
        global canvas

        if not self.mouse_pressed:
            return

        if self.board.geometry().contains(event.pos()):
            current = self.map_to_canvas(event.pos())
            prev = self.last_mouse_point

            if prev:
                color = (255, 255, 255) if eraser_mode else pen_color
                thickness = eraser_thickness if eraser_mode else pen_thickness
                cv2.line(canvas, prev, current, color, thickness)

            self.last_mouse_point = current

    def mouseReleaseEvent(self, event):
        self.mouse_pressed = False
        self.last_mouse_point = None

    def map_to_canvas(self, pos):
        local = self.board.mapFromParent(pos)
        bx, by = local.x(), local.y()
        bw, bh = self.board.width(), self.board.height()
        cx = int(bx * CANVAS_W / bw)
        cy = int(by * CANVAS_H / bh)
        return (cx, cy)

    # ================= UPDATE =================
    def update_frames(self):
        global canvas, prev_x, prev_y
        global last_draw_point, eraser_mode
        global typing_mode, typed_text, text_position

        ret, frame = cap.read()
        if not ret:
            return

        frame = cv2.flip(frame, 1)
        cam_h, cam_w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        draw_point = None

        if gesture_enabled and result.multi_hand_landmarks:
            for hand_landmarks in result.multi_hand_landmarks:

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
                pointer = (canvas_x, canvas_y)

                if gesture == "draw":
                    eraser_mode = False
                    draw_point = pointer

                elif gesture == "erase":
                    eraser_mode = True
                    draw_point = pointer

        if draw_point:
            if last_draw_point is None:
                self.save_state()  # SAVE BEFORE DRAWING
                last_draw_point = draw_point

            color = (255, 255, 255) if eraser_mode else pen_color
            thickness = eraser_thickness if eraser_mode else pen_thickness

            cv2.line(canvas, last_draw_point,
                     draw_point, color, thickness)

            last_draw_point = draw_point
        else:
            last_draw_point = None

        overlay = canvas.copy()
        
        # ================= TYPING PREVIEW =================
        if typing_mode and typed_text:
            cv2.putText(
                overlay,
                typed_text,
                text_position,
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 0),
                2
            )

        # ================= POINTER MARKER =================
        if draw_point:
            marker_color = (0, 0, 255) if eraser_mode else (255, 0, 0)
            cv2.circle(overlay, draw_point, 10, marker_color, -1)

        # ================= ALWAYS SHOW POINTER =================
        if gesture_enabled and (prev_x != 0 or prev_y != 0):
            pointer_x = int(np.interp(prev_x, [0, cam_w], [0, CANVAS_W]))
            pointer_y = int(np.interp(prev_y, [0, cam_h], [0, CANVAS_H]))
            cv2.circle(overlay, (pointer_x, pointer_y), 8, (0, 120, 255), -1)

        # ================= STATUS TEXT OVERLAY =================
        cv2.putText(
            overlay,
            f"Gesture: {'ON' if gesture_enabled else 'OFF'}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (80, 80, 80),
            2
        )

        cv2.putText(
            overlay,
            f"Eraser: {'ON' if eraser_mode else 'OFF'}",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (80, 80, 80),
            2
        )

        if typing_mode:
            cv2.putText(
                overlay,
                "Typing Mode: ON",
                (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

        rgb_board = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)

        qimg = QImage(
            rgb_board.data,
            rgb_board.shape[1],
            rgb_board.shape[0],
            QImage.Format_RGB888
        )

        pixmap = QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(
            self.board.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.board.setPixmap(scaled)

        qimg_cam = QImage(
            rgb.data,
            rgb.shape[1],
            rgb.shape[0],
            QImage.Format_RGB888
        )

        self.camera.setPixmap(QPixmap.fromImage(qimg_cam))

    # ================= CONTROLS =================
    def clear_canvas(self):
        global canvas
        self.save_state()
        canvas[:] = 255

    def save_canvas(self):
        filename = f"clarion_{int(time.time())}.png"
        cv2.imwrite(filename, canvas)
        self.status.setText(f"Saved {filename}")

    def toggle_gesture(self):
        global gesture_enabled
        gesture_enabled = not gesture_enabled

    def toggle_eraser(self):
        global eraser_mode
        eraser_mode = not eraser_mode

    def analyze_board(self):
        self.status.setText("Analyzing board with AI...")

        texts = self.extract_text(canvas)
        shapes = self.detect_shapes(canvas)

        structured_prompt = "You are an AI smart classroom assistant.\n\n"

        # ✅ Include committed OCR text
        if texts:
            structured_prompt += "The following text was written on the board:\n"
            for t in texts:
                structured_prompt += f"- {t}\n"

        # ✅ NEW: Include currently typed text even if not committed
        if typed_text.strip():
            structured_prompt += "\nThe user is currently typing:\n"
            structured_prompt += f"- {typed_text.strip()}\n"

        if shapes:
            structured_prompt += "\nThe following shapes were detected:\n"
            for s in shapes:
                structured_prompt += f"- {s}\n"

        if not texts and not shapes and not typed_text.strip():
            self.output.setText("Nothing detected.")
            return

        structured_prompt += "\nExplain clearly what this represents. If it is a formula, explain it. If it is a question, answer it."

        ai_response = self.ask_ai(structured_prompt)

        self.output.setPlainText(ai_response)
        self.save_session(ai_response)
        self.status.setText("AI Analysis Complete")
    
    def detect_shapes(self, image):

        detected = []
    
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
        blur = cv2.GaussianBlur(gray, (5,5), 0)
    
        # Strong threshold for whiteboard
        _, thresh = cv2.threshold(blur, 180, 255, cv2.THRESH_BINARY_INV)
    
        # Fill gaps in hand drawn lines
        kernel = np.ones((5,5), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
        # Edge detection
        edges = cv2.Canny(thresh, 50, 150)
    
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
        for cnt in contours:
        
            area = cv2.contourArea(cnt)
    
            if area < 1500:
                continue
            
            peri = cv2.arcLength(cnt, True)
    
            approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
    
            sides = len(approx)
    
            if sides == 3:
                detected.append("Triangle")
    
            elif sides == 4:
                x, y, w, h = cv2.boundingRect(approx)
                aspect_ratio = w / float(h)
    
                if 0.9 <= aspect_ratio <= 1.1:
                    detected.append("Square")
                else:
                    detected.append("Rectangle")
    
            elif sides > 6:
                detected.append("Circle")
    
        return list(set(detected))


    def extract_text(self, image):

        # Downscale for speed
        small = cv2.resize(image, (640, 360))

        # Clean background
        small[small > 240] = 255

        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        # Strong threshold (better than adaptive for whiteboard)
        _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)

        # 🔥 DILATION to thicken strokes
        kernel = np.ones((3, 3), np.uint8)
        thresh = cv2.dilate(thresh, kernel, iterations=1)

        results = self.ocr_reader.readtext(thresh, detail=0)

        return [t.strip() for t in results if t.strip()]
    
    def save_state(self):
        global canvas, undo_stack, redo_stack

        undo_stack.append(canvas.copy())

        if len(undo_stack) > MAX_HISTORY:
            undo_stack.pop(0)

        # Clear redo stack whenever new action happens
        redo_stack.clear()
    
    def undo(self):
        global canvas, undo_stack, redo_stack

        if len(undo_stack) > 0:
            redo_stack.append(canvas.copy())
            canvas = undo_stack.pop()
            self.status.setText("Undo")

    def ask_ai(self, prompt_text):
        try:
            chat_completion = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are an intelligent classroom assistant."},
                    {"role": "user", "content": prompt_text}
                ],
                temperature=0.3
            )

            return chat_completion.choices[0].message.content

        except Exception as e:
            return f"AI Error: {str(e)}"
        
    def save_session(self, ai_output):
    
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        session_folder = os.path.join("sessions", f"session_{timestamp}")
        os.makedirs(session_folder, exist_ok=True)

        # Save board image
        board_path = os.path.join(session_folder, "board.png")
        cv2.imwrite(board_path, canvas)

        # Save AI explanation
        explanation_path = os.path.join(session_folder, "explanation.txt")
        with open(explanation_path, "w", encoding="utf-8") as f:
            f.write(ai_output)

        # Save metadata
        metadata = {
            "timestamp": timestamp,
            "board_image": board_path,
            "ai_explanation": explanation_path
        }

        metadata_path = os.path.join(session_folder, "session.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=4)

        self.status.setText(f"Session saved: {timestamp}")

# ================= RUN =================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SmartBoardApp()
    win.show()
    sys.exit(app.exec_())