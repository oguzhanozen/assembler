# Tang Nano 9K PicoRV32 UART Loader

Bu klasör, `.picoimg` programlarını UART üzerinden 16 KiB BRAM'e yükleyip PicoRV32 üzerinde çalıştıran FPGA tarafını içerir.

## Mimari

```text
USB-UART
  -> uart_rx
  -> picorv_loader_protocol
  -> CRC32 / ACK-NACK
  -> 16 KiB BRAM
  -> picorv32
  -> 0x10000000 LED MMIO
```

Loader yükleme boyunca PicoRV32'yi reset altında tutar. `END` komutunda toplam byte ve transfer CRC32 doğrulandıktan sonra `RUN` komutu işlemci resetini kaldırır. V1 tasarımında desteklenen entry adresi `0x00000000` değeridir.

## GowinEDA Kurulumu

1. `GW1NR-LV9QN88PC6/I5` cihazıyla yeni proje oluşturun.
2. Top module olarak `tang_nano_9k_top` seçin.
3. Aşağıdaki Verilog kaynaklarını projeye ekleyin:

```text
rtl/vendor/picorv32.v
rtl/vendor/uart_rx.v
rtl/vendor/uart_tx.v
rtl/crc32_byte.v
rtl/uart_response_tx.v
rtl/picorv_loader_protocol.v
rtl/picorv_system.v
rtl/tang_nano_9k_top.v
```

4. Physical Constraints olarak `tang_nano_9k.cst`, timing constraint olarak `tang_nano_9k.sdc` ekleyin.
5. Synthesis ve Place & Route çalıştırın, ardından bitstream'i karta yükleyin.
6. Bilgisayardan loader image gönderin:

```powershell
python -m src.host_loader outputs\loader\program.picoimg --port COM5
```

Komut satırından sentez ve bitstream üretimi:

```powershell
& "C:\Gowin\Gowin_V1.9.12.02_SP2_x64\IDE\bin\gw_sh.exe" build.tcl
```

Build sonucunda karta yüklenecek son bitstream `outputs/fpga/picorv_loader.fs`
dosyasına kopyalanır. `fpga/impl/` klasörü yeniden üretilebilir Gowin build artığıdır.

## Sabitler

- Sistem saati: 27 MHz
- UART: 115200 baud, 8N1
- Program/veri BRAM: `0x00000000` - `0x00003FFF`
- LED MMIO: `0x10000000`, düşük 6 bit
- LED çıkışları kart üzerinde active-low
- Kart butonu: pin `4`, active-low, LVCMOS18
- USB-UART: FPGA RX pin `18`, FPGA TX pin `17`, LVCMOS33

## Vendor Kaynakları

- `picorv32.v`: YosysHQ PicoRV32, ISC lisansı
- `uart_rx.v`, `uart_tx.v`: Alex Forencich Verilog UART, MIT lisansı

Lisans metinleri `rtl/vendor/` altında korunur.

## Doğrulama Durumu

Host protokolü, CRC32, ACK/NACK ve retry davranışı Python testleriyle doğrulanır.
Tasarım GowinEDA CLI ile sentezlenmiş, place & route tamamlanmış ve Tang Nano 9K üzerinde
gerçek UART aktarımıyla doğrulanmıştır.

27 MHz saat için `tang_nano_9k.sdc` uygulanır. Son timing analizinde setup/hold ihlali yoktur;
raporlanan maksimum frekans 42.442 MHz'dir.
