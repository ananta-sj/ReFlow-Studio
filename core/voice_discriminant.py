"""Episode-local voice proposals trained only from labelled source anchors.

Scores are rejection thresholds, not calibrated identity probabilities. This
adds no downloaded model and never trains on its own proposed assignments.
"""
import numpy as np


def train(templates,vectors):
    reliable={row['label'] for row in templates.values()
              if not row.get('generic') and len(row.get('indices',[]))>=2}
    if len(reliable)<2:return None
    keys=list(templates)
    labelled=[(i,key) for key,row in templates.items() for i in row.get('indices',[]) if i in vectors]
    if not labelled:return None
    x=np.asarray([vectors[i] for i,_ in labelled],dtype=float)
    if x.ndim!=2 or not x.shape[1] or not np.isfinite(x).all():raise ValueError('Invalid labelled source vectors')
    y=np.asarray([[float(owner==key) for key in keys] for _,owner in labelled])
    try:
        # Long films can have many labelled cues. Solve the smaller system;
        # never allocate a quadratic matrix in the number of all movie cues.
        if len(x)>x.shape[1]:
            weights=np.linalg.solve(x.T@x+.1*np.eye(x.shape[1]),x.T@y)
        else:
            weights=x.T@np.linalg.solve(x@x.T+.1*np.eye(len(x)),y)
    except np.linalg.LinAlgError:return None
    return dict(keys=keys,weights=weights,templates=templates)


def propose(vector,model):
    if model is None or vector is None:return None,{}
    vector=np.asarray(vector,dtype=float)
    if vector.shape!=(model['weights'].shape[0],) or not np.isfinite(vector).all():
        raise ValueError('Invalid source voice dimensions')
    scores=vector@model['weights'];order=np.argsort(scores)[::-1]
    if len(order)<2:return None,{}
    best,second=map(int,order[:2]);key=model['keys'][best];row=model['templates'][key]
    score=float(scores[best]);margin=score-float(scores[second])
    similarity=float(vector@np.asarray(row['center']))
    evidence=dict(method='labelled_source_discriminant',classifier_score=round(score,4),
                  classifier_margin=round(margin,4),similarity=round(similarity,4))
    if row.get('generic') or len(row.get('indices',[]))<2 or score<.4 or margin<.3 or similarity<.55:
        return None,evidence
    return key,evidence
