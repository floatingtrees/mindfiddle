from dataclasses import dataclass

@dataclass 
class Pointers:
    INST_PTR: int
    DATA_PTR_1: int
    DATA_PTR_2: int
    ACTIVE: int = 1

    @property
    def data_ptr(self):
        return self.DATA_PTR_1 if self.ACTIVE == 1 else self.DATA_PTR_2

    @data_ptr.setter
    def data_ptr(self, value):
        if self.ACTIVE == 1:
            self.DATA_PTR_1 = value
        else:
            self.DATA_PTR_2 = value

SYMBOLS = {
    "0": 0,
    "1": 1,
    "s": 2,
    "a": 3,
    "b": 4,
    "+": 5,
    "<": 6,
    ">": 7,
    "X": 8,
    "_": 15,
}

INSTRUCTIONS = {code: symbol for symbol, code in SYMBOLS.items()}

def convert_int_to_binary(x):
    assert x <= 15, "only instructions can be converted"
    return [(x >> i) & 1 for i in range(3, -1, -1)]

def convert_program_to_binary(program: str):
    program_list = []
    for char in program:
        code = SYMBOLS[char]
        value = convert_int_to_binary(code)
        program_list.extend(value)
    return program_list


def convert_tape_to_utf_8(tape):
    padded = tape + [0] * (-len(tape) % 8)
    data = bytearray()
    for i in range(0, len(padded), 8):
        byte = 0
        for bit in padded[i: i + 8]:
            byte = (byte << 1) | bit
        data.append(byte)
    return data.decode("utf-8", errors="replace")

def binary_to_inst(binary_array):
    assert len(binary_array) == 4, "instructions should be 4 bit"
    code = 0
    for bit in binary_array:
        code = (code << 1) | bit
    return INSTRUCTIONS.get(code, "_")


DATA_DIGITS = {"0": 0, "1": 1}
INST_DIGITS = {"a": 0, "b": 1}


def read_literal(tape, start, digits):
    value = 0
    sign = 1
    pos = start
    leading = True
    while pos + 4 <= len(tape):
        symbol = binary_to_inst(tape[pos: pos + 4])
        if symbol not in digits:
            break
        if leading:
            sign = -1 if digits[symbol] == 0 else 1
            leading = False
        else:
            value = (value << 1) | digits[symbol]
        pos += 4
    return sign * value


def step(tape, POINTERS):
    instruction = binary_to_inst(tape[POINTERS.INST_PTR: POINTERS.INST_PTR + 4])
    size = len(tape)
    jumped = False

    match instruction:
        case "0" | "1":
            offset = read_literal(tape, POINTERS.INST_PTR, DATA_DIGITS)
            if tape[POINTERS.data_ptr] == 0:
                POINTERS.data_ptr = (POINTERS.data_ptr + offset) % size
        case "a" | "b":
            offset = read_literal(tape, POINTERS.INST_PTR, INST_DIGITS)
            if tape[POINTERS.data_ptr] == 0:
                POINTERS.INST_PTR = (POINTERS.INST_PTR + offset * 4) % size
                jumped = True
        case "s":
            POINTERS.ACTIVE = 2 if POINTERS.ACTIVE == 1 else 1
        case "+":
            tape[POINTERS.data_ptr] ^= 1
        case "<":
            POINTERS.data_ptr = (POINTERS.data_ptr - 1) % size
        case ">":
            POINTERS.data_ptr = (POINTERS.data_ptr + 1) % size
        case "X":
            return False
        case "_":
            pass

    if not jumped:
        POINTERS.INST_PTR = (POINTERS.INST_PTR + 4) % size

    return True


def interpret(program: str, data_tape: list, max_steps):
    tape = convert_program_to_binary(program)
    program_length = len(tape)
    POINTERS = Pointers(0, program_length, program_length)
    tape.extend(data_tape)

    for _ in range(max_steps):
        if not step(tape, POINTERS):
            break

    inst_tape = [
        binary_to_inst(tape[i: i + 4]) for i in range(0, program_length, 4)
    ]
    return inst_tape, tape[program_length:]


if __name__ == "__main__":
    inst_tape, data_tape = interpret("+++", [1] * 8, 8)
    print(inst_tape)
    print(data_tape)
    print(convert_tape_to_utf_8(data_tape))
    