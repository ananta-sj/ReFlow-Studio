"""Cooperative cancellation at local autoregressive generation boundaries."""
from core.render_context import current_job


def generation_kwargs():
    job = current_job()
    if job is None:
        return {}
    job.check()
    from transformers import StoppingCriteria

    class CancelGeneration(StoppingCriteria):
        def __call__(self, input_ids, scores, **kwargs):
            job.check()
            return False

        def __deepcopy__(self, memo):
            # Transformers copies criteria; the callback retains the same job.
            return self

    return {'stopping_criteria': [CancelGeneration()]}
