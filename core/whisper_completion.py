"""Validate underlying Whisper decoder output before timestamp postprocessing."""
def require_finished_decoder(tokens, generated_steps, eos_token_id, limit=440):
    sequence = tokens.tolist() if hasattr(tokens,'tolist') else tokens
    if isinstance(sequence,list) and sequence and isinstance(sequence[0],list) and len(sequence) == 1:
        sequence = sequence[0]
    if (not isinstance(sequence,list) or not sequence
            or any(type(token) is not int or token < 0 for token in sequence)
            or type(generated_steps) is not int or generated_steps <= 0
            or type(eos_token_id) is not int):
        raise ValueError('Whisper returned invalid decoder completion evidence.')
    if generated_steps >= limit:
        raise ValueError('Whisper recognition reached its output token window.')
    if sequence[-1] != eos_token_id:
        raise ValueError('Whisper recognition decoder did not finish.')
