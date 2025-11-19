# run.py
# ponto de entrada (mantém o mesmo comportamento: cria reader, atribui em serial_comm.reader, inicia UI)

import tkinter as tk
import time

from serial_comm import SerialReader, state_lock, state
import serial_comm as sc
from ui import EnigmaDuoApp

if __name__ == "__main__":
    # inicia thread serial (disponível globalmente para send_result_over_serial fallback)
    reader = SerialReader()
    # expor reader no módulo serial_comm para compatibilidade com send_result_over_serial
    sc.reader = reader
    reader.start()

    root = tk.Tk()
    app = EnigmaDuoApp(root)

    try:
        root.mainloop()
    finally:
        reader.stop()
        with sc.state_lock:
            sc.state['running'] = False
        # dar um tempinho para encerrar
        time.sleep(0.05)
