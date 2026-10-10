import argparse
import collections
import random
import sys

from mindfiddle import interpret, interpret_python

PLAIN_SYMBOLS = "01sab+<>_"
HALT_SYMBOL = "X"

DEFAULT_TRIALS = 200
DEFAULT_SEED = 20261010
DEFAULT_MAX_STEPS = 20000
MAX_PROGRAM_LENGTH = 10000
MAX_DATA_TAPE_LENGTH = 4096


def random_program(rng):
    scale = rng.choice([16, 256, 2048, MAX_PROGRAM_LENGTH])
    length = rng.randint(1, scale)

    alphabet = list(PLAIN_SYMBOLS)
    weights = [1.0] * len(alphabet)

    halt_share = rng.choice([0.0, 0.0, 0.0001, 0.001, 0.01, 0.1])
    if halt_share > 0.0:
        alphabet.append(HALT_SYMBOL)
        weights.append(halt_share * len(PLAIN_SYMBOLS))

    return "".join(rng.choices(alphabet, weights=weights, k=length))


def outcome(fn, program, data_tape_length, max_steps):
    try:
        inst_tape, data_tape = fn(program, data_tape_length, max_steps)
        return ("ok", inst_tape, data_tape)
    except Exception as exc:
        return ("error", type(exc).__name__, str(exc))


def describe(result):
    if result[0] == "error":
        return "{}: {}".format(result[1], result[2])
    inst_tape, data_tape = result[1], result[2]
    return "ok inst={} ones={}".format("".join(inst_tape[:40]), sum(data_tape))


def run_trials(trials, seed, max_steps_cap):
    rng = random.Random(seed)
    failures = []
    stats = collections.Counter()

    for trial in range(trials):
        program = random_program(rng)
        data_tape_length = rng.randint(1, MAX_DATA_TAPE_LENGTH)
        max_steps = rng.randint(0, max_steps_cap)

        fast = outcome(interpret, program, data_tape_length, max_steps)
        slow = outcome(interpret_python, program, data_tape_length, max_steps)

        stats["trials"] += 1
        stats["program_symbols"] += len(program)
        stats[slow[1] if slow[0] == "error" else "ok"] += 1
        if fast[0] == "ok" and "".join(fast[1]) != program:
            stats["self_modified"] += 1

        if fast != slow:
            failures.append(
                {
                    "trial": trial,
                    "seed": seed,
                    "program_length": len(program),
                    "program_head": program[:200],
                    "data_tape_length": data_tape_length,
                    "max_steps": max_steps,
                    "c": describe(fast),
                    "python": describe(slow),
                }
            )

    return failures, stats


def test_differential():
    failures, _ = run_trials(DEFAULT_TRIALS, DEFAULT_SEED, DEFAULT_MAX_STEPS)
    assert not failures, failures[:3]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS)
    args = parser.parse_args()

    failures, stats = run_trials(args.trials, args.seed, args.max_steps)

    print("seed:            ", args.seed)
    print("trials:          ", stats["trials"])
    print("program symbols: ", stats["program_symbols"])
    print("halted or ran:   ", stats["ok"])
    print("AssertionError:  ", stats["AssertionError"])
    print("IndexError:      ", stats["IndexError"])
    print("self modified:   ", stats["self_modified"])
    print("mismatches:      ", len(failures))

    for failure in failures[:5]:
        print()
        for key, value in failure.items():
            print("  {}: {}".format(key, value))

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
