/*
  calibrar_ganho.ino
  Utilitario para calibrar o SHIFT_BITS usado nos outros sketches.

  Captura ~1,5s de audio SEM aplicar nenhum shift, encontra o valor
  absoluto de pico nas amostras brutas (32 bits) e calcula qual SHIFT_BITS
  traria esse pico para ~70% da faixa de 16 bits (com folga para nao
  saturar de novo). Rode com a fonte de som mais alta que o projeto vai
  precisar captar (ex.: o motor na rotacao mais alta do teste).

  Mesma fiacao dos demais sketches (SCK->GPIO14, WS->GPIO15, SD->GPIO16).
*/

#include <driver/i2s.h>

#define I2S_SCK   14
#define I2S_WS    15
#define I2S_SD    16
#define I2S_PORT  I2S_NUM_0

#define SAMPLE_RATE      16000
#define CAPTURE_SECONDS  1.5
#define NUM_SAMPLES      ((int)(SAMPLE_RATE * CAPTURE_SECONDS))

// Alvo de pico na faixa de 16 bits (max teorico = 32767). Usar ~70% deixa
// folga de seguranca para picos um pouco mais altos que os capturados aqui.
#define TARGET_PEAK 22000

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
  Serial.begin(115200);
  delay(2000);
  setupI2S();

  Serial.println("Calibrando... mantenha a fonte de som mais alta do projeto tocando agora.");
  delay(500);

  int32_t rawMax = 0; // maior valor absoluto observado
  size_t bytesRead;
  int32_t raw;

  for (int i = 0; i < NUM_SAMPLES; i++) {
    i2s_read(I2S_PORT, &raw, sizeof(raw), &bytesRead, portMAX_DELAY);
    int32_t absVal = abs(raw);
    if (absVal > rawMax) rawMax = absVal;
  }

  // Encontra o menor shift que traz rawMax para <= TARGET_PEAK
  int suggestedShift = 0;
  while ((rawMax >> suggestedShift) > TARGET_PEAK && suggestedShift < 31) {
    suggestedShift++;
  }

  int32_t resultingPeak = rawMax >> suggestedShift;

  Serial.println("---- Resultado da calibracao ----");
  Serial.printf("Valor bruto de pico (32 bits): %ld\n", (long)rawMax);
  Serial.printf("SHIFT_BITS sugerido: %d\n", suggestedShift);
  Serial.printf("Pico resultante com esse shift: %ld (alvo: %d)\n",
                (long)resultingPeak, TARGET_PEAK);
  Serial.println("Atualize SHIFT_BITS nos outros sketches com o valor sugerido acima.");
}

void loop() {
  // nada aqui: a calibracao acontece uma unica vez, dentro de setup()
}
