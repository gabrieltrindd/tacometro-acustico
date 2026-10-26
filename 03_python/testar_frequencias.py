"""
testar_frequencias.py
Etapa 4 (testes com sinais conhecidos): gera versoes do sinal de teste com a
fundamental deslocada para varias frequencias conhecidas e verifica se o
pipeline (filtro -> Hann -> FFT -> pico -> RPM) encontra a frequencia certa.

Uso (dentro de 03_python):
  python testar_frequencias.py
  python testar_frequencias.py --freqs 125 135 145 155 165 --n 4096

Gera: resultados/tabela_frequencias.txt e resultados/fig_teste_frequencias.png
Dependencias: pip install numpy scipy matplotlib
"""
import argparse, os, wave
from fractions import Fraction
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import resample_poly, sosfilt

from simular_pipeline import ler_wav, ler_coeficientes, estimar_pico, HOP, DESCARTE_S

AQUI = os.path.dirname(os.path.abspath(__file__))


def pico_fino(x, fs, lo, hi):
    """Frequencia do pico com zero-padding + centroide (mesma medida do deslocar_frequencia.py)."""
    n = 1 << 21
    X = np.abs(np.fft.rfft((x - x.mean()) * np.hanning(len(x)), n)); f = np.fft.rfftfreq(n, 1 / fs)
    m = (f >= lo) & (f <= hi); fp = f[m][np.argmax(X[m])]
    mm = (f >= fp - 1.5) & (f <= fp + 1.5); P = X[mm] ** 2
    return float((f[mm] * P).sum() / P.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", default=os.path.join(AQUI, "..", "04_audios_teste", "original_16k.wav"))
    ap.add_argument("--freqs", type=float, nargs="+", default=[125, 135, 143, 155, 165])
    ap.add_argument("--n", type=int, default=4096, help="tamanho da FFT")
    ap.add_argument("--pas", type=int, default=2)
    ap.add_argument("--header", default=os.path.join(AQUI, "..", "02_firmware", "aquisicao_freertos", "filtro_bandpass.h"))
    ap.add_argument("--saida", default=os.path.join(AQUI, "resultados"))
    args = ap.parse_args()
    os.makedirs(args.saida, exist_ok=True)

    x, fs = ler_wav(args.wav)
    x = x.astype(float)
    f0 = pico_fino(x, fs, 120, 180)            # fundamental do sinal original (~150 Hz)
    sos = ler_coeficientes(args.header)
    ini = int(DESCARTE_S * fs)

    linhas, reais, medias, dps = [], [], [], []
    for alvo in args.freqs:
        r = Fraction(f0 / alvo).limit_denominator(5000)
        y = resample_poly(x, r.numerator, r.denominator)        # desloca a fundamental para 'alvo'
        yf = sosfilt(sos, y.astype(np.float32))
        est = np.array([estimar_pico(yf[s:s + args.n], fs)[1] for s in range(ini, len(yf) - args.n, HOP)])
        rpm_ref, rpm_est = alvo * 60 / args.pas, est.mean() * 60 / args.pas
        erro = 100 * abs(est.mean() - alvo) / alvo
        linhas.append(f"{alvo:.1f} | {rpm_ref:.0f} | {est.mean():.2f} | {rpm_est:.0f} | {erro:.2f} | {est.std() * 60 / args.pas:.1f}")
        reais.append(alvo); medias.append(est.mean()); dps.append(est.std())

    cab = "f real (Hz) | RPM real | f estimada (Hz) | RPM estimada | Erro (%) | Desvio (RPM)"
    tabela = cab + "\n" + "\n".join(linhas)
    open(os.path.join(args.saida, "tabela_frequencias.txt"), "w", encoding="utf-8").write(tabela + "\n")
    print(f"Fundamental do sinal original: {f0:.2f} Hz | FFT de {args.n} pontos")
    print(tabela)

    # grafico: RPM estimada x RPM real
    AZUL, TXT2 = "#2a78d6", "#52514e"
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                         "grid.color": "#e4e3df", "axes.edgecolor": TXT2, "font.size": 10,
                         "axes.titlesize": 11, "axes.titleweight": "bold"})
    rr = np.array(reais) * 60 / args.pas; re = np.array(medias) * 60 / args.pas
    fig, ax = plt.subplots(figsize=(6, 4))
    lim = [rr.min() - 200, rr.max() + 200]
    ax.plot(lim, lim, color=TXT2, lw=1, ls="--", label="Ideal (estimada = real)")
    ax.errorbar(rr, re, yerr=np.array(dps) * 60 / args.pas, fmt="o", color=AZUL, ms=7, capsize=4,
                label="Estimada (média ± desvio)")
    for a, b in zip(rr, re):
        ax.annotate(f"{b:.0f}", (a, b), xytext=(8, -12), textcoords="offset points", fontsize=8, color=TXT2)
    ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel("RPM real do sinal de teste"); ax.set_ylabel("RPM estimada pelo algoritmo")
    ax.set_title(f"Testes com sinais de frequência conhecida (FFT de {args.n} pontos)")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout(); fig.savefig(os.path.join(args.saida, "fig_teste_frequencias.png"), dpi=200)
    print("Grafico salvo em resultados/fig_teste_frequencias.png")


if __name__ == "__main__":
    main()
