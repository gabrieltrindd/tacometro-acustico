/*
  filtro_bandpass.h  (GERADO por projetar_filtro.py - nao edite a mao)
  Filtro passa-faixa Butterworth, prototipo de ordem 4 (ordem 8 no
  passa-faixa), cascata de 4 secoes biquad em Direct Form II Transposed.
  fs = 16000 Hz, banda de passagem (-3 dB) 120-170 Hz.

  Uso:
    static BandpassFilter filtro;
    bandpass_init(&filtro);
    y = bandpass_process(&filtro, x);
*/

#ifndef FILTRO_BANDPASS_H
#define FILTRO_BANDPASS_H

#define NUM_SECTIONS 4

typedef struct {
  float b0, b1, b2; // numerador
  float a1, a2;     // denominador (a0 = 1)
  float z1, z2;     // estado interno
} BiquadSection;

typedef struct {
  BiquadSection sections[NUM_SECTIONS];
} BandpassFilter;

static inline void bandpass_init(BandpassFilter *f) {
  BiquadSection sections[NUM_SECTIONS] = {
    { 9.0555254999e-09f, 1.8111051000e-08f, 9.0555254999e-09f, -1.9772505095f, 0.9808179397f, 0.0f, 0.0f },
    { 1.0000000000e+00f, 2.0000000000e+00f, 1.0000000000e+00f, -1.9805050464f, 0.9832283470f, 0.0f, 0.0f },
    { 1.0000000000e+00f, -2.0000000000e+00f, 1.0000000000e+00f, -1.9869996429f, 0.9913234546f, 0.0f, 0.0f },
    { 1.0000000000e+00f, -2.0000000000e+00f, 1.0000000000e+00f, -1.9914364299f, 0.9937070295f, 0.0f, 0.0f },
  };
  for (int i = 0; i < NUM_SECTIONS; i++) f->sections[i] = sections[i];
}

static inline float bandpass_process(BandpassFilter *f, float x) {
  for (int i = 0; i < NUM_SECTIONS; i++) {
    BiquadSection *s = &f->sections[i];
    float y = s->b0 * x + s->z1;
    s->z1 = s->b1 * x - s->a1 * y + s->z2;
    s->z2 = s->b2 * x - s->a2 * y;
    x = y;
  }
  return x;
}

#endif
