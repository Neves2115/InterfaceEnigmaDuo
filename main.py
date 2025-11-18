"""
Enigma Duo — 
- Serial: COM3 @ 115200, 7E1 (7 data bits, even parity, 1 stop bit)
- ENTER: avança telas (se intro estiver digitando, completa o texto)
- S: toggles simulação
- C: limpa estado
- Q: sair

Tema aplicado: "Enigma / Cofre" (cores suaves, TEA-friendly)
"""

import tkinter as tk
from tkinter import font
import threading, time, sys
from PIL import Image, ImageTk
import os
import serial

# -------- THEME (Enigma / Cofre, TEA-friendly) ----------
THEME = {
  "bg":       "#0b0f14",
  "card":     "#1b2835",
  "panel":    "#121a22",
  "text":     "#e6e9eb",
  "muted":    "#a4b2b8",
  "hint":     "#e0d5b8",
  "accent":   "#c8a04a",
  "success":  "#5fae86",
  "near":     "#d98b5f",
  "almost":   "#d4b073",
  "far":      "#6ea7c8"
}

# -------- CONFIG ----------
PORT = "COM8"
BAUDRATE = 115200
READ_SLEEP = 0.01
UI_UPDATE_MS = 120
FAR_TH = 30
TH_VERY_CLOSE = 3
TH_ALMOST = 12

# -------- shared state ----------
# impedir escrita simultânea
state_lock = threading.Lock()
state = {
    "error": None,
    "serial_ok": False,
    "running": True,
    "sim_on": False
}
serial_write_lock = threading.Lock()


# -------- serial reader (7E1) ----------
class SerialReader(threading.Thread):
    def __init__(self, port, baud):
        super().__init__(daemon=True)
        self.port = port
        self.baud = baud
        self.ser = None
        self.buffer = ""
        self.running = True
        self._last_sent_result = None

    def open_serial(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                bytesize=serial.SEVENBITS,
                parity=serial.PARITY_EVEN,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.12
            )
            try: self.ser.reset_input_buffer()
            except: pass
            print(f"✅ Serial aberta: {self.port} @ {self.baud} (7E1)")
            with state_lock: state["serial_ok"] = True
            return True
        except Exception as e:
            print("Erro abrindo serial:", e)
            with state_lock: state["serial_ok"] = False
            self.ser = None
            return False

    def run(self):
        if not self.open_serial():
            while self.running and serial is not None:
                time.sleep(2.0)
                if self.open_serial(): break

        while self.running:
            try:
                if self.ser and self.ser.is_open:
                    try:
                        in_wait = self.ser.in_waiting
                    except Exception:
                        in_wait = 0
                    read_len = in_wait or 1
                    raw = self.ser.read(read_len)
                    if raw:
                        try: chunk = raw.decode('ascii', errors='ignore')
                        except: chunk = raw.decode('utf-8', errors='ignore')
                        self.buffer += chunk
                        while '#' in self.buffer:
                            frame, self.buffer = self.buffer.split('#', 1)
                            frame = frame.strip()
                            if frame != "":
                                self.process_frame(frame)
                    else:
                        time.sleep(READ_SLEEP)
                else:
                    with state_lock: state["serial_ok"] = False
                    time.sleep(0.6)
            except Exception as e:
                print("Erro no loop serial:", e)
                try:
                    if self.ser: self.ser.close()
                except: pass
                self.ser = None
                with state_lock: state["serial_ok"] = False
                time.sleep(1.0)
        try:
            if self.ser and self.ser.is_open: self.ser.close()
        except: pass
        print("SerialReader finalizado.")

    def process_frame(self, text):
        txt = text.replace('\r','').replace('\n','').strip()
        try:
            val = int(txt)
            with state_lock:
                state["error"] = max(0, val)
        except Exception as e:
            print(f"Frame inválido (ignorando): '{txt}' -> {e}")

    def stop(self):
        self.running = False

# -------- simulation ----------
def simulate_sequence():
    seq = [25, 12, 6, 3, 1, 0, 2, 5, 15, 28]
    while True:
        with state_lock:
            if not state.get("sim_on", False): break
        for v in seq:
            with state_lock:
                if not state.get("sim_on", False): break
                state["error"] = v
            print(f"[SIM] erro -> {v}")
            time.sleep(1.0)

# -------- helpers ----------
def qualitative_bucket(err):
    if err == 0: return 0, "ACERTO!"
    if err <= TH_VERY_CLOSE: return 1, "Muito próximo"
    if err <= TH_ALMOST: return 2, "Quase"
    return 3, "Longe"

def bucket_color(bucket):
    if bucket == 0: return THEME["success"]
    if bucket == 1: return THEME["near"]
    if bucket == 2: return THEME["almost"]
    return THEME["far"]

# -------- App with flow ----------
class EnigmaDuoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Enigma Duo")
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg=THEME["bg"])
        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))
        self._setup_fonts()
        self.screen = 'splash'
        root.bind("<Key>", self.on_key)
        self._setup_canvas()
        self._load_splash_image()
        self._setup_intro_typing()
        self._setup_game_state()
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        root.after(40, self.update_ui)


    def _setup_fonts(self):
        self.ft_title = font.Font(family="Helvetica", size=24, weight="bold")
        self.ft_sub   = font.Font(family="Helvetica", size=14)
        self.ft_big   = font.Font(family="Helvetica", size=46, weight="bold")
        self.ft_med   = font.Font(family="Helvetica", size=16)
        self.ft_small = font.Font(family="Helvetica", size=12)
        self.ft_game_like = self.game_font = font.Font(family="Consolas", size=14)

    def _setup_canvas(self):
        self.canvas = tk.Canvas(self.root, bg=THEME["panel"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.canvas.config(width=screen_w, height=screen_h)

    def _load_splash_image(self):
        try:
            path = os.path.join(os.path.dirname(__file__), "splash_enigma_duo.jpg")
            img = Image.open(path).convert("RGB")

            cw = int(self.canvas['width'])
            ch = int(self.canvas['height'])

            img.thumbnail((cw, ch), Image.LANCZOS)  # garante proporcional
            w, h = img.size

            if w < cw or h < ch:
                scale = max(cw / w, ch / h)
                img = img.resize((int(w*scale), int(h*scale)), Image.LANCZOS)

            # crop central
            w, h = img.size
            x0 = (w - cw) // 2
            y0 = (h - ch) // 2
            img = img.crop((x0, y0, x0 + cw, y0 + ch))

            self.splash_photo = ImageTk.PhotoImage(img)

        except Exception as e:
            print("⚠️ Erro carregando splash:", e)
            self.splash_photo = None

    def _setup_intro_typing(self):
        self.intro_text = (
            "À frente de vocês, um cofre antigo guarda segredos esquecidos. "
            "Para despertá-lo, será necessário que cooperem e resolvam os enigmas. "
            "Este é o primeiro de dois desafios: o Enigma da Distância. "
            "Um jogador move o anteparo, o outro observa os sinais do cofre. "
            "Cada reação é uma pista. Decifrem juntos... "
        )
        self.typing_pos = 0
        self.typing_speed_ms = 32
        self.typing_running = False
        self._fade_item = None

    def _setup_game_state(self):
        self.running = True
        # agora temos 6 algarismos secretos no total; o primeiro jogo exige os 3 primeiros
        self.secret_sequence = "235679"
        self.first_secret = self.secret_sequence[:3]   # '235' - usado no jogo 1

        # keypad state: lista de 3 slots e flags de locked para dígitos corretos
        self.keypad_input = ['','','']     # lista com 3 slots
        self.locked = [False, False, False]  # True significa dígito correto e imutável
        self.keypad_value = None   # opcional: valor confirmado (int) quando completo
        # feedback do keypad: tuple (type:str, until:float)
        self.kp_feedback = None

        # segundo jogo: tentar carregar imagem (opcional)
        self.symbols_img = None
        symbols_path = os.path.join(os.path.dirname(__file__), "symbols.jpg")
        if os.path.exists(symbols_path):
            try:
                self.symbols_img = Image.open(symbols_path).convert("RGBA")
            except Exception as e:
                print("⚠️ Não foi possível carregar symbols.jpg:", e)

        # texto de introdução ao segundo jogo
        self.intro2_text = (
            "Vocês decifraram um dos enigmas! Algo mudou no cofre — "
            "reparem com atenção: agora é o Enigma dos Símbolos. "
            "Uma seta apontará para símbolos; interpretem o padrão e respondam."
        )

    def _send_result_thread(self, correct: bool):
        try:
            ok = self.send_result_over_serial(correct)
            if not ok:
                print("[TX] Envio falhou no thread")
        except Exception as e:
            print("[TX] Erro no thread de envio:", e)

    def send_result_over_serial(self, correct: bool) -> bool:
        """
        Envia 0xFF (acerto) ou 0x00 (erro) usando reader.ser como fonte única.
        Retorna True se a escrita ocorreu com sucesso, False caso contrário.
        """
        byte_to_send = b'\xff' if correct else b'\x00'

        # obtém o objeto reader (supondo que esteja no global)
        rdr = globals().get('reader')
        if not rdr:
            print("[TX] reader não encontrado.")
            return False

        ser = getattr(rdr, 'ser', None)
        if not (ser and getattr(ser, 'is_open', False)):
            print("[TX] reader.ser não disponível/aberta.")
            return False

        lock = globals().get('serial_write_lock', None)
        try:
            if lock is not None:
                with lock:
                    ser.write(byte_to_send)
                    ser.flush()
            else:
                ser.write(byte_to_send)
                ser.flush()

            print(f"[TX] Enviado byte {byte_to_send.hex()} via reader.ser")
            return True
        except Exception as e:
            print("[TX] Erro escrevendo em reader.ser:", e)
            return False

    def on_key(self, event):
        key = event.keysym.lower()
        if self.screen in ('game', 'game2'):
            # tratar teclado do keypad
            if key.isdigit() and len(key) == 1:
                self._handle_keypad_press(key)
                return
            if key == "backspace":
                self._handle_keypad_press("DEL")
                return
            if key == "c":
                self._handle_keypad_press("CLR")
                with state_lock:
                    state["error"] = None
                return

        if key == 'return':
            if self.screen == 'splash':
                self.start_intro_transition()
            elif self.screen == 'intro':
                if self.typing_running:
                    self.finish_typing()
                else:
                    self.start_game()
            elif self.screen == 'intro2':
                # avança ao segundo jogo
                self.start_second_game()
            elif self.screen == 'game':
                # se já completou a sequência, ignorar (a transição já faz intro2)
                pass
            elif self.screen == 'game2':
                pass
        elif key == 's':
            with state_lock:
                state["sim_on"] = not state.get("sim_on", False)
            if state["sim_on"]:
                threading.Thread(target=simulate_sequence, daemon=True).start()
        elif key == 'q':
            self.on_close()

    def _on_canvas_click(self, event):
        """Detecta clique em botões do keypad desenhados no canvas."""
        try:
            x, y = event.x, event.y
            items = self.canvas.find_overlapping(x, y, x, y)
            if not items:
                return
            for iid in reversed(items):
                tags = self.canvas.gettags(iid)
                for t in tags:
                    if t.startswith("kp_btn_"):
                        key = t.replace("kp_btn_", "")
                        self._handle_keypad_press(key)
                        return
        except Exception as e:
            print("Erro _on_canvas_click:", e)


    def _handle_keypad_press(self, key):
        """Processa tecla do keypad: '0'..'9', 'DEL', 'CLR'.
        Implementa checagem algarismo-a-algarismo contra self.first_secret,
        trava dígitos corretos (não podem ser apagados) e avança para intro2 quando completo.
        """
        now = time.time()

        # DEL: remove o último dígito não-locked (se houver)
        if key == "DEL":
            # encontra último índice preenchido que não está locked
            for i in range(len(self.keypad_input)-1, -1, -1):
                if self.keypad_input[i] != '' and not self.locked[i]:
                    self.keypad_input[i] = ''
                    self.kp_feedback = ("neutral", now + 0.25)
                    # atualizar keypad_value
                    self._update_keypad_value()
                    return
            # nada para deletar
            return

        # CLR: limpa apenas os slots não-locked
        if key == "CLR":
            changed = False
            for i in range(len(self.keypad_input)):
                if not self.locked[i] and self.keypad_input[i] != '':
                    self.keypad_input[i] = ''
                    changed = True
            if changed:
                self.kp_feedback = ("neutral", now + 0.25)
                self._update_keypad_value()
            return

        # dígito
        if key.isdigit():
            # encontra primeiro slot vazio (''), que também não deve estar locked
            idx = None
            for i in range(len(self.keypad_input)):
                if self.keypad_input[i] == '' and not self.locked[i]:
                    idx = i
                    break
            if idx is None:
                # nenhum slot disponível
                return

            expected_digit = self.first_secret[idx]  # compara com os 3 primeiros dígitos

            # coloca temporariamente para feedback visual
            self.keypad_input[idx] = key
            self._update_keypad_value()

            if key == expected_digit:
                # dígito correto: marca locked e envia 0xFF
                self.locked[idx] = True
                self.kp_feedback = ("success", now + 0.35)
                try:
                    threading.Thread(target=self._send_result_thread, args=(True,), daemon=True).start()
                except Exception as e:
                    print("[TX] Erro ao iniciar thread de envio (correct):", e)

                # se todos os três estão locked -> sequência completa
                if all(self.locked):
                    self.kp_feedback = ("sequence_ok", now + 1.0)
                    # daqui a 1s vamos para a introdução do segundo jogo
                    self.root.after(800, self.start_second_intro)
                return
            else:
                # dígito incorreto: sinaliza, envia 0x00 e remove o dígito após curto delay
                self.kp_feedback = ("error", now + 0.45)
                try:
                    threading.Thread(target=self._send_result_thread, args=(False,), daemon=True).start()
                except Exception as e:
                    print("[TX] Erro ao iniciar thread de envio (incorrect):", e)

                # usar after para remover o dígito (evita manipular estado desde outra thread)
                def remove_bad_slot(i=idx):
                    # apenas remove se posição não estiver locked e o valor ainda for o digit errado
                    if 0 <= i < len(self.keypad_input) and not self.locked[i]:
                        self.keypad_input[i] = ''
                        self._update_keypad_value()
                self.root.after(180, remove_bad_slot)
                return

    def _update_keypad_value(self):
        s = ''.join(self.keypad_input)
        if '' not in self.keypad_input:
            try:
                self.keypad_value = int(s)
            except:
                self.keypad_value = None
        else:
            self.keypad_value = None


    # -------- Flow control --------
    def start_intro(self):
        self.screen = 'intro'
        self.typing_pos = 0
        self.typing_running = True
        self.canvas.delete("all")
        self.root.after(self.typing_speed_ms, self._typing_step)

    def start_intro_transition(self):
        """Transição suave: tela escurece e depois volta levemente antes de trocar de tela."""
        if getattr(self, "_fade_item", None):
            return

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        fade_steps = 10
        delay = 20  # ms entre frames → total ~200ms

        # cria o retângulo escuro transparente
        self._fade_item = self.canvas.create_rectangle(
            0, 0, w, h,
            fill=THEME["bg"],
            outline=""
        )
        self.canvas.itemconfig(self._fade_item, stipple="gray75")
        self.canvas.tag_raise(self._fade_item)

        def fade_in(step=0):
            """Escurece gradualmente."""
            alpha = int(255 * (step / fade_steps))
            color = f"#{alpha:02x}{alpha:02x}{alpha:02x}"
            self.canvas.itemconfig(self._fade_item, fill=color)
            if step < fade_steps:
                self.root.after(delay, lambda: fade_in(step + 1))
            else:
                self.root.after(80, fade_out)  # pequena pausa no escuro

        def fade_out(step=fade_steps):
            """Clareia gradualmente e troca de tela."""
            alpha = int(255 * (step / fade_steps))
            color = f"#{alpha:02x}{alpha:02x}{alpha:02x}"
            self.canvas.itemconfig(self._fade_item, fill=color)
            if step > 0:
                self.root.after(delay, lambda: fade_out(step - 1))
            else:
                self.canvas.delete(self._fade_item)
                self._fade_item = None
                self.start_intro()

        fade_in()

    def _typing_step(self):
        if not self.typing_running:
            return
        self.typing_pos += 1
        if self.typing_pos > len(self.intro_text):
            self.typing_running = False
            return
        self.draw_intro_text(self.intro_text[:self.typing_pos])
        self.root.after(self.typing_speed_ms, self._typing_step)

    def finish_typing(self):
        self.typing_running = False
        self.typing_pos = len(self.intro_text)
        self.draw_intro_text(self.intro_text)

    def start_game(self):
        self.screen = 'game'
        self.canvas.delete("all")

    def start_second_intro(self):
        # pequena introdução antes do segundo jogo
        self.screen = 'intro2'
        self.canvas.delete("all")

    def start_second_game(self):
        self.screen = 'game2'
        self.canvas.delete("all")


    # -------- Draw --------
    def draw_splash(self):
        self.canvas.delete("all")
        if self.splash_photo:
            self.canvas.create_image(0, 0, anchor="nw", image=self.splash_photo)
        else:
            self.canvas.create_rectangle(0,0,int(self.canvas['width']), int(self.canvas['height']), fill=THEME["panel"], outline="")
            self.canvas.create_text(int(self.canvas['width'])//2, int(self.canvas['height'])//2, text="ENIGMA DUO", font=self.ft_big, fill=THEME["accent"])

    def draw_intro_text(self, text):
        self.canvas.delete("all")

        # Pega o tamanho atual do canvas
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        # Centro
        cx = w // 2
        cy = h // 2

        # Dimensões do painel
        panel_w = 1040
        panel_h = 640
        x0 = cx - panel_w // 2
        y0 = cy - panel_h // 2
        x1 = cx + panel_w // 2
        y1 = cy + panel_h // 2

        # Retângulo central
        self.canvas.create_rectangle(x0, y0, x1, y1, fill=THEME["panel"], outline=THEME["card"])

        # Título (em cima, alinhado à esquerda dentro do painel)
        self.canvas.create_text(x0 + 20, y0 + 20, anchor="w", text="Introdução",
                                font=self.ft_med, fill=THEME["text"])

        # Texto principal (centralizado)
        self.canvas.create_text(cx, cy, text=text, font=self.ft_game_like,
                                fill=THEME["accent"], width=panel_w - 100, justify="center")

        # Texto inferior (depende do estado)
        footer_text = "(Pressione ENTER para pular)" if self.typing_running else "Pressione ENTER para iniciar o enigma"
        self.canvas.create_text(cx, y1 - 30, text=footer_text, font=self.ft_small,
                                fill=THEME["muted" if self.typing_running else "text"])

    def draw_intro2(self):
        # desenho simples da introdução ao segundo jogo (texto está em self.intro2_text)
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        cx = w // 2
        cy = h // 2

        panel_w = 1000
        panel_h = 420
        x0 = cx - panel_w // 2
        y0 = cy - panel_h // 2
        x1 = cx + panel_w // 2
        y1 = cy + panel_h // 2

        self.canvas.create_rectangle(x0, y0, x1, y1, fill=THEME["panel"], outline=THEME["card"])
        self.canvas.create_text(x0 + 20, y0 + 20, anchor="w", text="Próximo Enigma", font=self.ft_med, fill=THEME["text"])
        self.canvas.create_text(cx, cy - 20, text=self.intro2_text, font=self.ft_sub, width=panel_w-120, justify="center", fill=THEME["accent"])
        self.canvas.create_text(cx, y1 - 30, text="Pressione ENTER para continuar", font=self.ft_small, fill=THEME["muted"])

    def draw_game(self):
        # clear e draws centralizados com keypad à direita (jogo 1)
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        # header
        header_h = 60
        self.canvas.create_rectangle(0, 0, w, header_h, fill=THEME["panel"], outline="")
        status_text = f"Porta: {PORT}  |  Conexão: {'OK' if state.get('serial_ok') else 'NÃO'}"
        self.canvas.create_text(20, header_h//2, anchor="w",
                                text=status_text, font=self.ft_small, fill=THEME["text"])

        # define área esquerda/direita
        content_y0 = header_h + 20
        content_y1 = h - 40
        content_h = content_y1 - content_y0
        left_w = int(w * 0.5) - 20   # margem
        right_w = w - left_w - 40

        # painel esquerdo (onde fica o círculo)
        panel_left_x0 = 20
        panel_left_x1 = panel_left_x0 + left_w
        panel_left_y0 = content_y0
        panel_left_y1 = content_y1
        self.canvas.create_rectangle(panel_left_x0, panel_left_y0, panel_left_x1, panel_left_y1,
                                     fill=THEME["panel"], outline=THEME["card"])

        # centro do painel esquerdo
        cx = panel_left_x0 + left_w // 2
        cy = panel_left_y0 + content_h // 2 - 20

        with state_lock:
            err = state.get("error")

        if err is None:
            self.canvas.create_text(cx, cy, text="Aguardando leitura...", font=self.ft_med, fill=THEME["muted"])
        else:
            bucket, label = qualitative_bucket(err)
            color = bucket_color(bucket)

            # big circle
            r = min(120, int(min(left_w, content_h) * 0.35))
            self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill=color, outline="")

            # label
            self.canvas.create_text(cx, cy, text=label, font=self.ft_big, fill=THEME["text"])

            # hint
            if bucket == 0:
                hint = "Vocês acharam a distância correta! Digite o número correspondente"
            elif bucket == 1:
                hint = "Um leve ruído ecoa... vocês estão muito próximos."
            elif bucket == 2:
                hint = "O ar parece vibrar... quase lá."
            else:
                hint = "Silêncio absoluto... nada reage."
            self.canvas.create_text(cx, cy + int(r*0.9) + 48, text=hint, font=self.ft_med, fill=THEME["hint"])

        # painel direito (keypad)
        pad = 12
        panel_right_x0 = panel_left_x1 + 20
        panel_right_x1 = w - 20
        panel_right_y0 = panel_left_y0
        panel_right_y1 = panel_left_y1
        self.canvas.create_rectangle(panel_right_x0, panel_right_y0, panel_right_x1, panel_right_y1,
                                     fill=THEME["panel"], outline=THEME["card"])

        # --- keypad: centered na área direita ---
        panel_right_width = panel_right_x1 - panel_right_x0
        panel_right_height = panel_right_y1 - panel_right_y0

        # dimensões do teclado (ajustáveis)
        cols = 3
        rows = 4
        spacing = 12
        # btn_w tenta usar espaço disponível, com valor máximo
        btn_w = min(100, int((panel_right_width - 80) / cols))
        btn_h = 56

        # total da grade
        total_grid_w = cols * btn_w + (cols - 1) * spacing
        total_grid_h = rows * btn_h + (rows - 1) * spacing

        # display acima do grid: largura baseada no grid + margens
        display_h = 60
        display_w = min(panel_right_width - 40, total_grid_w + 40)

        # espaço entre display e grid
        gap_display_grid = 20

        # calcular origem para centralizar todo o bloco (display + gap + grid)
        block_h = display_h + gap_display_grid + total_grid_h
        block_y0 = panel_right_y0 + max( (panel_right_height - block_h) // 2, 10 )

        # centraliza horizontalmente
        block_x_center = panel_right_x0 + panel_right_width // 2

        # display posicionado centrado
        display_x0 = int(block_x_center - display_w // 2)
        display_x1 = int(block_x_center + display_w // 2)
        display_y0 = block_y0
        display_y1 = display_y0 + display_h

        # desenha display (campo de entrada)
        self.canvas.create_rectangle(display_x0, display_y0, display_x1, display_y1,
                                     fill=THEME["bg"], outline=THEME["card"])
        display_text = ''.join(self.keypad_input)
        self.canvas.create_text((display_x0+display_x1)//2, display_y0 + display_h//2,
                                text=display_text, font=self.ft_big, fill=THEME["accent"])

        # desenha feedback do keypad (se existir)
        if self.kp_feedback:
            ftype, until = self.kp_feedback
            if time.time() < until:
                if ftype == "success":
                    # pequeno indicador verde no canto direito do display
                    cx_fb = display_x1 - 24
                    cy_fb = display_y0 + display_h//2
                    self.canvas.create_oval(cx_fb-12, cy_fb-12, cx_fb+12, cy_fb+12, fill=THEME["success"], outline="")
                elif ftype == "error":
                    # flash vermelho semitransparente sobre display — usando stipple
                    # cor vermelha tema (usamos um vermelho compatível)
                    self.canvas.create_rectangle(display_x0, display_y0, display_x1, display_y1,
                                                 fill="#c94b4b", stipple="gray50", outline="")
                elif ftype == "sequence_ok":
                    # mensagem grande de sucesso sobre o painel direito (centrada acima do grid)
                    self.canvas.create_text(block_x_center, display_y1 - 100,
                                            text="Sequência correta!", font=self.ft_med, fill=THEME["success"])
                # 'neutral' no momento não desenha nada especial
            else:
                # tempo expirou, limpar
                self.kp_feedback = None

        # calcula origem da grade centralizada
        grid_x0 = int(block_x_center - total_grid_w // 2)
        grid_y0 = display_y1 + gap_display_grid

        labels = [
            ["1","2","3"],
            ["4","5","6"],
            ["7","8","9"],
            ["CLR","0","DEL"]
        ]

        for r, row in enumerate(labels):
            for c, lab in enumerate(row):
                x0 = grid_x0 + c * (btn_w + spacing)
                y0 = grid_y0 + r * (btn_h + spacing)
                x1 = x0 + btn_w
                y1 = y0 + btn_h
                tag = f"kp_btn_{lab}"
                # botão (retângulo com tag)
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=THEME["card"], outline="", tags=(tag,))
                # label centralizado no botão (mesma tag para clique)
                self.canvas.create_text((x0+x1)//2, (y0+y1)//2, text=lab, font=self.ft_med, fill=THEME["text"], tags=(tag,))


    def draw_game2(self):
        # jogo 2: à esquerda imagem (symbols), à direita keypad com os 3 dígitos já preenchidos (locked)
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        # header
        header_h = 60
        self.canvas.create_rectangle(0, 0, w, header_h, fill=THEME["panel"], outline="")
        status_text = f"Porta: {PORT}  |  Conexão: {'OK' if state.get('serial_ok') else 'NÃO'}"
        self.canvas.create_text(20, header_h//2, anchor="w",
                                text=status_text, font=self.ft_small, fill=THEME["text"])

        # define área esquerda/direita
        content_y0 = header_h + 20
        content_y1 = h - 40
        content_h = content_y1 - content_y0
        left_w = int(w * 0.5) - 20   # margem
        right_w = w - left_w - 40

        # painel esquerdo (imagem)
        panel_left_x0 = 20
        panel_left_x1 = panel_left_x0 + left_w
        panel_left_y0 = content_y0
        panel_left_y1 = content_y1
        self.canvas.create_rectangle(panel_left_x0, panel_left_y0, panel_left_x1, panel_left_y1,
                                     fill=THEME["panel"], outline=THEME["card"])

        # desenhar imagem dos símbolos, escalando para caber no painel esquerdo
        if self.symbols_img:
            try:
                img = self.symbols_img.copy()
                target_w = panel_left_x1 - panel_left_x0 - 20
                target_h = panel_left_y1 - panel_left_y0 - 20
                # manter proporção e "fit" (ajusta para caber)
                img_ratio = img.width / img.height
                if img_ratio > (target_w / target_h):
                    new_w = target_w
                    new_h = int(new_w / img_ratio)
                else:
                    new_h = target_h
                    new_w = int(img_ratio * new_h)
                resized = img.resize((new_w, new_h), Image.LANCZOS)
                photo = ImageTk.PhotoImage(resized)
                # centralizar dentro do painel esquerdo
                px = panel_left_x0 + (left_w // 2)
                py = panel_left_y0 + (content_h // 2)
                self.canvas.create_image(px, py, image=photo, anchor="center")
                # prevenir garbage-collection da PhotoImage (associar ao objeto)
                self._last_symbols_photo = photo
            except Exception as e:
                print("Erro ao desenhar symbols_img:", e)
        else:
            self.canvas.create_text(panel_left_x0 + left_w//2, panel_left_y0 + content_h//2,
                                    text="(Imagem dos símbolos ausente)\nColoque symbols.jpg na pasta", font=self.ft_sub,
                                    fill=THEME["muted"], justify="center")

        # painel direito (keypad) - reutiliza desenho similar ao draw_game, mas display mostra os 3 dígitos preenchidos
        pad = 12
        panel_right_x0 = panel_left_x1 + 20
        panel_right_x1 = w - 20
        panel_right_y0 = panel_left_y0
        panel_right_y1 = panel_left_y1
        self.canvas.create_rectangle(panel_right_x0, panel_right_y0, panel_right_x1, panel_right_y1,
                                     fill=THEME["panel"], outline=THEME["card"])

        panel_right_width = panel_right_x1 - panel_right_x0
        panel_right_height = panel_right_y1 - panel_right_y0

        cols = 3
        rows = 4
        spacing = 12
        btn_w = min(100, int((panel_right_width - 80) / cols))
        btn_h = 56
        total_grid_w = cols * btn_w + (cols - 1) * spacing
        total_grid_h = rows * btn_h + (rows - 1) * spacing
        display_h = 60
        display_w = min(panel_right_width - 40, total_grid_w + 40)
        gap_display_grid = 20
        block_h = display_h + gap_display_grid + total_grid_h
        block_y0 = panel_right_y0 + max( (panel_right_height - block_h) // 2, 10 )
        block_x_center = panel_right_x0 + panel_right_width // 2
        display_x0 = int(block_x_center - display_w // 2)
        display_x1 = int(block_x_center + display_w // 2)
        display_y0 = block_y0
        display_y1 = display_y0 + display_h

        # display mostra os 3 dígitos já preenchidos (imutáveis)
        self.canvas.create_rectangle(display_x0, display_y0, display_x1, display_y1,
                                     fill=THEME["bg"], outline=THEME["card"])
        display_text = ''.join(self.keypad_input)
        self.canvas.create_text((display_x0+display_x1)//2, display_y0 + display_h//2,
                                text=display_text, font=self.ft_big, fill=THEME["accent"])

        # desenha o grid (os botões ainda aparecem, mas não permitirão sobrescrever digits locked)
        grid_x0 = int(block_x_center - total_grid_w // 2)
        grid_y0 = display_y1 + gap_display_grid

        labels = [
            ["1","2","3"],
            ["4","5","6"],
            ["7","8","9"],
            ["CLR","0","DEL"]
        ]

        for r, row in enumerate(labels):
            for c, lab in enumerate(row):
                x0 = grid_x0 + c * (btn_w + spacing)
                y0 = grid_y0 + r * (btn_h + spacing)
                x1 = x0 + btn_w
                y1 = y0 + btn_h
                tag = f"kp_btn_{lab}"
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=THEME["card"], outline="", tags=(tag,))
                self.canvas.create_text((x0+x1)//2, (y0+y1)//2, text=lab, font=self.ft_med, fill=THEME["text"], tags=(tag,))


    # -------- Update --------
    def update_ui(self):
        if self.screen == 'splash':
            self.draw_splash()
        elif self.screen == 'intro':
            if not self.typing_running:
                self.draw_intro_text(self.intro_text)
        elif self.screen == 'game':
            self.draw_game()
        elif self.screen == 'intro2':
            self.draw_intro2()
        elif self.screen == 'game2':
            self.draw_game2()
        if self.running:
            self.root.after(UI_UPDATE_MS, self.update_ui)

    def on_close(self):
        self.running = False
        with state_lock:
            state["running"] = False
        try:
            root.destroy()
        except:
            sys.exit(0)


# -------- start ----------
if __name__ == "__main__":
    reader = SerialReader(PORT, BAUDRATE)
    reader.start()
    root = tk.Tk()
    app = EnigmaDuoApp(root)
    try:
        root.mainloop()
    finally:
        reader.stop()
        with state_lock:
            state["running"] = False
        time.sleep(0.05)
