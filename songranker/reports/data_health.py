"""Stage-relative diagnostics, not a target that rewrites or normalises Elo."""
import math
from statistics import fmean,pstdev


def label(text,level):return dict(label=text,level=level)


def exposure_health(values,spread=None):
    values=list(values);n=len(values);mean=fmean(values) if n else 0
    relative=pstdev(values)/(1+mean) if n else 0
    if not n:balance=label('Unavailable','new')
    elif not mean:balance=label('New competition','new')
    elif mean<1:balance=label('Building evidence','new')
    elif relative>1:balance=label('Poor balance','bad')
    elif relative>.6:balance=label('Uneven','medium')
    elif relative>.35:balance=label('Fair','medium')
    elif relative>.15:balance=label('Good','good')
    else:balance=label('Excellent','good')
    # Approximate K32, equal-rating random-result IQR. Diagnostic reference only:
    # a consistent preference signal can legitimately produce a wider range.
    expected=1.349*16*math.sqrt(mean)
    low,high=.5*expected,2*expected
    if spread is None:rating=label('Not applicable','new')
    elif mean<2:rating=label('Still settling','new')
    elif spread<low:rating=label('Compact','medium')
    elif spread>high:rating=label('Wide preference spread','medium')
    else:rating=label('Within reference','good')
    return dict(balance=balance,elo=rating,mean=round(mean,3),dispersion=round(relative,3),
        reference_low=round(low,1),reference_high=round(high,1),
        stage='Starting' if mean<1 else 'Developing' if mean<8 else 'Established')


def coverage_health(right,total):
    if not total:return label('Unavailable','new')
    part=right/total
    return label('Excellent','good') if part>=.95 else label('Good','good') if part>=.8 else label('Fair','medium') if part>=.6 else label('Limited','medium') if part>=.3 else label('Poor','bad')
