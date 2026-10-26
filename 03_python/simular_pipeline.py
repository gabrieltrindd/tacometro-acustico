"""
simular_pipeline.py
Simula offline, em Python, o mesmo pipeline que vai rodar no ESP32:

  WAV 16 kHz -> filtro passa-faixa (coeficientes lidos do filtro_bandpass.h)
             -> janela de Hann -> FFT -> pico em 120-170 Hz
             -> interpolacao parabolica -> RPM = f * 60 / pas

Gera os graficos e a tabela do relatorio parcial 2 (a resposta do filtro
sai do projetar_filtro.py) na pasta "resultados/".

Uso:
  python simular_pipeline.py ../04_audios_teste/motor_143Hz_16k.wav --fref 143

  --fref   frequencia fundamental conhecida do sinal de teste (para calcular erro)
  --pas    numero de pas da helice (padrao 2)
  --header caminho do filtro_bandpass.h (padrao: o do firmware)

Dependencias: pip install numpy scipy matplotlib
"""
import argparse, os, re, wave
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import sosfilt, sosfreqz

AQUI = os.path.dirname(os.path.abspath(__file__))
F_LO, F_HI = 120.0, 170.0         # faixa de busca do pico (= banda do filtro)
JANELAS = [1024, 4096, 16384]      # tamanhos de FFT comparados
HOP = 512                          # = BUFFER_LEN do firmware (~32 ms)
DESCARTE_S = 0.5                   # ignora o transitorio inicial do filtro IIR

# ---------- estilo dos graficos ----------
AZUL, LARANJA, VERDE = "#2a78d6", "#eb6834", "#1baf7a"
TXT, TXT2, GRADE = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": TXT2, "axes.labelcolor": TXT, "xtick.color": TXT2, "ytick.color": TXT2,
    "axes.grid": True, "grid.color": GRADE, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
    "lines.linewidth": 1.6, "savefig.dpi": 200, "savefig.bbox": "tight",
})


def ler_wav(caminho):
    with wave.open(caminho) as w:
        fs = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    return x, fs


def ler_coeficientes(header):
    """Le os biquads do filtro_bandpass.h -> matriz SOS do scipy (b0 b1 b2 1 a1 a2)."""
    txt = open(header, encoding="utf-8").read()
    linhas = re.findall(r"\{\s*([-+\d.eE]+)f,\s*([-+\d.eE]+)f,\s*([-+\d.eE]+)f,\s*([-+\d.eE]+)f,\s*([-+\d.eE]+)f", txt)
    sos = np.array([[float(b0), float(b1), float(b2), 1.0, float(a1), float(a2)]
                    for b0, b1, b2, a1, a2 in linhas], dtype=np.float32)
    if len(sos) == 0:
        raise SystemExit(f"Nenhum coeficiente encontrado em {header}")
    return sos


def estimar_pico(frame, fs):
    """Hann + FFT + pico em [F_LO, F_HI] + interpolacao parabolica (log-magnitude)."""
    N = len(frame)
    X = np.abs(np.fft.rfft(frame * np.hanning(N)))
    f = np.fft.rfftfreq(N, 1 / fs)
    idx = np.where((f >= F_LO) & (f <= F_HI))[0]
    k = idx[np.argmax(X[idx])]
    a, b, c = np.log(X[k - 1] + 1e-12), np.log(X[k] + 1e-12), np.log(X[k + 1] + 1e-12)
    den = a - 2 * b + c
    delta = 0.5 * (a - c) / den if den < 0 else 0.0  # so interpola se k for maximo local
    delta = float(np.clip(delta, -0.5, 0.5))           # nunca sai do bin vizinho
    return f[k], (k + delta) * fs / N


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--fref", type=float, default=None)
    ap.add_argument("--pas", type=int, default=2)
    ap.add_argument("--header", default=os.path.join(AQUI, "..", "02_firmware",
                                                     "aquisicao_freertos", "filtro_bandpass.h"))
    ap.add_argument("--saida", default=os.path.join(AQUI, "resultados"))
    args = ap.parse_args()
    os.makedirs(args.saida, exist_ok=True)

    x, fs = ler_wav(args.wav)
    sos = ler_coeficientes(args.header)
    y = sosfilt(sos, x).astype(np.float32)
    rpm = lambda f: f * 60 / args.pas
    ini = int(DESCARTE_S * fs)

    # ---------- Espectro antes x depois do filtro ----------
    N = 16384
    seg = slice(ini, ini + N)
    f = np.fft.rfftfreq(N, 1 / fs)
    db = lambda s: 20 * np.log10(np.abs(np.fft.rfft(s * np.hanning(N))) + 1e-9)
    Xa, Xd = db(x[seg]), db(y[seg])
    ref = Xa.max()
    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.plot(f, Xa - ref, color=LARANJA, lw=1.0, label="Antes do filtro")
    ax.plot(f, Xd - ref, color=AZUL, lw=1.2, label="Depois do filtro")
    ax.axvspan(F_LO, F_HI, color=VERDE, alpha=0.12, lw=0)
    ax.set_xlim(0, 1000); ax.set_ylim(-120, 5)
    ax.set_xlabel("Frequência (Hz)"); ax.set_ylabel("Magnitude (dB, rel. ao máx.)")
    ax.set_title(f"Espectro do sinal de teste antes e depois do filtro ({F_LO:.0f}–{F_HI:.0f} Hz)")
    ax.legend(frameon=False, loc="upper right")
    fig.savefig(os.path.join(args.saida, "fig_espectro_antes_depois.png")); plt.close(fig)

    # ---------- Janelamento: quadro no tempo + espectro retangular x Hann ----------
    Nj = 4096
    q = y[ini:ini + Nj]; tq = np.arange(Nj) / fs * 1000; wh = np.hanning(Nj)
    fj = np.fft.rfftfreq(Nj, 1 / fs)
    Xr = 20 * np.log10(np.abs(np.fft.rfft(q)) + 1e-9); Xh = 20 * np.log10(np.abs(np.fft.rfft(q * wh)) + 1e-9)
    Xr -= Xr.max(); Xh -= Xh.max()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.4))
    a1.plot(tq, q, color=LARANJA, lw=0.8, label="Quadro filtrado")
    a1.plot(tq, q * wh, color=AZUL, lw=0.8, label="Após janela de Hann")
    a1.plot(tq, wh * np.abs(q).max(), color=TXT2, lw=1, ls="--", label="Janela (escalada)")
    a1.set_xlabel("Tempo (ms)"); a1.set_ylabel("Amplitude"); a1.legend(frameon=False, fontsize=8, ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.38))
    a1.set_title(f"Quadro de {Nj} amostras ({Nj / fs * 1000:.0f} ms)")
    a2.plot(fj, Xr, color=LARANJA, lw=1.1, label="Janela retangular")
    a2.plot(fj, Xh, color=AZUL, lw=1.3, label="Janela de Hann")
    a2.set_xlim(80, 220); a2.set_ylim(-80, 3)
    a2.set_xlabel("Frequência (Hz)"); a2.set_ylabel("Magnitude (dB)"); a2.legend(frameon=False, fontsize=8, ncol=2, loc="lower center", bbox_to_anchor=(0.5, -0.38))
    a2.set_title("Efeito da janela no vazamento espectral")
    fig.tight_layout(); fig.savefig(os.path.join(args.saida, "fig_janelamento.png")); plt.close(fig)

    # ---------- Deteccao do pico (zoom) ----------
    _, fpi = estimar_pico(y[seg], fs)
    Xl = np.abs(np.fft.rfft(y[seg] * np.hanning(N)))
    m = (f >= 60) & (f <= 200)
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.plot(f[m], Xl[m] / Xl[m].max(), color=AZUL)
    ax.axvspan(F_LO, F_HI, color=VERDE, alpha=0.12, lw=0)
    ax.axvline(fpi, color=TXT2, lw=1, ls="--")
    ax.annotate(f"pico: {fpi:.1f} Hz\n→ {rpm(fpi):.0f} RPM", xy=(fpi, 1.0), xytext=(fpi + 12, 0.85),
                fontsize=9, color=TXT, arrowprops=dict(arrowstyle="-", color=TXT2, lw=0.8))
    ax.set_xlabel("Frequência (Hz)"); ax.set_ylabel("Magnitude normalizada")
    ax.set_title(f"Detecção do pico na faixa de busca (FFT de {N} pontos)")
    fig.savefig(os.path.join(args.saida, "fig_deteccao_pico.png")); plt.close(fig)

    # ---------- RPM no tempo + tabela: RPM ao longo do tempo por tamanho de janela ----------
    cores = [LARANJA, VERDE, AZUL]
    linhas_tab = []
    fig, ax = plt.subplots(figsize=(7, 3.6))
    for Nw, cor in zip(JANELAS, cores):
        t, fb, fi = [], [], []
        for s in range(ini, len(y) - Nw, HOP):
            a, b = estimar_pico(y[s:s + Nw], fs)
            t.append((s + Nw) / fs); fb.append(a); fi.append(b)
        fb, fi = np.array(fb), np.array(fi)
        ax.plot(t, rpm(fi), color=cor, lw=1.4, label=f"N = {Nw} ({Nw / fs * 1000:.0f} ms)")
        linha = {"N": Nw, "res": fs / Nw, "lat": Nw / fs * 1000,
                 "f_bin": fb.mean(), "f_int": fi.mean(), "dp_rpm": rpm(fi).std()}
        if args.fref:
            linha["erro_bin"] = 100 * abs(fb.mean() - args.fref) / args.fref
            linha["erro_int"] = 100 * abs(fi.mean() - args.fref) / args.fref
        linhas_tab.append(linha)
    if args.fref:
        ax.axhline(rpm(args.fref), color=TXT, lw=1, ls="--", label=f"Referência {rpm(args.fref):.0f} RPM")
    ax.set_xlabel("Tempo (s)"); ax.set_ylabel("RPM estimado")
    ax.set_title("RPM estimado ao longo do tempo para diferentes tamanhos de janela")
    ax.legend(frameon=False, fontsize=8, ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.38))
    fig.savefig(os.path.join(args.saida, "fig_rpm_tempo_janelas.png")); plt.close(fig)

    # ---------- Tabela ----------
    cab = ["N", "Resolução (Hz)", "Latência (ms)", "f pico bin (Hz)", "f interp. (Hz)",
           "RPM interp.", "Desvio RPM"]
    if args.fref:
        cab += ["Erro bin (%)", "Erro interp. (%)"]
    linhas_txt = [" | ".join(cab)]
    for L in linhas_tab:
        cel = [f"{L['N']}", f"{L['res']:.2f}", f"{L['lat']:.0f}", f"{L['f_bin']:.2f}",
               f"{L['f_int']:.2f}", f"{rpm(L['f_int']):.0f}", f"{L['dp_rpm']:.1f}"]
        if args.fref:
            cel += [f"{L['erro_bin']:.2f}", f"{L['erro_int']:.2f}"]
        linhas_txt.append(" | ".join(cel))
    tabela = "\n".join(linhas_txt)
    open(os.path.join(args.saida, "tabela_janelas.txt"), "w", encoding="utf-8").write(tabela + "\n")

    # energia dentro x fora da banda
    def razao_db(s):
        P = np.abs(np.fft.rfft(s * np.hanning(len(s)))) ** 2
        ff = np.fft.rfftfreq(len(s), 1 / fs); b = (ff >= F_LO) & (ff <= F_HI)
        return 10 * np.log10(P[b].sum() / P[~b].sum())
    print(f"Arquivo: {os.path.basename(args.wav)} | fs = {fs} Hz | {len(x) / fs:.2f} s")
    print(f"Energia na banda / fora: antes {razao_db(x[ini:]):+.1f} dB | depois {razao_db(y[ini:]):+.1f} dB")
    print(tabela)
    print(f"Graficos salvos em: {args.saida}")


if __name__ == "__main__":
    main()
