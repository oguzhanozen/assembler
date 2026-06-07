import argparse
import csv
import html
import json
import math
import re
import statistics
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.assembler import PicoRVAssembler
from src.host_loader import HostLoader, open_serial
from src.linker import PicoRVLinker
from src.loader_image import read_loader_image
from src.loader_protocol import MAX_PAYLOAD


SCENARIOS = {
    "walking_one_led_pattern": {
        "title": "Walking-One Pattern Test",
        "sources": ["tests/walking_one_led_pattern/main.asm", "tests/walking_one_led_pattern/delay.asm"],
        "script": "tests/walking_one_led_pattern/main_delay.ld",
    },
    "up_down_counter": {
        "title": "Up/Down Counter Test",
        "sources": ["tests/up_down_counter/main2.asm", "tests/up_down_counter/memory_map.asm"],
        "script": "tests/project.ld",
    },
    "multi_object_call_relocation": {
        "title": "Multi-Object Call/Relocation Test",
        "sources": ["tests/multi_object_call_relocation/main1.asm", "tests/multi_object_call_relocation/math_ops.asm"],
        "script": "tests/project.ld",
    },
    "memory_boundary_out_of_range": {
        "title": "Memory Boundary/Out-of-Range Test",
        "sources": ["tests/memory_boundary_out_of_range/main3.asm", "tests/memory_boundary_out_of_range/secure_data.asm"],
        "script": "tests/project.ld",
    },
}


def build_scenarios(output_dir):
    results = []
    build_dir = output_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    for name, config in SCENARIOS.items():
        scenario_dir = build_dir / name
        scenario_dir.mkdir(parents=True, exist_ok=True)
        object_paths = []
        source_bytes = 0

        for source_rel in config["sources"]:
            source_path = ROOT / source_rel
            source_bytes += source_path.stat().st_size
            obj, errors = PicoRVAssembler().assemble(source_path.read_text(encoding="utf-8").splitlines())
            if errors:
                raise RuntimeError(f"{source_rel} assemble hatası: {' | '.join(errors)}")
            object_path = scenario_dir / f"{source_path.stem}.o"
            object_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
            object_paths.append(str(object_path))

        linker = PicoRVLinker(str(ROOT / config["script"]))
        linked, errors = linker.link(object_paths)
        if errors:
            raise RuntimeError(f"{name} link hatası: {' | '.join(errors)}")

        prefix = scenario_dir / name
        paths = linker.write_outputs(linked, str(prefix))
        image_path = Path(paths["loader_image"])
        image = read_loader_image(image_path)
        program_bytes = sum(len(segment["data"]) for segment in image["segments"])
        packet_count = 3 + sum(
            math.ceil(len(segment["data"]) / MAX_PAYLOAD)
            for segment in image["segments"]
        )
        bram_used = sum(region["used"] for region in linked["memory_regions"])

        results.append(
            {
                "scenario": name,
                "title": config["title"],
                "source_files": len(config["sources"]),
                "source_bytes": source_bytes,
                "program_bytes": program_bytes,
                "picoimg_bytes": image_path.stat().st_size,
                "bram_linked_bytes": bram_used,
                "segment_count": len(image["segments"]),
                "uart_packet_count": packet_count,
                "image_path": str(image_path),
                "image": image,
            }
        )
    return results


def measure_uart(results, port, baudrate, trials):
    trial_rows = []
    for result in results:
        durations = []
        for trial in range(1, trials + 1):
            with open_serial(port, baudrate, 1.0) as stream:
                loader = HostLoader(stream)
                loader.ping()
                started = time.perf_counter()
                loader.load_image(result["image"])
                elapsed_ms = (time.perf_counter() - started) * 1000
            durations.append(elapsed_ms)
            trial_rows.append(
                {
                    "scenario": result["scenario"],
                    "title": result["title"],
                    "trial": trial,
                    "load_time_ms": round(elapsed_ms, 3),
                }
            )
            time.sleep(0.05)

        result["uart_trials"] = trials
        result["uart_load_avg_ms"] = statistics.mean(durations)
        result["uart_load_min_ms"] = min(durations)
        result["uart_load_max_ms"] = max(durations)
        result["uart_load_stddev_ms"] = statistics.stdev(durations) if len(durations) > 1 else 0.0
    return trial_rows


def parse_pnr_resources(report_path):
    text = report_path.read_text(encoding="utf-8", errors="replace")

    def match(pattern, label):
        found = re.search(pattern, text)
        if not found:
            raise RuntimeError(f"Gowin PNR raporunda {label} bulunamadı: {report_path}")
        return tuple(int(value) for value in found.groups())

    logic_used, logic_total, logic_percent_reported = match(
        r"Logic\s+\|\s+(\d+)/(\d+)\s+\|\s+(\d+)%",
        "Logic",
    )
    lut_used, alu_used = match(
        r"--LUT,ALU,ROM16\s+\|\s+\d+\((\d+) LUT,\s*(\d+) ALU",
        "LUT/ALU",
    )
    register_used, register_total, register_percent_reported = match(
        r"Register\s+\|\s+(\d+)/(\d+)\s+\|\s+(\d+)%",
        "Register",
    )
    bsram_used, bsram_total, bsram_percent_reported = match(
        r"BSRAM\s+\|\s+(\d+)/(\d+)\s+\|\s*(\d+)%",
        "BSRAM",
    )
    return {
        "report": str(report_path),
        "logic_used": logic_used,
        "logic_total": logic_total,
        "logic_percent": logic_used / logic_total * 100,
        "logic_percent_reported": logic_percent_reported,
        "lut_used": lut_used,
        "lut_capacity_basis": logic_total,
        "lut_percent": lut_used / logic_total * 100,
        "alu_used": alu_used,
        "register_used": register_used,
        "register_total": register_total,
        "register_percent": register_used / register_total * 100,
        "register_percent_reported": register_percent_reported,
        "bsram_used": bsram_used,
        "bsram_total": bsram_total,
        "bsram_percent": bsram_used / bsram_total * 100,
        "bsram_percent_reported": bsram_percent_reported,
    }


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def svg_bar_chart(path, title, labels, values, y_label, max_value=None):
    width, height = 1000, 600
    left, right, top, bottom = 95, 35, 75, 135
    plot_width = width - left - right
    plot_height = height - top - bottom
    max_value = max_value or max(values) * 1.15
    max_value = max(max_value, 1)
    bar_slot = plot_width / len(values)
    bar_width = bar_slot * 0.58

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2}" y="38" text-anchor="middle" font-family="Arial" font-size="24" font-weight="bold">{html.escape(title)}</text>',
        f'<text x="24" y="{top + plot_height / 2}" transform="rotate(-90 24 {top + plot_height / 2})" text-anchor="middle" font-family="Arial" font-size="16">{html.escape(y_label)}</text>',
    ]

    for step in range(6):
        value = max_value * step / 5
        y = top + plot_height - plot_height * step / 5
        lines.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#dddddd"/>')
        lines.append(f'<text x="{left - 10}" y="{y + 5:.1f}" text-anchor="end" font-family="Arial" font-size="13">{value:.1f}</text>')

    colors = ["#1976d2", "#388e3c", "#f57c00", "#7b1fa2", "#c62828"]
    for index, (label, value) in enumerate(zip(labels, values)):
        x = left + index * bar_slot + (bar_slot - bar_width) / 2
        bar_height = plot_height * value / max_value
        y = top + plot_height - bar_height
        color = colors[index % len(colors)]
        lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{color}"/>')
        lines.append(f'<text x="{x + bar_width / 2:.1f}" y="{y - 8:.1f}" text-anchor="middle" font-family="Arial" font-size="14" font-weight="bold">{value:.2f}</text>')
        lines.append(f'<text x="{x + bar_width / 2:.1f}" y="{top + plot_height + 24}" text-anchor="middle" font-family="Arial" font-size="13">{html.escape(label)}</text>')

    lines.append(f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#333333"/>')
    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def svg_scatter_chart(path, title, results):
    width, height = 1000, 600
    left, right, top, bottom = 100, 45, 75, 90
    plot_width = width - left - right
    plot_height = height - top - bottom
    x_max = max(result["program_bytes"] for result in results) * 1.15
    y_max = max(result["uart_load_avg_ms"] for result in results) * 1.2
    colors = ["#1976d2", "#388e3c", "#f57c00", "#7b1fa2"]

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2}" y="38" text-anchor="middle" font-family="Arial" font-size="24" font-weight="bold">{html.escape(title)}</text>',
        f'<text x="{left + plot_width / 2}" y="{height - 25}" text-anchor="middle" font-family="Arial" font-size="16">Yüklenen program boyutu (byte)</text>',
        f'<text x="25" y="{top + plot_height / 2}" transform="rotate(-90 25 {top + plot_height / 2})" text-anchor="middle" font-family="Arial" font-size="16">Ortalama UART yükleme süresi (ms)</text>',
    ]
    for step in range(6):
        x_value = x_max * step / 5
        x = left + plot_width * step / 5
        y_value = y_max * step / 5
        y = top + plot_height - plot_height * step / 5
        lines.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" stroke="#eeeeee"/>')
        lines.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}" stroke="#eeeeee"/>')
        lines.append(f'<text x="{x:.1f}" y="{top + plot_height + 24}" text-anchor="middle" font-family="Arial" font-size="12">{x_value:.0f}</text>')
        lines.append(f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-family="Arial" font-size="12">{y_value:.1f}</text>')

    for index, result in enumerate(results):
        x = left + plot_width * result["program_bytes"] / x_max
        y = top + plot_height - plot_height * result["uart_load_avg_ms"] / y_max
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="{colors[index]}"/>')
        lines.append(f'<text x="{x + 12:.1f}" y="{y - 10:.1f}" font-family="Arial" font-size="13">{html.escape(result["title"])}</text>')

    lines.append(f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#333333"/>')
    lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#333333"/>')
    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_report(output_dir, results, resources, port, baudrate, trials):
    rows = []
    for result in results:
        rows.append(
            {
                "scenario": result["scenario"],
                "source_files": result["source_files"],
                "source_bytes": result["source_bytes"],
                "program_bytes": result["program_bytes"],
                "picoimg_bytes": result["picoimg_bytes"],
                "bram_linked_bytes": result["bram_linked_bytes"],
                "segments": result["segment_count"],
                "uart_packets": result["uart_packet_count"],
                "uart_trials": result["uart_trials"],
                "uart_load_avg_ms": round(result["uart_load_avg_ms"], 3),
                "uart_load_min_ms": round(result["uart_load_min_ms"], 3),
                "uart_load_max_ms": round(result["uart_load_max_ms"], 3),
                "uart_load_stddev_ms": round(result["uart_load_stddev_ms"], 3),
                "lut_used": resources["lut_used"],
                "lut_percent": round(resources["lut_percent"], 2),
                "register_used": resources["register_used"],
                "register_percent": round(resources["register_percent"], 2),
                "bsram_used": resources["bsram_used"],
                "bsram_percent": round(resources["bsram_percent"], 2),
            }
        )

    fieldnames = list(rows[0].keys())
    write_csv(output_dir / "scenario_metrics.csv", fieldnames, rows)

    serializable_results = []
    for result in results:
        serializable_results.append({key: value for key, value in result.items() if key != "image"})
    (output_dir / "scenario_metrics.json").write_text(
        json.dumps(
            {
                "measurement": {
                    "port": port,
                    "baudrate": baudrate,
                    "trials_per_scenario": trials,
                    "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                },
                "fpga_resources": resources,
                "scenarios": serializable_results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    charts_dir = output_dir / "charts"
    charts_dir.mkdir(exist_ok=True)
    svg_bar_chart(
        charts_dir / "uart_load_time_by_scenario.svg",
        "Senaryolara Göre UART Yükleme Süresi",
        [result["title"] for result in results],
        [result["uart_load_avg_ms"] for result in results],
        "Ortalama süre (ms)",
    )
    svg_scatter_chart(
        charts_dir / "code_size_vs_uart_load_time.svg",
        "Kod Boyutu ve UART Yükleme Süresi",
        results,
    )
    svg_bar_chart(
        charts_dir / "fpga_resource_utilization.svg",
        "Ortak FPGA Tasarımı Kaynak Kullanımı",
        ["LUT", "Register", "BSRAM"],
        [resources["lut_percent"], resources["register_percent"], resources["bsram_percent"]],
        "Kullanım (%)",
        max_value=100,
    )

    table_lines = [
        "# Test Senaryoları Metrik Raporu",
        "",
        f"- Ölçüm tarihi: `{time.strftime('%Y-%m-%d %H:%M:%S')}`",
        f"- UART: `{port}`, `{baudrate}` baud",
        f"- Tekrar sayısı: her senaryo için `{trials}`",
        "- Yükleme süresi: `PING` hariç, `BEGIN + DATA + END + RUN` paketlerinin gönderilip ACK alınması için geçen süre.",
        "",
        "## Program Boyutu ve Yükleme Süresi",
        "",
        "| Senaryo | Program (byte) | `.picoimg` (byte) | BRAM yerleşimi (byte) | Paket | Ortalama (ms) | Min (ms) | Max (ms) | Std. sapma (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        table_lines.append(
            f"| {result['title']} | {result['program_bytes']} | {result['picoimg_bytes']} | "
            f"{result['bram_linked_bytes']} | {result['uart_packet_count']} | "
            f"{result['uart_load_avg_ms']:.3f} | {result['uart_load_min_ms']:.3f} | "
            f"{result['uart_load_max_ms']:.3f} | {result['uart_load_stddev_ms']:.3f} |"
        )

    table_lines.extend(
        [
            "",
            "## FPGA Kaynak Kullanımı",
            "",
            "| Kaynak | Kullanılan | Kapasite | Kullanım |",
            "|---|---:|---:|---:|",
            f"| LUT | {resources['lut_used']} | {resources['lut_capacity_basis']} logic birimi | {resources['lut_percent']:.2f}% |",
            f"| Register | {resources['register_used']} | {resources['register_total']} | {resources['register_percent']:.2f}% |",
            f"| BSRAM | {resources['bsram_used']} | {resources['bsram_total']} | {resources['bsram_percent']:.2f}% |",
            f"| Toplam Logic | {resources['logic_used']} | {resources['logic_total']} | {resources['logic_percent']:.2f}% |",
            "",
            "Assembly programları UART loader üzerinden çalışma zamanında BRAM'e yazılır. Bu nedenle farklı test senaryoları aynı FPGA bitstream'ini kullanır ve LUT/Register/BSRAM değerleri senaryolar arasında değişmez.",
            "",
            "LUT yüzdesi, Gowin PNR raporundaki LUT sayısının cihazın ortak logic kapasitesine oranıdır. Gowin ayrıca toplam Logic kullanımını LUT, ALU ve SSRAM birlikte olacak şekilde raporlar.",
            "",
            "## Grafikler",
            "",
            "- [Senaryolara göre UART yükleme süresi](charts/uart_load_time_by_scenario.svg)",
            "- [Kod boyutu ve UART yükleme süresi](charts/code_size_vs_uart_load_time.svg)",
            "- [FPGA kaynak kullanım yüzdeleri](charts/fpga_resource_utilization.svg)",
            "",
            "Ham ölçümler `raw_uart_trials.csv`, ayrıntılı sonuçlar `scenario_metrics.csv` ve `scenario_metrics.json` dosyalarındadır.",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(table_lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Assembly test senaryolarının FPGA/UART metriklerini toplar.")
    parser.add_argument("--port", default="COM7", help="UART seri portu")
    parser.add_argument("--baud", type=int, default=115200, help="UART baud hızı")
    parser.add_argument("--trials", type=int, default=10, help="Her senaryo için yükleme tekrar sayısı")
    parser.add_argument(
        "--output",
        default=str(ROOT / "metrics" / "test_scenarios"),
        help="Metrik çıktı klasörü",
    )
    args = parser.parse_args()

    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    results = build_scenarios(output_dir)
    trial_rows = measure_uart(results, args.port, args.baud, args.trials)
    resources = parse_pnr_resources(ROOT / "fpga" / "impl" / "pnr" / "picorv_loader.rpt.txt")
    write_csv(
        output_dir / "raw_uart_trials.csv",
        ["scenario", "title", "trial", "load_time_ms"],
        trial_rows,
    )
    write_report(output_dir, results, resources, args.port, args.baud, args.trials)
    print(f"Metrikler üretildi: {output_dir}")


if __name__ == "__main__":
    main()
