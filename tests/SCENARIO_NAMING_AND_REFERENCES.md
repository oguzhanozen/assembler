# Test Senaryosu Adlandırması ve Literatür Kaynakları

Bu senaryolar resmi bir benchmark paketinin birebir uygulaması değildir. Adlar,
senaryoların doğruladığı davranışları literatürde kullanılan yerleşik terimlerle
ifade edecek şekilde seçilmiştir.

## Adlandırma Eşleştirmesi

| Klasör | Rapor adı | Literatürdeki karşılığı | Bu projede doğrulanan davranış |
|---|---|---|---|
| `walking_one_led_pattern` | Walking-One Pattern Test | Walking ones test pattern | Tek bir `1` bitinin LED çıkışları boyunca sırayla ilerlemesi |
| `up_down_counter` | Up/Down Counter Test | Up/down counter | Buton girdilerine göre sayacın artırılması, azaltılması ve sınırda başa sarması |
| `multi_object_call_relocation` | Multi-Object Call/Relocation Test | Procedure call, symbol resolution ve static relocation | Ayrı object dosyasındaki fonksiyonlara çağrı, dönüş ve sembol relocation işlemleri |
| `memory_boundary_out_of_range` | Memory Boundary/Out-of-Range Test | Boundary value analysis ve out-of-bounds write | Son geçerli BRAM adresine ve BRAM dışındaki ilk adrese yazma girişimleri |

## Kaynaklar

1. **AMD/Xilinx, Test Utilities for Memory and Caches (UG643)**

   `XIL_TESTMEM_WALKONES` terimini "Walking Ones test" olarak tanımlar ve test
   değerinde tek bir `1` bitinin konum değiştirdiğini gösterir.

   https://docs.amd.com/r/2021.1-English/oslib_rm/Test-Utilities-for-Memory-and-Caches

2. **AMD/Xilinx, Counter (UG958)**

   FPGA sayaçlarını `up`, `down` ve `up/down counter` olarak sınıflandırır.

   https://docs.amd.com/r/en-US/ug958-vivado-sysgen-ref/Counter

3. **RISC-V ABIs Specification**

   RISC-V calling convention, ELF symbol table, static relocation, procedure call,
   `R_RISCV_JAL`, `R_RISCV_HI20` ve `R_RISCV_LO12` kavramlarını tanımlar.

   https://riscv-non-isa.github.io/riscv-elf-psabi-doc/

4. **ISTQB, Boundary Value Analysis According to the Foundation Level Syllabus**

   Boundary value analysis yöntemini sınır değerlerini ve komşularını çalıştıran
   bir test tekniği olarak açıklar.

   https://istqb.org/wp-content/uploads/2025/10/Boundary-Value-Analysis-white-paper.pdf

5. **MITRE CWE-787: Out-of-bounds Write**

   Amaçlanan bellek alanının sonundan sonra veya başlangıcından önce yapılan yazma
   işlemlerini out-of-bounds write olarak tanımlar.

   https://cwe.mitre.org/data/definitions/787.html

## Adlandırma Notları

- Walking-one senaryosu bir RAM bütünlük testi değildir; aynı test desenini LED
  çıkış veri yolunun gözlemlenmesi için kullanır.
- Multi-object senaryosu standart RISC-V ELF dosyası üretmez; ancak assembler ve
  linker içindeki çağrı, sembol çözümleme ve relocation davranışlarını aynı
  terminolojiyle sınar.
- Memory boundary senaryosu korumalı bellek hatası üretmeyi garanti etmez. Son
  geçerli adres ile ilk geçersiz adresi çalıştırarak sınır davranışını gözlemler.
