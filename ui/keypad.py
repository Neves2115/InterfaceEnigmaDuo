# ui/keypad.py
import time
import serial_comm as sc

class KeypadManager:
    """
    Gerencia 6 slots do teclado (0..5). Usa active_range para determinar
    onde o jogador pode digitar (por exemplo 0..3 para jogo 1, 3..6 para jogo 2).
    """

    def __init__(self, app):
        self.app = app
        # 6 slots (inicialmente vazios)
        self.keypad_input = [''] * 6
        self.locked = [False] * 6
        self.kp_feedback = None
        self.keypad_value = None  # opcional
        # secrets: lista de 6 caracteres (strings) que representam a senha recebida via serial
        self.secrets = ['0'] * 6
        # intervalo ativo [start, end) — indices onde o jogador pode digitar
        self.active_start = 0
        self.active_end = 3

    # setar os 6 dígitos da sequência (string ou iterável com 6 chars)
    def set_secrets(self, secret6):
        s = str(secret6)
        s = s.strip()
        if len(s) < 6:
            s = s.ljust(6, '0')
        self.secrets = list(s[:6])
        # reseta estado de digitação ao receber nova sequência
        self.keypad_input = [''] * 6
        self.locked = [False] * 6
        self.kp_feedback = None
        self.keypad_value = None

    # define intervalo ativo [start, end) — start inclusive, end exclusive
    def set_active_range(self, start, end):
        assert 0 <= start <= end <= 6
        self.active_start = start
        self.active_end = end
        # limpa feedback temporário
        self.kp_feedback = None
        # garante que não escreveremos fora do intervalo (mas não limpamos os slots anteriores)
        # se quiser limpar ao mudar faixa, descomente abaixo:
        # for i in range(0, 6):
        #     if not (start <= i < end):
        #         self.keypad_input[i] = ''

    def _update_keypad_value(self):
        s = ''.join(self.keypad_input)
        try:
            # mantém None até que TODOS os 6 estejam preenchidos; adaptável se quiser outro comportamento
            if '' not in self.keypad_input:
                self.keypad_value = int(s)
            else:
                self.keypad_value = None
        except:
            self.keypad_value = None

    def handle_keypress(self, key):
        now = time.time()

        # DEL: remove o último dígito não-locked DENTRO do intervalo ativo
        if key == "DEL":
            for i in range(self.active_end - 1, self.active_start - 1, -1):
                if self.keypad_input[i] != '' and not self.locked[i]:
                    self.keypad_input[i] = ''
                    self.kp_feedback = ("neutral", now + 0.25)
                    self._update_keypad_value()
                    return
            return

        # CLR: limpa apenas os slots não-locked DENTRO do intervalo ativo
        if key == "CLR":
            changed = False
            for i in range(self.active_start, self.active_end):
                if not self.locked[i] and self.keypad_input[i] != '':
                    self.keypad_input[i] = ''
                    changed = True
            if changed:
                self.kp_feedback = ("neutral", now + 0.25)
                self._update_keypad_value()
            return

        # dígito
        if key.isdigit():
            # encontra primeiro slot vazio dentro do intervalo ativo
            idx = None
            for i in range(self.active_start, self.active_end):
                if self.keypad_input[i] == '' and not self.locked[i]:
                    idx = i
                    break
            if idx is None:
                # nenhum slot disponível no intervalo
                return

            # escreve temporariamente para feedback visual
            self.keypad_input[idx] = key
            self._update_keypad_value()

            # --- comportamento para o 1º bloco (digito-a-digito) ---
            if self.active_start == 0 and self.active_end == 3:
                expected_digit = self.secrets[idx]  # compara com os 3 primeiros dígitos
                if key == expected_digit:
                    # acerto por dígito
                    self.locked[idx] = True
                    self.kp_feedback = ("success", now + 0.35)
                    try:
                        sc.send_result_async(True)
                    except Exception as e:
                        print("[TX] Erro ao iniciar envio async (correct):", e)

                    # se todos os três estão locked -> sequência completa
                    if all(self.locked[i] for i in range(self.active_start, self.active_end)):
                        self.kp_feedback = ("sequence_ok", now + 1.0)
                        # aguarda e avança para intro 2
                        self.app.root.after(800, self.app.start_second_intro)
                    return
                else:
                    # dígito incorreto: sinaliza, envia 0x00 e remove o dígito após curto delay
                    self.kp_feedback = ("error", now + 0.45)
                    try:
                        sc.send_result_async(False)
                    except Exception as e:
                        print("[TX] Erro ao iniciar envio async (incorrect):", e)
                    try:
                        if hasattr(self.app, "lose_life"):
                            self.app.lose_life()
                    except Exception:
                        pass

                    def remove_bad_slot(i=idx):
                        if 0 <= i < len(self.keypad_input) and not self.locked[i]:
                            self.keypad_input[i] = ''
                            self._update_keypad_value()
                    self.app.root.after(180, remove_bad_slot)
                    return

            # --- comportamento para o 2º bloco (comparar os 3 juntos) ---
            else:
                # Se ainda há slots vazios no intervalo, aguardamos (nenhuma verificação por dígito)
                if '' in self.keypad_input[self.active_start:self.active_end]:
                    # apenas escrevemos e aguardamos os próximos dígitos
                    return

                # Quando o último dígito do bloco foi preenchido, comparar o conjunto
                entered = ''.join(self.keypad_input[self.active_start:self.active_end])
                expected = ''.join(self.secrets[self.active_start:self.active_end])

                if entered == expected:
                    # sucesso global do bloco (aplica locks e envia ACERTO apenas agora)
                    for i in range(self.active_start, self.active_end):
                        self.locked[i] = True
                    self.kp_feedback = ("sequence_ok", now + 1.0)
                    try:
                        sc.send_result_async(True)
                    except Exception as e:
                        print("[TX] Erro ao iniciar envio async (correct block):", e)
                    self.app.root.after(600, self.app.start_win_transition)
                    return
                else:
                    # erro: sinaliza, envia 0x00 e apaga os três dígitos do bloco após curto delay
                    self.kp_feedback = ("error", now + 0.45)
                    try:
                        sc.send_result_async(False)
                    except Exception as e:
                        print("[TX] Erro ao iniciar envio async (incorrect block):", e)
                    try:
                        if hasattr(self.app, "lose_life"):
                            self.app.lose_life()
                    except Exception:
                        pass

                    def clear_block():
                        for i in range(self.active_start, self.active_end):
                            if not self.locked[i]:
                                self.keypad_input[i] = ''
                        self._update_keypad_value()
                    # manter timing parecido com o primeiro jogo
                    self.app.root.after(300, clear_block)
                    return

    # util para draw
    def display_text(self):
        # retorna os 6 dígitos (poderia formatar com espaços se quiser)
        return ''.join(self.keypad_input)

    def get_state_snapshot(self):
        return {
            "keypad_input": list(self.keypad_input),
            "locked": list(self.locked),
            "kp_feedback": self.kp_feedback,
            "keypad_value": self.keypad_value
        }
