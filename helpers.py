# helpers.py
# pequenas funções utilitárias para bucket/cores

from constants import THEME, TH_VERY_CLOSE, TH_ALMOST

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
