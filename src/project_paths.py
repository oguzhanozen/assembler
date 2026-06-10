import os


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs")
ASSEMBLER_OUTPUT_DIR = os.path.join(OUTPUTS_DIR, "assembler")
LINKER_OUTPUT_DIR = os.path.join(OUTPUTS_DIR, "linker")
LOADER_OUTPUT_DIR = os.path.join(OUTPUTS_DIR, "loader")
FPGA_OUTPUT_DIR = os.path.join(OUTPUTS_DIR, "fpga")


def ensure_output_dirs():
    for path in (
        ASSEMBLER_OUTPUT_DIR,
        LINKER_OUTPUT_DIR,
        LOADER_OUTPUT_DIR,
        FPGA_OUTPUT_DIR,
    ):
        os.makedirs(path, exist_ok=True)
