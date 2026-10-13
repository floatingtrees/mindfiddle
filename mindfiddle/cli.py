import argparse

from mindfiddle import convert_tape_to_utf_8, interpret


def main():
    parser = argparse.ArgumentParser(prog="mindfiddle")
    parser.add_argument("program")
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--steps", type=int, default=10000)
    args = parser.parse_args()

    with open(args.program) as handle:
        program = "".join(handle.read().split())

    inst_tape, data_tape = interpret(program, [1] * args.length, args.steps)

    print("inst: ", "".join(inst_tape))
    print("data: ", "".join(str(bit) for bit in data_tape))
    print("utf-8:", convert_tape_to_utf_8(data_tape))


if __name__ == "__main__":
    main()
