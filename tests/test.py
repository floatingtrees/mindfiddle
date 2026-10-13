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

NULLS = "nulls"
ZEROS = "zeros"
MIXED = "mixed"


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


def random_data_tape(rng):
    length = rng.randint(1, MAX_DATA_TAPE_LENGTH)
    fill = rng.choice([NULLS, NULLS, ZEROS, MIXED])

    if fill == NULLS:
        return fill, [1] * length
    if fill == ZEROS:
        return fill, [0] * length
    return fill, rng.choices([0, 1], k=length)


def outcome(fn, program, data_tape, max_steps):
    try:
        inst_tape, result_tape = fn(program, data_tape, max_steps)
        return ("ok", inst_tape, result_tape)
    except Exception as exc:
        return ("error", type(exc).__name__, str(exc))


def describe(result):
    if result[0] == "error":
        return "{}: {}".format(result[1], result[2])
    return "ok inst={} ones={}".format("".join(result[1][:40]), sum(result[2]))


def run_trials(trials, seed, max_steps_cap):
    rng = random.Random(seed)
    failures = []
    stats = collections.Counter()

    for trial in range(trials):
        program = random_program(rng)
        fill, source_tape = random_data_tape(rng)
        max_steps = rng.randint(0, max_steps_cap)

        fast_input = list(source_tape)
        slow_input = list(source_tape)
        fast = outcome(interpret, program, fast_input, max_steps)
        slow = outcome(interpret_python, program, slow_input, max_steps)

        stats["trials"] += 1
        stats["program_symbols"] += len(program)
        stats["tape_bits"] += len(source_tape)
        stats["fill_" + fill] += 1
        stats[slow[1] if slow[0] == "error" else "ok"] += 1
        if fast[0] == "ok" and "".join(fast[1]) != program:
            stats["self_modified"] += 1

        problem = None
        if fast != slow:
            problem = "backends disagree"
        elif fast_input != source_tape:
            problem = "c mutated the input tape"
        elif slow_input != source_tape:
            problem = "python mutated the input tape"

        if problem is not None:
            failures.append(
                {
                    "problem": problem,
                    "trial": trial,
                    "seed": seed,
                    "program_length": len(program),
                    "program_head": program[:200],
                    "tape_fill": fill,
                    "tape_length": len(source_tape),
                    "max_steps": max_steps,
                    "c": describe(fast),
                    "python": describe(slow),
                }
            )

    return failures, stats


def test_differential():
    failures, _ = run_trials(DEFAULT_TRIALS, DEFAULT_SEED, DEFAULT_MAX_STEPS)
    assert not failures, [failure["problem"] for failure in failures[:3]]


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
    print("tape bits:       ", stats["tape_bits"])
    print(
        "tape fills:       nulls={} zeros={} mixed={}".format(
            stats["fill_" + NULLS], stats["fill_" + ZEROS], stats["fill_" + MIXED]
        )
    )
    print("halted or ran:   ", stats["ok"])
    print("AssertionError:  ", stats["AssertionError"])
    print("IndexError:      ", stats["IndexError"])
    print("self modified:   ", stats["self_modified"])
    print("failures:        ", len(failures))

    for failure in failures[:5]:
        print()
        for key, value in failure.items():
            print("  {}: {}".format(key, value))

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
