/*
  aquisicao_freertos.ino
  Etapa 1 (continuacao) - Aquisicao continua de audio via I2S usando uma
  task dedicada do FreeRTOS, com uma fila entregando os buffers para o
  restante do sistema (nas proximas etapas: pre-processamento e FFT).

  Cada amostra ja sai filtrada (passa-faixa em torno da frequencia de
  blade-pass esperada, ver filtro_bandpass.h) antes de entrar na fila.
  A task "consumidora" ainda so calcula estatisticas simples (minimo,
  maximo, RMS) de cada buffer recebido, so para provar que o pipeline
  aquisicao -> filtro -> fila -> consumidor esta funcionando. Ela sera
  substituida pela task de janelamento/FFT na proxima etapa.

  Mesmas ligacoes do captura_validacao.ino (SD no GPIO16, pois GPIO26-37
  sao reservados pela flash/PSRAM octal no ESP32-S3-N16R8).

  IMPORTANTE: coloque o arquivo filtro_bandpass.h na mesma pasta deste
  sketch (o Arduino IDE mostra ele como uma aba extra automaticamente).
*/

#include <driver/i2s.h>
#include "filtro_bandpass.h"

#define I2S_SCK   14
#define I2S_WS    15
#define I2S_SD    16
#define I2S_PORT  I2S_NUM_0

#define SAMPLE_RATE   16000
#define BUFFER_LEN    512      // amostras por buffer (~32 ms a 16 kHz)
#define SHIFT_BITS    16       // calibrado com calibrar_ganho.ino
#define QUEUE_LENGTH  4        // buffers pendentes que a fila pode segurar

typedef struct {
  int16_t samples[BUFFER_LEN];
} AudioBuffer;

QueueHandle_t audioQueue;

void setupI2S() {
  i2s_config_t config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = BUFFER_LEN,
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

// Task produtora: le continuamente do I2S, filtra e envia buffers pela fila
void acquisitionTask(void *param) {
  int32_t rawBuffer[BUFFER_LEN];
  size_t bytesRead;

  static BandpassFilter filtro;
  bandpass_init(&filtro);

  while (true) {
    i2s_read(I2S_PORT, rawBuffer, sizeof(rawBuffer), &bytesRead, portMAX_DELAY);

    AudioBuffer buf;
    int samplesRead = bytesRead / sizeof(int32_t);
    for (int i = 0; i < samplesRead; i++) {
      int16_t amostra = (int16_t)(rawBuffer[i] >> SHIFT_BITS);
      buf.samples[i] = (int16_t)bandpass_process(&filtro, (float)amostra);
    }

    // Envia para a fila; se estiver cheia, descarta o buffer mais antigo
    // em vez de travar a aquisicao (revisar essa politica mais adiante)
    if (xQueueSend(audioQueue, &buf, 0) != pdTRUE) {
      AudioBuffer discard;
      xQueueReceive(audioQueue, &discard, 0);
      xQueueSend(audioQueue, &buf, 0);
    }
  }
}

// Task consumidora provisoria: so demonstra que a fila esta funcionando
void statsTask(void *param) {
  AudioBuffer buf;
  int buffersReceived = 0;
  unsigned long lastReport = millis();

  while (true) {
    if (xQueueReceive(audioQueue, &buf, portMAX_DELAY) == pdTRUE) {
      buffersReceived++;

      if (millis() - lastReport >= 1000) {
        int16_t minVal = 32767, maxVal = -32768;
        double sumSquares = 0;
        for (int i = 0; i < BUFFER_LEN; i++) {
          minVal = min(minVal, buf.samples[i]);
          maxVal = max(maxVal, buf.samples[i]);
          sumSquares += (double)buf.samples[i] * buf.samples[i];
        }
        double rms = sqrt(sumSquares / BUFFER_LEN);

        // Esperado: ~31 buffers/s (16000 / 512). Se vier bem abaixo disso,
        // a fila esta perdendo buffers ou a task de aquisicao esta atrasada.
        Serial.printf("Buffers/s: %d | min: %d | max: %d | RMS: %.1f\n",
                      buffersReceived, minVal, maxVal, rms);

        buffersReceived = 0;
        lastReport = millis();
      }
    }
  }
}

void setup() {
  Serial.begin(115200);
  setupI2S();

  audioQueue = xQueueCreate(QUEUE_LENGTH, sizeof(AudioBuffer));

  // A task de aquisicao aloca ~3KB em buffers locais (rawBuffer + AudioBuffer),
  // alem da pilha usada internamente pelo driver I2S — 4096 bytes nao bastava
  // e causava estouro de pilha (stack canary). 8192 da folga confortavel.
  xTaskCreatePinnedToCore(acquisitionTask, "Acquisition", 8192, NULL, 2, NULL, 1);
  xTaskCreatePinnedToCore(statsTask,       "Stats",       4096, NULL, 1, NULL, 1);
}

void loop() {
  vTaskDelay(portMAX_DELAY); // tudo acontece dentro das tasks
}
