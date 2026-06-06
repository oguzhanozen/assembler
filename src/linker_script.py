import re
from dataclasses import dataclass


class LinkerScriptError(ValueError):
    pass


@dataclass
class MemoryRegion:
    name: str
    flags: str
    origin_expr: object
    length_expr: object


@dataclass
class InputSelector:
    object_pattern: str
    section_pattern: str


@dataclass
class LocationAssignment:
    expression: object


@dataclass
class OutputSection:
    name: str
    noload: bool
    start_expr: object
    commands: list
    region: str


@dataclass
class LinkerScript:
    entry: str
    memory: list
    sections: list


TOKEN_RE = re.compile(
    r"""
    \s+
    |/\*.*?\*/
    |//[^\n]*
    |\#[^\n]*
    |0[xX][0-9A-Fa-f]+[KkMm]?
    |\d+[KkMm]?
    |[A-Za-z_.$][A-Za-z0-9_.$*-]*
    |\*
    |[{}():;,>=+\-]
    """,
    re.VERBOSE | re.DOTALL,
)


def tokenize(text):
    tokens = []
    position = 0
    while position < len(text):
        match = TOKEN_RE.match(text, position)
        if not match:
            snippet = text[position:position + 20].splitlines()[0]
            raise LinkerScriptError(f"Desteklenmeyen linker script sözdizimi: '{snippet}'")
        token = match.group(0)
        position = match.end()
        if token.isspace() or token.startswith(("/*", "//", "#")):
            continue
        tokens.append(token)
    return tokens


class Parser:
    def __init__(self, text):
        self.tokens = tokenize(text)
        self.index = 0

    def peek(self, value=None):
        if self.index >= len(self.tokens):
            return False if value is not None else None
        token = self.tokens[self.index]
        return token.upper() == value.upper() if value is not None else token

    def take(self, value=None):
        token = self.peek()
        if token is None:
            raise LinkerScriptError("Linker script beklenmedik biçimde sona erdi.")
        if value is not None and token.upper() != value.upper():
            raise LinkerScriptError(f"'{value}' beklenirken '{token}' bulundu.")
        self.index += 1
        return token

    def optional(self, value):
        if self.peek(value):
            return self.take()
        return None

    def parse(self):
        entry = None
        memory = None
        sections = None
        while self.peek() is not None:
            if self.peek("ENTRY"):
                if entry is not None:
                    raise LinkerScriptError("ENTRY birden fazla tanımlandı.")
                entry = self.parse_entry()
            elif self.peek("MEMORY"):
                if memory is not None:
                    raise LinkerScriptError("MEMORY birden fazla tanımlandı.")
                memory = self.parse_memory()
            elif self.peek("SECTIONS"):
                if sections is not None:
                    raise LinkerScriptError("SECTIONS birden fazla tanımlandı.")
                sections = self.parse_sections()
            else:
                raise LinkerScriptError(f"Desteklenmeyen üst seviye yapı: '{self.peek()}'")
        if not entry:
            raise LinkerScriptError("Linker script ENTRY tanımı içermeli.")
        if not memory:
            raise LinkerScriptError("Linker script MEMORY tanımı içermeli.")
        if not sections:
            raise LinkerScriptError("Linker script SECTIONS tanımı içermeli.")
        return LinkerScript(entry, memory, sections)

    def parse_entry(self):
        self.take("ENTRY")
        self.take("(")
        symbol = self.take()
        self.take(")")
        self.optional(";")
        return symbol

    def parse_memory(self):
        self.take("MEMORY")
        self.take("{")
        regions = []
        while not self.peek("}"):
            name = self.take()
            flags = ""
            if self.optional("("):
                flags = self.take()
                self.take(")")
            self.take(":")
            self.take("ORIGIN")
            self.take("=")
            origin = self.parse_expression({","})
            self.take(",")
            self.take("LENGTH")
            self.take("=")
            length = self.parse_expression({";", "}"})
            self.optional(";")
            regions.append(MemoryRegion(name, flags.lower(), origin, length))
        self.take("}")
        return regions

    def parse_sections(self):
        self.take("SECTIONS")
        self.take("{")
        outputs = []
        while not self.peek("}"):
            if self.peek(".") and self.index + 1 < len(self.tokens) and self.tokens[self.index + 1] == "=":
                raise LinkerScriptError("Üst seviye location-counter ataması desteklenmiyor; output section içinde kullanın.")
            outputs.append(self.parse_output_section())
        self.take("}")
        return outputs

    def parse_output_section(self):
        name = self.take()
        noload = False
        if self.optional("("):
            self.take("NOLOAD")
            self.take(")")
            noload = True
        self.take(":")
        start_expr = None
        if not self.peek("{"):
            start_expr = self.parse_expression({"{"})
        self.take("{")
        commands = []
        while not self.peek("}"):
            if self.peek("."):
                self.take(".")
                self.take("=")
                commands.append(LocationAssignment(self.parse_expression({";"})))
                self.take(";")
                continue
            object_pattern = self.take()
            self.take("(")
            found = False
            while not self.peek(")"):
                commands.append(InputSelector(object_pattern, self.take()))
                found = True
            if not found:
                raise LinkerScriptError(f"{object_pattern}(...) en az bir section seçici içermeli.")
            self.take(")")
        self.take("}")
        self.take(">")
        region = self.take()
        self.optional(";")
        return OutputSection(name, noload, start_expr, commands, region)

    def parse_expression(self, stops):
        expression = self.parse_add_sub(stops)
        if self.peek() is not None and self.peek() not in stops:
            raise LinkerScriptError(f"Expression içinde desteklenmeyen token: '{self.peek()}'")
        return expression

    def parse_add_sub(self, stops):
        node = self.parse_primary(stops)
        while self.peek() in ("+", "-"):
            operator = self.take()
            node = (operator, node, self.parse_primary(stops))
        return node

    def parse_primary(self, stops):
        token = self.peek()
        if token is None or token in stops:
            raise LinkerScriptError("Eksik expression.")
        if token == "-":
            self.take()
            return ("neg", self.parse_primary(stops))
        if token == "(":
            self.take()
            node = self.parse_add_sub({")"})
            self.take(")")
            return node
        if token == ".":
            self.take()
            return ("dot",)
        if token.upper() in ("ALIGN", "ORIGIN", "LENGTH"):
            function = self.take().upper()
            self.take("(")
            if function in ("ORIGIN", "LENGTH"):
                argument = ("region", self.take())
            else:
                argument = self.parse_add_sub({")"})
            self.take(")")
            return ("call", function, argument)
        self.take()
        if re.fullmatch(r"(?:0[xX][0-9A-Fa-f]+|\d+)[KkMm]?", token):
            suffix = token[-1].upper() if token[-1].isalpha() else ""
            digits = token[:-1] if suffix else token
            value = int(digits, 0)
            if suffix == "K":
                value *= 1024
            elif suffix == "M":
                value *= 1024 * 1024
            return ("number", value)
        raise LinkerScriptError(f"Expression içinde desteklenmeyen değer: '{token}'")


def evaluate_expression(node, dot=0, regions=None):
    regions = regions or {}
    kind = node[0]
    if kind == "number":
        return node[1]
    if kind == "dot":
        return dot
    if kind == "neg":
        return -evaluate_expression(node[1], dot, regions)
    if kind in ("+", "-"):
        left = evaluate_expression(node[1], dot, regions)
        right = evaluate_expression(node[2], dot, regions)
        return left + right if kind == "+" else left - right
    if kind == "call":
        function = node[1]
        if function == "ALIGN":
            alignment = evaluate_expression(node[2], dot, regions)
            if alignment <= 0 or alignment & (alignment - 1):
                raise LinkerScriptError("ALIGN pozitif power-of-two değer bekler.")
            return (dot + alignment - 1) // alignment * alignment
        region_name = node[2][1]
        if region_name not in regions:
            raise LinkerScriptError(f"Bilinmeyen memory region: '{region_name}'")
        return regions[region_name]["origin" if function == "ORIGIN" else "length"]
    raise LinkerScriptError(f"Geçersiz expression düğümü: {node}")


def parse_linker_script(text):
    return Parser(text).parse()
