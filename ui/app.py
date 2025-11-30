# ui/app.py
import tkinter as tk
from tkinter import font
import threading, time, sys
from PIL import Image, ImageTk
import os

from constants import THEME, PORT, UI_UPDATE_MS
import serial_comm as sc
from helpers import qualitative_bucket, bucket_color

from . import draw
from .keypad import KeypadManager

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
        # instancia o manager do keypad (usa self.first_secret definido em _setup_game_state)
        self.keypad = KeypadManager(self)
        # inicializa o keypad com a sequência atual (6 dígitos) e ativa faixa do 1º jogo
        self.keypad.set_secrets(self.secret_sequence)   # reserva e reseta estado visual
        self.keypad.set_active_range(0, 3)              # jogo 1 => índices 0..2 (end exclusivo = 3)

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

            img.thumbnail((cw, ch), Image.LANCZOS)
            w, h = img.size

            if w < cw or h < ch:
                scale = max(cw / w, ch / h)
                img = img.resize((int(w*scale), int(h*scale)), Image.LANCZOS)

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
        self.intro2_typing_pos = 0
        self.intro2_typing_running = False

    def _setup_game_state(self):
        self.running = True
        self.secret_sequence = "000000"
        self.first_secret = self.secret_sequence[:3]
        self.second_secret = self.secret_sequence[3:6]

        self.keypad_value = None
        self.symbols_img = None
        symbols_path = os.path.join(os.path.dirname(__file__), "symbols.png")
        if os.path.exists(symbols_path):
            try:
                self.symbols_img = Image.open(symbols_path).convert("RGBA")
            except Exception as e:
                print("⚠️ Não foi possível carregar symbols.jpg:", e)

        self.intro2_text = (
            "Vocês decifraram um dos enigmas! Algo mudou no cofre — "
            "reparem com atenção: agora é o Enigma dos Símbolos. "
            "Uma seta apontará para símbolos; interpretem o padrão e respondam."
        )

    # ----------------- eventos / delegação para keypad -----------------
    def on_key(self, event):
        key = event.keysym.lower()
        if self.screen in ('game', 'game2'):
            # tratar teclado do keypad
            if key.isdigit() and len(key) == 1:
                self.keypad.handle_keypress(key)
                return
            if key == "backspace":
                self.keypad.handle_keypress("DEL")
                return
            if key == "c":
                self.keypad.handle_keypress("CLR")
                with sc.state_lock:
                    sc.state["error"] = None
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
                if self.intro2_typing_running:
                    self.finish_typing()
                else:
                    self.start_second_game()
            elif self.screen == 'game':
                pass
            elif self.screen == 'game2':
                pass
        elif key == 's':
            with sc.state_lock:
                sc.state["sim_on"] = not sc.state.get("sim_on", False)
            if sc.state["sim_on"]:
                threading.Thread(target=sc.simulate_sequence, daemon=True).start()
        elif key == 'q':
            self.on_close()
        elif key == 'r':
            self.reset()            

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
                        self.keypad.handle_keypress(key)
                        return
        except Exception as e:
            print("Erro _on_canvas_click:", e)

    def _update_keypad_value(self):
        self.keypad._update_keypad_value()
        self.keypad_value = self.keypad.keypad_value

    # -------- Flow control --------
    def start_intro(self):
        self.screen = 'intro'
        self.typing_pos = 0
        self.typing_running = True
        self.canvas.delete("all")
        self.root.after(self.typing_speed_ms, self._typing_step)

    def start_intro_transition(self):
        if getattr(self, "_fade_item", None):
            return

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        fade_steps = 10
        delay = 20
        self._fade_item = self.canvas.create_rectangle(0, 0, w, h, fill=THEME["bg"], outline="")
        self.canvas.itemconfig(self._fade_item, stipple="gray75")
        self.canvas.tag_raise(self._fade_item)

        def fade_in(step=0):
            alpha = int(255 * (step / fade_steps))
            color = f"#{alpha:02x}{alpha:02x}{alpha:02x}"
            self.canvas.itemconfig(self._fade_item, fill=color)
            if step < fade_steps:
                self.root.after(delay, lambda: fade_in(step + 1))
            else:
                self.root.after(80, fade_out)

        def fade_out(step=fade_steps):
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
        if self.screen == 'intro':
            if not self.typing_running:
                return
            self.typing_pos += 1
            if self.typing_pos > len(self.intro_text):
                self.typing_running = False
                return
            draw.draw_intro_text(self, self.intro_text[:self.typing_pos])
            self.root.after(self.typing_speed_ms, self._typing_step)

        elif self.screen == 'intro2':
            if not self.intro2_typing_running:
                return
            self.intro2_typing_pos += 1
            if self.intro2_typing_pos > len(self.intro2_text):
                self.intro2_typing_running = False
                return
            draw.draw_intro2(self, self.intro2_text[:self.intro2_typing_pos])
            self.root.after(self.typing_speed_ms, self._typing_step)

        else:
            return


    def finish_typing(self):
        if self.screen == 'intro':
            self.typing_running = False
            self.typing_pos = len(self.intro_text)
            draw.draw_intro_text(self, self.intro_text)
        elif self.screen == 'intro2':
            self.intro2_typing_running = False
            self.intro2_typing_pos = len(self.intro2_text)
            draw.draw_intro2(self, self.intro2_text)


    def start_game(self):
        self.screen = 'game'
        # ativa faixa do 1º jogo (slots 0..2)
        self.keypad.set_active_range(0, 3)
        self.canvas.delete("all")


    def start_second_intro(self):
        self.screen = 'intro2'
        self.canvas.delete("all")
        self.intro2_typing_pos = 0
        self.intro2_typing_running = True
        self.root.after(self.typing_speed_ms, self._typing_step)

    def start_second_game(self):
        self.screen = 'game2'
        # ativa faixa do 2º jogo (slots 3..5)
        self.keypad.set_active_range(3, 6)
        self.canvas.delete("all")


    # -------- Draw delegations --------
    def draw_splash(self):
        draw.draw_splash(self)

    def draw_intro_text(self, text):
        draw.draw_intro_text(self, text)

    def draw_intro2(self, text):
        draw.draw_intro2(self, text)

    def draw_game(self):
        draw.draw_game(self)

    def draw_game2(self):
        draw.draw_game2(self)

    # -------- Update loop --------
    def update_ui(self):
        with sc.state_lock:
            newseq = sc.state.pop("target_digits", None)
        if newseq:
            # garante string de 6 chars (trunca/pad com zeros se necessário)
            newseq = str(newseq).strip()[:6].ljust(6, "0")
            print("🔐 Nova sequência recebida:", newseq)
            self.secret_sequence = newseq
            self.first_secret = newseq[:3]
            self.second_secret = newseq[3:6]

            # atualiza keypad (reseta entradas/locks) e ativa faixa do 1º jogo
            self.keypad.set_secrets(self.secret_sequence)
            self.keypad.set_active_range(0, 3)


        # --- 2) Renderização normal da UI ---
        if self.screen == 'splash':
            self.draw_splash()

        elif self.screen == 'intro':
            if not self.typing_running:
                self.draw_intro_text(self.intro_text)

        elif self.screen == 'game':
            self.draw_game()

        elif self.screen == 'intro2':
            if not self.intro2_typing_running:
                self.draw_intro2(self.intro2_text)

        elif self.screen == 'game2':
            self.draw_game2()

        # --- 3) Loop contínuo ---
        if self.running:
            self.root.after(UI_UPDATE_MS, self.update_ui)

    def on_close(self):
        self.running = False
        with sc.state_lock:
            sc.state["running"] = False
        try:
            self.root.destroy()
        except:
            sys.exit(0)

    def reset(self):
        print("[APP] Resetando jogo...")
        # 1) parar animações/typings ativas
        try:
            self.typing_running = False
            self.typing_pos = 0
            self.intro2_typing_running = False
            self.intro2_typing_pos = 0
        except Exception:
            pass
        # 2) voltar à tela inicial (splash)
        self.screen = 'splash'
        # 3) limpar/zerar a sequência e secrets locais
        self.secret_sequence = "000000"
        self.first_secret = self.secret_sequence[:3]
        self.second_secret = self.secret_sequence[3:6]
        # 4) resetar estado do keypad através da API do KeypadManager
        # set_secrets deve resetar estado visual/entradas internas (conforme comentário anterior)
        self.keypad.set_secrets(self.secret_sequence)
        # reativa faixa do 1º jogo (slots 0..2) por padrão
        self.keypad.set_active_range(0, 3)
        # 5) limpar valores locais relacionados ao keypad / UI
        self.keypad_value = None
        # 6) limpar estados no serial_comm (se houver)
        try:
            with sc.state_lock:
                # apagar sequência alvo pendente vindo da serial (se existir)
                sc.state.pop("target_digits", None)
                # limpar erro/sinal e simulação
                sc.state["error"] = None
                sc.state["sim_on"] = False
        except Exception as e:
            print("[RESET] Aviso: não foi possível limpar estado em serial_comm:", e)
        # 7) redesenha tela inicial e garante foco
        try:
            self.canvas.delete("all")
            self.draw_splash()
        except Exception as e:
            print("[RESET] Aviso ao redesenhar splash:", e)
        try:
            # devolve foco para a janela (receberá teclas novamente)
            self.root.focus_set()
        except Exception:
            pass
        print("[APP] Reset completo.")

