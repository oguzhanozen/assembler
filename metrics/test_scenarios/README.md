# Test Senaryoları Metrik Raporu

- Ölçüm tarihi: `2026-06-07 12:34:26`
- UART: `COM7`, `115200` baud
- Tekrar sayısı: her senaryo için `10`
- Yükleme süresi: `PING` hariç, `BEGIN + DATA + END + RUN` paketlerinin gönderilip ACK alınması için geçen süre.

## Program Boyutu ve Yükleme Süresi

| Senaryo | Program (byte) | `.picoimg` (byte) | BRAM yerleşimi (byte) | Paket | Ortalama (ms) | Min (ms) | Max (ms) | Std. sapma (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Walking-One Pattern Test | 48 | 96 | 48 | 4 | 22.364 | 22.085 | 22.698 | 0.152 |
| Up/Down Counter Test | 156 | 204 | 160 | 5 | 35.805 | 35.593 | 36.085 | 0.122 |
| Multi-Object Call/Relocation Test | 116 | 164 | 116 | 4 | 28.251 | 28.103 | 28.417 | 0.086 |
| Memory Boundary/Out-of-Range Test | 148 | 196 | 148 | 5 | 35.035 | 34.843 | 35.266 | 0.113 |

## FPGA Kaynak Kullanımı

| Kaynak | Kullanılan | Kapasite | Kullanım |
|---|---:|---:|---:|
| LUT | 2095 | 8640 logic birimi | 24.25% |
| Register | 965 | 6693 | 14.42% |
| BSRAM | 15 | 26 | 57.69% |
| Toplam Logic | 2695 | 8640 | 31.19% |

Assembly programları UART loader üzerinden çalışma zamanında BRAM'e yazılır. Bu nedenle farklı test senaryoları aynı FPGA bitstream'ini kullanır ve LUT/Register/BSRAM değerleri senaryolar arasında değişmez.

LUT yüzdesi, Gowin PNR raporundaki LUT sayısının cihazın ortak logic kapasitesine oranıdır. Gowin ayrıca toplam Logic kullanımını LUT, ALU ve SSRAM birlikte olacak şekilde raporlar.

## Grafikler

- [Senaryolara göre UART yükleme süresi](charts/uart_load_time_by_scenario.svg)
- [Kod boyutu ve UART yükleme süresi](charts/code_size_vs_uart_load_time.svg)
- [FPGA kaynak kullanım yüzdeleri](charts/fpga_resource_utilization.svg)

Ham ölçümler `raw_uart_trials.csv`, ayrıntılı sonuçlar `scenario_metrics.csv` ve `scenario_metrics.json` dosyalarındadır.
