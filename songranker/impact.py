"""Read-only catalogue-relative Impact, in the current public Elo scale."""
from math import isfinite
from statistics import fmean, median


def rated(songs):
    """One finite rating per linked song; duplicate relationships add no weight."""
    result={}
    for raw in songs:
        song=dict(raw);value=song.get('elo_score')
        if song.get('id') is not None and type(value) in (int,float) and isfinite(value):
            result[song['id']]=value
    return result


def calibrate(songs, peers):
    library=rated(songs)
    sizes=[len(set(rated(group)) & library.keys()) for group in peers]
    return dict(baseline=fmean(library.values()) if library else 1200.0,
                prior_tracks=float(median(n for n in sizes if n)) if any(sizes) else 1.0,
                ratings=library)


def measure(songs, context):
    ids=set(rated(songs)) & context['ratings'].keys()
    n=len(ids);prior=context['prior_tracks'];base=context['baseline']
    average=fmean(context['ratings'][sid] for sid in ids) if n else None
    support=n/(n+prior)
    return dict(impact_score=base+support*(average-base) if n else None,
                impact_average=average,impact_tracks=n,impact_support=support,
                impact_baseline=base,impact_prior_tracks=prior)
