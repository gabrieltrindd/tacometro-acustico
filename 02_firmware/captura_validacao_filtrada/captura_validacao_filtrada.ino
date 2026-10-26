/*
  captura_validacao_filtrada.ino
  Mesma captura do captura_validacao.ino, mas aplicando o filtro
  passa-faixa (filtro_bandpass.h) a cada amostra antes de enviar.

  Use este sketch com o mesmo validar_captura.py para comparar, no
  waveform/espectrograma, o sinal antes (captura_validacao.ino) e depois
  (este aqui) do filtro — boa evidencia visual para o relatorio.

  Ligacoes: identicas ao captura_validacao.ino.

  IMPORTANTE: coloque o arquivo filtro_bandpass.h na mesma pasta deste
  sketch (o Arduino IDE mostra ele como uma aba extra automaticamente).
*/

#include <driver/i2s.h>
#include "filtro_bandpass.h"

#define I2S_SCK   14
#define I2S_WS    15
#define I2S_SD    16
#define I2S_PORT  I2S_NUM_0

#define SAMPLE_RATE     16000
#define CAPTURE_SECONDS 12      // entre 10 e 15s, ajuste aqui se quiser (igual ao captura_validacao.ino)
#define NUM_SAMPLES     (SAMPLE_RATE * CAPTURE_SECONDS)

#define SHIFT_BITS 16  // calibrado com calibrar_ganho.ino

// Buffer alocado na PSRAM (ver captura_validacao.ino para detalhes)
int16_t *audioBuffer;

void setupI2S() {
  i2s_config_t config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 256,
    .use_apll = false
  };
  i2s_pin_config_t pins = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD
  };
  i2s_driver_install(I2S_PORT, &config, 0, NULL);
  i2s_set_pin(I2S_PORT, &pins);
  i2s_zero_dma_buffer(I2S_PORT);
}

void setup() {
  Serial.begin(921600);
  delay(2000); // tempo para abrir o script no PC antes da captura comecar

  if (!psramFound()) {
    Serial.println("ERRO: PSRAM nao encontrada. Confira se a opcao de PSRAM");
    Serial.println("(OPI PSRAM) esta habilitada em Ferramentas na Arduino IDE.");
    while (true) delay(1000);
  }

  audioBuffer = (int16_t *)ps_malloc(NUM_SAMPLES * sizeof(int16_t));
  if (audioBuffer == NULL) {
    Serial.println("ERRO: falha ao alocar o buffer de audio na PSRAM.");
    while (true) delay(1000);
  }

  setupI2S();

  BandpassFilter filtro;
  bandpass_init(&filtro);

  Serial.printf("Capturando %d segundos (com filtro)... aproxime o microfone da fonte de som.\n",
                CAPTURE_SECONDS);
  delay(500);

  size_t bytesRead = 0;
  int32_t raw;
  for (int i = 0; i < NUM_SAMPLES; i++) {
    i2s_read(I2S_PORT, &raw, sizeof(raw), &bytesRead, portMAX_DELAY);
    int16_t amostra = (int16_t)(raw >> SHIFT_BITS);
    audioBuffer[i] = (int16_t)bandpass_process(&filtro, (float)amostra);
  }

  // Envia os dados em binario, precedidos e seguidos de marcadores de texto
  Serial.println("DATA_START");
  Serial.write((uint8_t*)audioBuffer, NUM_SAMPLES * sizeof(int16_t));
  Serial.println();
  Serial.println("DATA_END");
}

void loop() {
  // nada aqui: a captura acontece uma unica vez, dentro de setup()
}
