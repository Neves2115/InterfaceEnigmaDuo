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
        # opcional: ao mudar de intervalo, não limpamos slots anteriores (eles permanecem)
        # mas garantir que não haverá escrita fora do intervalo
        # limpa feedback temporário
        self.kp_feedback = None

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

        # DEL: remove o último dígito não-locked dentro do intervalo ativo (procura do fim para o início)
        if key == "DEL":
            for i in range(self.active_end - 1, self.active_start - 1, -1):
                if self.keypad_input[i] != '' and not self.locked[i]:
                    self.keypad_input[i] = ''
                    self.kp_feedback = ("neutral", now + 0.25)
                    self._update_keypad_value()
                    return
            return

        # CLR: limpa apenas os slots não-locked dentro do intervalo ativo
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

            expected_digit = self.secrets[idx]  # compara com o segredo completo (6 dígitos)

            # escreve temporariamente para feedback visual
            self.keypad_input[idx] = key
            self._update_keypad_value()

            if key == expected_digit:
                # acerto
                self.locked[idx] = True
                self.kp_feedback = ("success", now + 0.35)
                try:
                    sc.send_result_async(True)
                except Exception as e:
                    print("[TX] Erro ao iniciar envio async (correct):", e)

                # se todos os do intervalo estiverem locked -> avanço
                all_locked = all(self.locked[i] for i in range(self.active_start, self.active_end))
                if all_locked:
                    self.kp_feedback = ("sequence_ok", now + 1.0)
                    # se era o primeiro bloco (0..3) -> manda para intro 2
                    if self.active_start == 0 and self.active_end == 3:
                        # aguarda um instante e avança
                        self.app.root.after(800, self.app.start_second_intro)
                    else:
                        # se era o segundo bloco (3..6) -> jogo 2 concluído; você pode adicionar callback
                        # por enquanto apenas limpa/mostra sucesso
                        pass
                return
            else:
                # erro -> sinaliza e remove após delay curto
                self.kp_feedback = ("error", now + 0.45)
                try:
                    sc.send_result_async(False)
                except Exception as e:
                    print("[TX] Erro ao iniciar envio async (incorrect):", e)

                def remove_bad_slot(i=idx):
                    if 0 <= i < len(self.keypad_input) and not self.locked[i]:
                        self.keypad_input[i] = ''
                        self._update_keypad_value()
                self.app.root.after(180, remove_bad_slot)
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
