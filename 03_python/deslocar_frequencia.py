"""
deslocar_frequencia.py
Desloca o pico fundamental de original_16k.wav para uma frequencia-alvo
por reamostragem (muda todas as frequencias na mesma proporcao).

Uso: python deslocar_frequencia.py 143    -> gera motor_143Hz_16k.wav
Dependencias: pip install numpy scipy
"""
import sys, wave, numpy as np
from fractions import Fraction
from scipy.signal import resample_poly

def ler(p):
    w = wave.open(p); fs = w.getframerate()
    return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float), fs
def salvar(p, x, fs):
    x = np.clip(np.round(x), -32768, 32767).astype(np.int16)
    with wave.open(p, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(fs); w.writeframes(x.tobytes())
def pico(x, fs, lo, hi):
    n = 1 << 21                      # zero-padding -> grade fina de frequencia
    X = np.abs(np.fft.rfft((x - x.mean()) * np.hanning(len(x)), n)); f = np.fft.rfftfreq(n, 1/fs)
    m = (f >= lo) & (f <= hi); i = np.argmax(X[m]); fp = f[m][i]
    # centroide de potencia em +-1.5 Hz do pico (robusto a ondulacao)
    mm = (f >= fp-1.5) & (f <= fp+1.5); P = X[mm]**2
    return fp, float((f[mm]*P).sum()/P.sum())

x, fs = ler("original_16k.wav")
fp, fc = pico(x, fs, 120, 180)
print(f"pico fundamental original: {fp:.2f} Hz (centroide {fc:.2f} Hz)")
alvo = float(sys.argv[1]); f0 = fc
razao = Fraction(f0/alvo).limit_denominator(5000)   # fator de alongamento no tempo
y = resample_poly(x, razao.numerator, razao.denominator)   # mais amostras; tocado a 16 kHz => tom mais grave
saida = f"motor_{int(alvo)}Hz_16k.wav"
salvar(saida, y, fs)
fp2, fc2 = pico(y, fs, alvo-15, alvo+15)
print(f"fator tempo={razao} ({float(razao):.4f}) | duracao {len(x)/fs:.2f}s -> {len(y)/fs:.2f}s")
print(f"pico apos deslocamento: {fp2:.2f} Hz (centroide {fc2:.2f} Hz) | alvo {alvo} Hz")
print(f"pico de amplitude: {np.abs(y).max():.0f} (limite 32767)")
