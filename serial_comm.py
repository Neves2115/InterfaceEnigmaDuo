# serial_comm.py
import threading, time
import serial
from constants import PORT, BAUDRATE, READ_SLEEP

# estado compartilhado (mesmo comportamento)
state_lock = threading.Lock()
state = {
    "error": None,
    "serial_ok": False,
    "running": True,
    "sim_on": False
}
serial_write_lock = threading.Lock()

# exposto para run.py atribuir e para ui usar
reader = None

class SerialReader(threading.Thread):
    def __init__(self, port=PORT, baud=BAUDRATE):
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
            try:
                self.ser.reset_input_buffer()
            except:
                pass
            print(f"✅ Serial aberta: {self.port} @ {self.baud} (7E1)")
            with state_lock:
                state["serial_ok"] = True
            return True
        except Exception as e:
            print("Erro abrindo serial:", e)
            with state_lock:
                state["serial_ok"] = False
            self.ser = None
            return False
        
    def stop(self):
        self.running = False
        
    def run(self):
        if not self.open_serial():
            while self.running and serial is not None:
                time.sleep(2.0)
                if self.open_serial():
                    break

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
                        try:
                            chunk = raw.decode('ascii', errors='ignore')
                        except:
                            chunk = raw.decode('utf-8', errors='ignore')
                        self.buffer += chunk
                        while '#' in self.buffer:
                            frame, self.buffer = self.buffer.split('#', 1)
                            frame = frame.strip()
                            if frame != "":
                                self.process_frame(frame)
                    else:
                        time.sleep(READ_SLEEP)
                else:
                    with state_lock:
                        state["serial_ok"] = False
                    time.sleep(0.6)
            except Exception as e:
                print("Erro no loop serial:", e)
                try:
                    if self.ser:
                        self.ser.close()
                except:
                    pass
                self.ser = None
                with state_lock:
                    state["serial_ok"] = False
                time.sleep(1.0)
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except:
            pass
        print("SerialReader finalizado.")

def process_frame(self, text):
    """
    Recebe um frame já separado pelo '#'.
    Pode ser:
      - "DD"   (medidas, valores inteiros)
      - "123456"  (a nova sequência de 6 dígitos)
    """
    txt = text.replace('\r','').replace('\n','').strip()

    if len(txt) == 6 and txt.isdigit():
        with state_lock:
            state["target_digits"] = txt
        print(f"[Serial] Sequência recebida: {txt}")
        return 

    try:
        val = int(txt)
        with state_lock:
            state["error"] = max(0, val)
    except Exception as e:
        print(f"Frame inválido (ignorando): '{txt}' -> {e}")




# função de simulação (idêntica)
def simulate_sequence():
    seq = [25, 12, 6, 3, 1, 0, 2, 5, 15, 28]
    while True:
        with state_lock:
            if not state.get("sim_on", False):
                break
        for v in seq:
            with state_lock:
                if not state.get("sim_on", False):
                    break
                state["error"] = v
            print(f"[SIM] erro -> {v}")
            time.sleep(1.0)


# ---------------------
# API de envio (nova)
# ---------------------
def send_result(correct: bool) -> bool:
    """
    Envia 0xFF (acerto) ou 0x00 (erro) usando reader.ser como fonte única.
    Retorna True se a escrita ocorreu com sucesso, False caso contrário.
    """
    byte_to_send = b'\xff' if correct else b'\x00'

    rdr = globals().get('reader')  # reader deve ser atribuído por run.py: sc.reader = reader
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

def send_result_async(correct: bool):
    """Dispara envio em thread daemon para não bloquear a UI."""
    t = threading.Thread(target=lambda: send_result(correct), daemon=True)
    t.start()
    return t

# backward compatibility helpers (opcionais)
def send_result_thread(correct: bool):
    """Nome alternativo, caso algum código já chamasse _send_result_thread."""
    return send_result_async(correct)
