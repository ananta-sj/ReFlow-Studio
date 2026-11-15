"""Keep actionable local failures while stripping service credentials and URLs."""
import re


def summarize(error):
    message = str(error)
    message = re.sub(r'https?://\S+', '[service URL removed]', message, flags=re.I)
    message = re.sub(r'''(?i)(authorization["']?\s*[:=]\s*["']?(?:bearer\s+)?|(?:api[_-]?key|token|password|secret)["']?\s*[:=]\s*["']?)[^\s,;"']+''',
                     r'\1[redacted]', message)
    return dict(type=type(error).__name__, message=message[:2400])
