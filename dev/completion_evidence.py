"""Conservative completion evidence from the pinned runner's performance log."""
import re


def generation_counts(log):
    return [int(match.group(1)) for line in log.splitlines()
        if ('common_perf_print:' in line or 'llama_perf_context_print:' in line) and 'prompt eval' not in line
        for match in [re.search(r'eval time\s*=.*?/\s*(\d+)\s+runs',line)] if match]


def finished_before_cap(log,maximum):
    counts=generation_counts(log)
    # The first sampled token can precede the measured decode runs. A run
    # count of maximum-1 can therefore mean the token cap was reached.
    return bool(counts and 0<counts[-1]<maximum-1)
