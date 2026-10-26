"""
projetar_filtro.py
Projeta o filtro passa-faixa Butterworth em torno da frequencia de
blade-pass de interesse, imprime a checagem da resposta em frequencia,
gera o grafico da resposta e escreve o filtro_bandpass.h pronto para o
firmware (nas pastas dos sketches que usam o filtro).

Reexecute sempre que a faixa de interesse ou o numero de pas mudar.

Dependencias: pip install scipy numpy matplotlib
"""
import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, sosfreqz

# ---- Parametros de projeto: ajuste aqui ----
FS = 16000        # taxa de amostragem do firmware (Hz)
F_LO = 120.0      # borda inferior da banda de passagem (-3 dB)
F_HI = 170.0      # borda superior da banda de passagem (-3 dB)
ORDER = 4         # ordem do prototipo passa-baixas (passa-faixa resultante: ordem 8)
# ---------------------------------------------

AQUI = os.path.dirname(os.path.abspath(__file__))
SKETCHES = ["aquisicao_freertos", "captura_validacao_filtrada"]

sos = butter(ORDER, [F_LO, F_HI], btype="bandpass", fs=FS, output="sos")
w, h = sosfreqz(sos, worN=1 << 16, fs=FS)
gdb = 20 * np.log10(np.abs(h) + 1e-15)
ganho = lambda f: gdb[np.argmin(np.abs(w - f))]

print(f"Butterworth passa-faixa | fs={FS} Hz | banda {F_LO:.0f}-{F_HI:.0f} Hz | "
      f"ordem {2*ORDER} ({sos.shape[0]} secoes biquad)")
print("Checagem da resposta em frequencia:")
for f in [50, 60, 100, F_LO, 130, 143, 150, F_HI, 200, 300, 500, 1000, 2500]:
    print(f"  {f:7.1f} Hz: {ganho(f):8.2f} dB")

# ---- escreve o .h ----
linhas = "\n".join(
    f"    {{ {s[0]:.10e}f, {s[1]:.10e}f, {s[2]:.10e}f, {s[4]:.10f}f, {s[5]:.10f}f, 0.0f, 0.0f }},"
    for s in sos)
header = f"""/*
  filtro_bandpass.h  (GERADO por projetar_filtro.py - nao edite a mao)
  Filtro passa-faixa Butterworth, prototipo de ordem {ORDER} (ordem {2*ORDER} no
  passa-faixa), cascata de {sos.shape[0]} secoes biquad em Direct Form II Transposed.
  fs = {FS} Hz, banda de passagem (-3 dB) {F_LO:.0f}-{F_HI:.0f} Hz.

  Uso:
    static BandpassFilter filtro;
    bandpass_init(&filtro);
    y = bandpass_process(&filtro, x);
*/

#ifndef FILTRO_BANDPASS_H
#define FILTRO_BANDPASS_H

#define NUM_SECTIONS {sos.shape[0]}

typedef struct {{
  float b0, b1, b2; // numerador
  float a1, a2;     // denominador (a0 = 1)
  float z1, z2;     // estado interno
}} BiquadSection;

typedef struct {{
  BiquadSection sections[NUM_SECTIONS];
}} BandpassFilter;

static inline void bandpass_init(BandpassFilter *f) {{
  BiquadSection sections[NUM_SECTIONS] = {{
{linhas}
  }};
  for (int i = 0; i < NUM_SECTIONS; i++) f->sections[i] = sections[i];
}}

static inline float bandpass_process(BandpassFilter *f, float x) {{
  for (int i = 0; i < NUM_SECTIONS; i++) {{
    BiquadSection *s = &f->sections[i];
    float y = s->b0 * x + s->z1;
    s->z1 = s->b1 * x - s->a1 * y + s->z2;
    s->z2 = s->b2 * x - s->a2 * y;
    x = y;
  }}
  return x;
}}

#endif
"""
for sk in SKETCHES:
    d = os.path.join(AQUI, "..", "02_firmware", sk)
    if os.path.isdir(d):
        open(os.path.join(d, "filtro_bandpass.h"), "w", encoding="utf-8").write(header)
        print(f"filtro_bandpass.h atualizado em 02_firmware/{sk}/")

# ---- grafico da resposta ----
saida = os.path.join(AQUI, "resultados"); os.makedirs(saida, exist_ok=True)
AZUL, VERDE, TXT, TXT2 = "#2a78d6", "#1baf7a", "#0b0b0b", "#52514e"
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": "#e4e3df", "axes.edgecolor": TXT2, "font.size": 10,
                     "axes.titlesize": 11, "axes.titleweight": "bold"})
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.4), gridspec_kw={"width_ratios": [1.4, 1]})
for ax in (a1, a2):
    ax.plot(w[1:], gdb[1:], color=AZUL, lw=1.8)
    ax.axvspan(F_LO, F_HI, color=VERDE, alpha=0.13, lw=0)
    ax.set_xlabel("Frequência (Hz)"); ax.set_ylabel("Ganho (dB)")
a1.set_xscale("log"); a1.set_xlim(10, FS / 2); a1.set_ylim(-140, 5)
a1.set_title("Resposta em frequência (visão geral)")
a2.set_xlim(80, 220); a2.set_ylim(-30, 3)
a2.axhline(-3, color=TXT2, lw=1, ls="--")
a2.text(82, -2.2, "−3 dB", fontsize=8, color=TXT2)
a2.set_title(f"Detalhe da banda {F_LO:.0f}–{F_HI:.0f} Hz")
fig.tight_layout(); fig.savefig(os.path.join(saida, "fig_filtro_resposta.png"), dpi=200)
print(f"Grafico salvo em resultados/fig_filtro_resposta.png")
