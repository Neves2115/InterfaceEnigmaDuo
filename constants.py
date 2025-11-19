# constants.py
# configurações e tema - importado por outros módulos conforme solicitado

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

# porta / serial
PORT = "COM8"
BAUDRATE = 115200
READ_SLEEP = 0.01

# UI / thresholds
UI_UPDATE_MS = 120
FAR_TH = 30
TH_VERY_CLOSE = 3
TH_ALMOST = 12
