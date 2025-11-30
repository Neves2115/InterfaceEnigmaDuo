# ui/draw.py
import time
from PIL import Image, ImageTk
import os
from constants import THEME, PORT
import serial_comm as sc
from helpers import qualitative_bucket, bucket_color

# Cada função recebe o objeto app (instância de EnigmaDuoApp),
# e desenha no app.canvas usando o state e o keypad.

def draw_splash(app):
    app.canvas.delete("all")
    if getattr(app, "splash_photo", None):
        app.canvas.create_image(0, 0, anchor="nw", image=app.splash_photo)
    else:
        app.canvas.create_rectangle(0,0,int(app.canvas['width']), int(app.canvas['height']), fill=THEME["panel"], outline="")
        app.canvas.create_text(int(app.canvas['width'])//2, int(app.canvas['height'])//2, text="ENIGMA DUO", font=app.ft_big, fill=THEME["accent"])

def draw_intro_text(app, text):
    app.canvas.delete("all")
    w = app.canvas.winfo_width()
    h = app.canvas.winfo_height()
    cx = w // 2
    cy = h // 2
    panel_w = 1040
    panel_h = 640
    x0 = cx - panel_w // 2
    y0 = cy - panel_h // 2
    x1 = cx + panel_w // 2
    y1 = cy + panel_h // 2
    app.canvas.create_rectangle(x0, y0, x1, y1, fill=THEME["panel"], outline=THEME["card"])
    app.canvas.create_text(x0 + 20, y0 + 20, anchor="w", text="Introdução",
                            font=app.ft_med, fill=THEME["text"])
    app.canvas.create_text(cx, cy, text=text, font=app.ft_game_like,
                            fill=THEME["accent"], width=panel_w - 100, justify="center")
    footer_text = "(Pressione ENTER para pular)" if app.typing_running else "Pressione ENTER para iniciar o enigma"
    app.canvas.create_text(cx, y1 - 30, text=footer_text, font=app.ft_small,
                            fill=THEME["muted" if app.typing_running else "text"])

# em ui/draw.py

def draw_intro2(app, text):
    canvas = app.canvas
    canvas.delete("all")
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    cx = w // 2
    cy = h // 2

    panel_w = 1000
    panel_h = 420
    x0 = cx - panel_w // 2
    y0 = cy - panel_h // 2
    x1 = cx + panel_w // 2
    y1 = cy + panel_h // 2

    canvas.create_rectangle(x0, y0, x1, y1, fill=THEME["panel"], outline=THEME["card"])
    canvas.create_text(x0 + 20, y0 + 20, anchor="w", text="Próximo Enigma", font=app.ft_med, fill=THEME["text"])
    canvas.create_text(cx, cy - 20, text=text, font=app.ft_game_like, width=panel_w-120, justify="center", fill=THEME["accent"])
    canvas.create_text(cx, y1 - 30, text="Pressione ENTER para continuar", font=app.ft_small, fill=THEME["muted"])


def draw_game(app):
    app.canvas.delete("all")
    w = app.canvas.winfo_width()
    h = app.canvas.winfo_height()

    # header
    header_h = 60
    app.canvas.create_rectangle(0, 0, w, header_h, fill=THEME["panel"], outline="")
    status_text = f"Porta: {PORT}  |  Conexão: {'OK' if sc.state.get('serial_ok') else 'NÃO'}"
    app.canvas.create_text(20, header_h//2, anchor="w",
                            text=status_text, font=app.ft_small, fill=THEME["text"])

    heart_h = 32
    spacing = 8
    margin_right = 16
    # calc posição inicial (lado direito)
    # desenhar com base na largura 'w'
    total_w = (heart_h * getattr(app, "max_lives", 3)) + spacing * (getattr(app, "max_lives", 3) - 1)
    start_x = w - margin_right - (heart_h // 2) - total_w + (heart_h // 2)
    y = header_h // 2

    for i in range(getattr(app, "max_lives", 3)):
        x = start_x + i * (heart_h + spacing)
        # escolher imagem preenchida ou vazia
        if hasattr(app, "lives") and i < getattr(app, "lives", 0):
            # filled
            if getattr(app, "_heart_full_photo", None):
                app.canvas.create_image(x, y, image=app._heart_full_photo, anchor="center")
        else:
            # empty
            if getattr(app, "_heart_empty_photo", None):
                app.canvas.create_image(x, y, image=app._heart_empty_photo, anchor="center")

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
    app.canvas.create_rectangle(panel_left_x0, panel_left_y0, panel_left_x1, panel_left_y1,
                                 fill=THEME["panel"], outline=THEME["card"])

    # centro do painel esquerdo
    cx = panel_left_x0 + left_w // 2
    cy = panel_left_y0 + content_h // 2 - 20

    with sc.state_lock:
        err = sc.state.get("error")

    if err is None:
        app.canvas.create_text(cx, cy, text="Aguardando leitura...", font=app.ft_med, fill=THEME["muted"])
    else:
        bucket, label = qualitative_bucket(err)
        color = bucket_color(bucket)

        # big circle
        r = min(120, int(min(left_w, content_h) * 0.35))
        app.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill=color, outline="")

        # label
        app.canvas.create_text(cx, cy, text=label, font=app.ft_big, fill=THEME["text"])

        progress = 1.0 - min(max(err, 0.0), 30) / 30
        progress = max(0.0, min(1.0, progress))

        # dimensões da barra: largura relativa ao painel esquerdo, posicionada abaixo do círculo
        bar_w = int(left_w * 0.75)
        bar_h = 18
        bar_x0 = cx - bar_w // 2
        bar_y0 = cy + int(r * 0.9) + 80   # ligeiramente abaixo do hint area
        bar_x1 = bar_x0 + bar_w
        bar_y1 = bar_y0 + bar_h

        # fundo da barra (track)
        app.canvas.create_rectangle(bar_x0, bar_y0, bar_x1, bar_y1,
                                    fill=THEME["card"], outline="")

        # preenchimento proporcional
        fill_w = int(bar_w * progress)
        if fill_w > 0:
            fill_color = color if (bucket is not None) else THEME["accent"]
            app.canvas.create_rectangle(bar_x0, bar_y0, bar_x0 + fill_w, bar_y1,
                                        fill=fill_color, outline="")

        # contorno fino
        app.canvas.create_rectangle(bar_x0, bar_y0, bar_x1, bar_y1, outline=THEME["text"], width=1)

        # hint
        if bucket == 0:
            hint = "Vocês acharam a distância correta! Digite o número correspondente"
        elif bucket == 1:
            hint = "Um leve ruído ecoa... vocês estão muito próximos."
        elif bucket == 2:
            hint = "Ainda não... Tentem mover um pouco mais."
        else:
            hint = "Silêncio absoluto... nada reage."
        app.canvas.create_text(cx, cy + int(r*0.9) + 48, text=hint, font=app.ft_med, fill=THEME["hint"])

    # painel direito (keypad)
    pad = 12
    panel_right_x0 = panel_left_x1 + 20
    panel_right_x1 = w - 20
    panel_right_y0 = panel_left_y0
    panel_right_y1 = panel_left_y1
    app.canvas.create_rectangle(panel_right_x0, panel_right_y0, panel_right_x1, panel_right_y1,
                                 fill=THEME["panel"], outline=THEME["card"])

    panel_right_width = panel_right_x1 - panel_right_x0
    panel_right_height = panel_right_y1 - panel_right_y0

    # dimensões do teclado (ajustáveis)
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

    # desenha display (campo de entrada)
    app.canvas.create_rectangle(display_x0, display_y0, display_x1, display_y1,
                                 fill=THEME["bg"], outline=THEME["card"])
    display_text = ''.join(app.keypad.keypad_input)
    app.canvas.create_text((display_x0+display_x1)//2, display_y0 + display_h//2,
                            text=display_text, font=app.ft_big, fill=THEME["accent"])

    # desenha feedback do keypad (se existir)
    if app.keypad.kp_feedback:
        ftype, until = app.keypad.kp_feedback
        if time.time() < until:
            if ftype == "success":
                cx_fb = display_x1 - 24
                cy_fb = display_y0 + display_h//2
                app.canvas.create_oval(cx_fb-12, cy_fb-12, cx_fb+12, cy_fb+12, fill=THEME["success"], outline="")
            elif ftype == "error":
                app.canvas.create_rectangle(display_x0, display_y0, display_x1, display_y1,
                                             fill="#c94b4b", stipple="gray50", outline="")
            elif ftype == "sequence_ok":
                app.canvas.create_text(block_x_center, display_y1 - 100,
                                        text="Sequência correta!", font=app.ft_med, fill=THEME["success"])
        else:
            app.keypad.kp_feedback = None

    # calcula origem da grade centralizada
    grid_x0 = int(block_x_center - total_grid_w // 2)
    grid_y0 = display_y1 + gap_display_grid

    labels = [
        ["1","2","3"],
        ["4","5","6"],
        ["7","8","9"],
        ["","0",""]
    ]

    for r, row in enumerate(labels):
        for c, lab in enumerate(row):
            x0 = grid_x0 + c * (btn_w + spacing)
            y0 = grid_y0 + r * (btn_h + spacing)
            x1 = x0 + btn_w
            y1 = y0 + btn_h
            tag = f"kp_btn_{lab}"
            if(lab != ""):
                app.canvas.create_rectangle(x0, y0, x1, y1, fill=THEME["card"], outline="", tags=(tag,))
                app.canvas.create_text((x0+x1)//2, (y0+y1)//2, text=lab, font=app.ft_med, fill=THEME["text"], tags=(tag,))

def draw_game_over(app):
    """
    Tela simples de Game Over / tentar novamente.
    Mostra mensagem centralizada e dica para apertar 'R' (reset).
    """
    canvas = app.canvas
    canvas.delete("all")

    w = canvas.winfo_width()
    h = canvas.winfo_height()
    cx = w // 2
    cy = h // 2

    # painel central suave
    panel_w = min(900, int(w * 0.8))
    panel_h = min(300, int(h * 0.35))
    x0 = cx - panel_w // 2
    y0 = cy - panel_h // 2
    x1 = cx + panel_w // 2
    y1 = cy + panel_h // 2

    canvas.create_rectangle(x0, y0, x1, y1, fill=THEME["panel"], outline=THEME["card"], width=2)
    # título
    canvas.create_text(cx, y0 + 100, text="Quase lá! Vamos tentar outra vez?", font=app.ft_title, fill=THEME["text"], anchor="n")

    # instrução para reset
    hint = "Aperte 'R' para tentar novamente"
    canvas.create_text(cx, y1 - 36, text=hint, font=app.ft_med, fill=THEME["accent"])

def draw_victory_transition(app):
    canvas = app.canvas
    canvas.delete("all")
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    cx = w // 2
    cy = h // 2

    panel_w = 1000
    panel_h = 420
    x0 = cx - panel_w // 2
    y0 = cy - panel_h // 2
    x1 = cx + panel_w // 2
    y1 = cy + panel_h // 2

    canvas.create_rectangle(x0, y0, x1, y1, fill=THEME["panel"], outline=THEME["card"])
    canvas.create_text(x0 + 20, y0 + 20, anchor="w", text="Parabéns!", font=app.ft_med, fill=THEME["text"])
    canvas.create_text(cx, cy - 20, text="Vocês conseguiram! Uma incrível recompensa os espera!", font=app.ft_game_like, width=panel_w-120, justify="center", fill=THEME["accent"])
    canvas.create_text(cx, y1 - 30, text="Pressione ENTER para continuar", font=app.ft_small, fill=THEME["muted"])

def draw_final_victory(app):
    canvas = app.canvas
    canvas.delete("all")
    w = canvas.winfo_width()
    h = canvas.winfo_height()

    # Se já carregamos antes, redimensionamos
    if getattr(app, "_victory_img", None):
        img = app._victory_img

        # FORÇAR imagem a ocupar 100% da tela
        resized = img.resize((w, h), Image.LANCZOS)
        app._victory_photo = ImageTk.PhotoImage(resized)

        # Centralizar (como a imagem tem exatamente w×h, não importa o anchor)
        canvas.create_image(0, 0, image=app._victory_photo, anchor="nw")
        return

    # fallback (caso a imagem não carregue)
    canvas.create_text(w//2, h//2, text="VOCÊS CONSEGUIRAM!",
                       font=app.ft_big, fill="white")



def draw_game2(app):
    app.canvas.delete("all")
    w = app.canvas.winfo_width()
    h = app.canvas.winfo_height()

    # header
    header_h = 60
    app.canvas.create_rectangle(0, 0, w, header_h, fill=THEME["panel"], outline="")
    status_text = f"Porta: {PORT}  |  Conexão: {'OK' if sc.state.get('serial_ok') else 'NÃO'}"
    app.canvas.create_text(20, header_h//2, anchor="w",
                            text=status_text, font=app.ft_small, fill=THEME["text"])
    heart_h = 32
    spacing = 8
    margin_right = 16
    # calc posição inicial (lado direito)
    # desenhar com base na largura 'w'
    total_w = (heart_h * getattr(app, "max_lives", 3)) + spacing * (getattr(app, "max_lives", 3) - 1)
    start_x = w - margin_right - (heart_h // 2) - total_w + (heart_h // 2)
    y = header_h // 2

    for i in range(getattr(app, "max_lives", 3)):
        x = start_x + i * (heart_h + spacing)
        # escolher imagem preenchida ou vazia
        if hasattr(app, "lives") and i < getattr(app, "lives", 0):
            # filled
            if getattr(app, "_heart_full_photo", None):
                app.canvas.create_image(x, y, image=app._heart_full_photo, anchor="center")
        else:
            # empty
            if getattr(app, "_heart_empty_photo", None):
                app.canvas.create_image(x, y, image=app._heart_empty_photo, anchor="center")

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
    app.canvas.create_rectangle(panel_left_x0, panel_left_y0, panel_left_x1, panel_left_y1,
                                 fill=THEME["panel"], outline=THEME["card"])

    # desenhar imagem dos símbolos, escalando para caber no painel esquerdo
    if app.symbols_img:
        try:
            img = app.symbols_img.copy()
            target_w = panel_left_x1 - panel_left_x0 - 20
            target_h = panel_left_y1 - panel_left_y0 - 20
            img_ratio = img.width / img.height
            if img_ratio > (target_w / target_h):
                new_w = target_w
                new_h = int(new_w / img_ratio)
            else:
                new_h = target_h
                new_w = int(img_ratio * new_h)
            resized = img.resize((new_w, new_h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(resized)
            px = panel_left_x0 + (left_w // 2)
            py = panel_left_y0 + (content_h // 2)
            app.canvas.create_image(px, py, image=photo, anchor="center")
            app._last_symbols_photo = photo
        except Exception as e:
            print("Erro ao desenhar symbols_img:", e)
    else:
        app.canvas.create_text(panel_left_x0 + left_w//2, panel_left_y0 + content_h//2,
                                text="(Imagem dos símbolos ausente)\nColoque symbols.jpg na pasta", font=app.ft_sub,
                                fill=THEME["muted"], justify="center")

    # painel direito (keypad)
    pad = 12
    panel_right_x0 = panel_left_x1 + 20
    panel_right_x1 = w - 20
    panel_right_y0 = panel_left_y0
    panel_right_y1 = panel_left_y1
    app.canvas.create_rectangle(panel_right_x0, panel_right_y0, panel_right_x1, panel_right_y1,
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

    # display (campo de entrada) - mostra todos os dígitos (6)
    app.canvas.create_rectangle(display_x0, display_y0, display_x1, display_y1,
                                 fill=THEME["bg"], outline=THEME["card"])
    display_text = ''.join(app.keypad.keypad_input)
    app.canvas.create_text((display_x0+display_x1)//2, display_y0 + display_h//2,
                            text=display_text, font=app.ft_big, fill=THEME["accent"])

    # --- agora renderizar feedbacks (success/error/sequence_ok) igual ao jogo 1 ---
    if app.keypad.kp_feedback:
        ftype, until = app.keypad.kp_feedback
        if time.time() < until:
            if ftype == "success":
                # pequeno indicador verde no canto direito do display
                cx_fb = display_x1 - 24
                cy_fb = display_y0 + display_h//2
                app.canvas.create_oval(cx_fb-12, cy_fb-12, cx_fb+12, cy_fb+12, fill=THEME["success"], outline="")
            elif ftype == "error":
                # flash vermelho semitransparente sobre display — usando stipple
                app.canvas.create_rectangle(display_x0, display_y0, display_x1, display_y1,
                                             fill="#c94b4b", stipple="gray50", outline="")
            elif ftype == "sequence_ok":
                app.canvas.create_text(block_x_center, display_y1 - 100,
                                        text="Senha correta!", font=app.ft_med, fill=THEME["success"])
        else:
            # expirar
            app.keypad.kp_feedback = None

    # grid buttons (permanece igual)
    grid_x0 = int(block_x_center - total_grid_w // 2)
    grid_y0 = display_y1 + gap_display_grid

    labels = [
        ["1","2","3"],
        ["4","5","6"],
        ["7","8","9"],
        ["","0",""]
    ]

    for r, row in enumerate(labels):
        for c, lab in enumerate(row):
            x0 = grid_x0 + c * (btn_w + spacing)
            y0 = grid_y0 + r * (btn_h + spacing)
            x1 = x0 + btn_w
            y1 = y0 + btn_h
            tag = f"kp_btn_{lab}"
            if(lab != ""):
                app.canvas.create_rectangle(x0, y0, x1, y1, fill=THEME["card"], outline="", tags=(tag,))
                app.canvas.create_text((x0+x1)//2, (y0+y1)//2, text=lab, font=app.ft_med, fill=THEME["text"], tags=(tag,))

