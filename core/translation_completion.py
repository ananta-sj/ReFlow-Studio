"""Reject oversized input and mechanically unfinished local translations."""


def require_input_window(inputs, model, engine):
    ids = inputs['input_ids']
    shape = getattr(ids, 'shape', None)
    count = int(shape[-1]) if shape is not None else len(ids[0] if ids and isinstance(ids[0], (list, tuple)) else ids)
    limit = getattr(getattr(model, 'config', None), 'max_position_embeddings', None)
    if type(limit) is not int or limit <= 0:
        raise RuntimeError(f'{engine} does not declare a valid input token limit.')
    if count > limit:
        raise ValueError(f'{engine} input has {count} tokens; its limit is {limit}. Split the source into complete sentences before translating.')


def require_finished(tokens, tokenizer, engine, max_new_tokens=512):
    sequences = tokens.tolist() if hasattr(tokens, 'tolist') else tokens
    if not isinstance(sequences, list) or len(sequences) != 1 or not isinstance(sequences[0], list):
        raise RuntimeError(f'{engine} returned invalid translation tokens.')
    sequence = sequences[0]
    if not sequence or any(type(token) is not int or token < 0 for token in sequence):
        raise RuntimeError(f'{engine} returned invalid translation tokens.')
    # One decoder-start token precedes newly generated tokens. An EOS forced at
    # the cap does not prove that the model completed the sentence naturally.
    if len(sequence) - 1 >= max_new_tokens:
        raise RuntimeError(f'{engine} translation reached its output token limit. Split the source and translate again.')
    eos = getattr(tokenizer, 'eos_token_id', None)
    pad = getattr(tokenizer, 'pad_token_id', None)
    if type(eos) is not int:
        raise RuntimeError(f'{engine} tokenizer has no valid end-of-sentence token.')
    while sequence and type(pad) is int and pad != eos and sequence[-1] == pad:
        sequence = sequence[:-1]
    if len(sequence) < 2 or sequence[-1] != eos:
        raise RuntimeError(f'{engine} returned an unfinished translation. Retry or split the source sentence.')
