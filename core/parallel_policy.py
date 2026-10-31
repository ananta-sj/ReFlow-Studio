"""Shared segment scheduling bounds; worker count is not a model speedup."""
def segment_buffer_window(workers):
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError('Parallel workers must be an integer between 1 and 8')
    return 1 if workers == 1 else workers * 2
