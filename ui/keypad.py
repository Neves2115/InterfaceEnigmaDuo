# ui/keypad.py
import time
import threading
import serial_comm as sc

class KeypadManager:
    """
    Gerencia estado do keypad (3 slots), lógica de verificação algarismo-a-algarismo,
    feedback temporal e chamadas de envio serial (assíncrono).
    Interface principal:
      - handle_keypress(key)   # recebe '0'..'9', 'DEL', 'CLR'
      - attributes visíveis: keypad_input (list), locked (list), kp_feedback (tuple|None), keypad_value
    """

class KeypadManager:
    def __init__(self, app):
        self.app = app
        self.keypad_input = ['','','']
        self.locked = [False, False, False]
        self.kp_feedback = None
        self.keypad_value = None

    def set_first_secret(self, seq3):
        self.app.first_secret = seq3
        self.keypad_input = ['','','']
        self.locked = [False, False, False]
        self.kp_feedback = None
        self.keypad_value = None

    def _update_keypad_value(self):
        s = ''.join(self.keypad_input)
        if '' not in self.keypad_input:
            try:
                self.keypad_value = int(s)
            except:
                self.keypad_value = None
        else:
            self.keypad_value = None

    def handle_keypress(self, key):
        """
        Processa tecla do keypad: '0'..'9', 'DEL', 'CLR'.
        Mantém lógica idêntica ao monolítico: checagem contra app.first_secret,
        trava dígitos corretos e avança para intro2 quando completo.
        """
        now = time.time()

        # DEL: remove o último dígito não-locked (se houver)
        if key == "DEL":
            for i in range(len(self.keypad_input)-1, -1, -1):
                if self.keypad_input[i] != '' and not self.locked[i]:
                    self.keypad_input[i] = ''
                    self.kp_feedback = ("neutral", now + 0.25)
                    self._update_keypad_value()
                    return
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

            expected_digit = self.app.first_secret[idx]  # compara com os 3 primeiros dígitos

            # coloca temporariamente para feedback visual
            self.keypad_input[idx] = key
            self._update_keypad_value()

            if key == expected_digit:
                # dígito correto: marca locked e envia 0xFF
                self.locked[idx] = True
                self.kp_feedback = ("success", now + 0.35)
                try:
                    sc.send_result_async(True)
                except Exception as e:
                    print("[TX] Erro ao iniciar envio async (correct):", e)

                # se todos os três estão locked -> sequência completa
                if all(self.locked):
                    self.kp_feedback = ("sequence_ok", now + 1.0)
                    # daqui a 1s vamos para a introdução do segundo jogo (usa app.root.after)
                    self.app.root.after(800, self.app.start_second_intro)
                return
            else:
                # dígito incorreto: sinaliza, envia 0x00 e remove o dígito após curto delay
                self.kp_feedback = ("error", now + 0.45)
                try:
                    sc.send_result_async(False)
                except Exception as e:
                    print("[TX] Erro ao iniciar envio async (incorrect):", e)

                # usar after para remover o dígito (evita manipular estado desde outra thread)
                def remove_bad_slot(i=idx):
                    if 0 <= i < len(self.keypad_input) and not self.locked[i]:
                        self.keypad_input[i] = ''
                        self._update_keypad_value()
                # manter o mesmo timing: 180 ms
                self.app.root.after(180, remove_bad_slot)
                return

    # util para testes/integração: permite obter texto do display
    def display_text(self):
        return ''.join(self.keypad_input)

    # facilita acesso de draw: expõe propriedades
    def get_state_snapshot(self):
        return {
            "keypad_input": list(self.keypad_input),
            "locked": list(self.locked),
            "kp_feedback": self.kp_feedback,
            "keypad_value": self.keypad_value
        }
