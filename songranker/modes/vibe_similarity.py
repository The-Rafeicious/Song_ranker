"""Small, coverage-scaled similarity adjustments; no eligibility or rating changes."""

import math
from songranker.storage.vibe_state import MAPS

MAX_BIAS = .15
WIDTH = .65
GRID = tuple((x/2-1, y/2-1) for x in range(5) for y in range(5))
KERNEL = tuple(tuple(math.exp(-((x-a)**2+(y-b)**2)/(2*WIDTH**2))
                     for a,b in GRID) for x,y in GRID)


def positions(song):
    """Extract only placed, finite, in-range coordinates for the fixed Vibe maps."""
    result = {}
    profiles = song.get('vibe_maps') or {}
    for key, *_ in MAPS:
        point = profiles.get(key) or {}
        x,y = point.get('x'),point.get('y')
        if (point.get('status') == 'placed' and
            all(isinstance(v,(int,float)) and not isinstance(v,bool)
                and math.isfinite(v) and -1 <= v <= 1 for v in (x,y))):
            result[key] = (x,y)
    return result


def point_similarity(a,b):
    """Measure Gaussian proximity between two coordinates using the fixed similarity
    width.
    """
    return math.exp(-sum((x-y)**2 for x,y in zip(a,b))/(2*WIDTH**2))


class SongVibeBias:
    def __init__(self, songs):
        self.profiles = {s['id']:positions(s) for s in songs}
        self.coverage = (sum(map(len,self.profiles.values())) /
                         (len(MAPS)*len(self.profiles))) if self.profiles else 0
        self.strength = MAX_BIAS*self.coverage

    def multiplier(self, anchor, candidate):
        """Compute a bounded song-draw multiplier from shared Vibe coordinates,
        leaving missing maps neutral.
        """
        a,b = self.profiles.get(anchor,{}),self.profiles.get(candidate,{})
        common = a.keys() & b.keys()
        # Missing/not-applicable maps contribute no evidence, never a fake centre.
        score = sum(2*point_similarity(a[key],b[key])-1 for key in common)/len(MAPS)
        return 1+self.strength*score


def density(points):
    """Soft histogram retaining multiple hotspots instead of only a centroid."""
    bins = [0.0]*len(GRID)
    for x,y in points:
        px,py = (x+1)*2,(y+1)*2
        ix,iy = min(3,int(px)),min(3,int(py))
        dx,dy = px-ix,py-iy
        for gx,wx in ((ix,1-dx),(ix+1,dx)):
            for gy,wy in ((iy,1-dy),(iy+1,dy)):
                bins[gx*5+gy] += wx*wy
    smoothed = [sum(weight*k for weight,k in zip(bins,row)) for row in KERNEL]
    norm = math.sqrt(sum(v*v for v in smoothed))
    return tuple(v/norm for v in smoothed) if norm else ()


class AlbumVibeBias:
    def __init__(self, groups):
        self.profiles = {}
        placed,total = 0,0
        for aid,tracks in groups.items():
            unique = {s['id']:s for s in tracks}
            profiles = [positions(s) for s in unique.values()]
            total += len(MAPS)*len(profiles)
            placed += sum(map(len,profiles))
            self.profiles[aid] = {}
            for key,*_ in MAPS:
                points = [p[key] for p in profiles if key in p]
                if points:
                    self.profiles[aid][key] = (density(points),len(points)/len(profiles))
        self.coverage = placed/total if total else 0
        self.strength = MAX_BIAS*self.coverage

    def multiplier(self, anchor, candidate):
        """Compute a coverage-aware album-draw multiplier from overlapping Vibe
        distributions.
        """
        a,b = self.profiles.get(anchor,{}),self.profiles.get(candidate,{})
        score = 0
        for key in a.keys() & b.keys():
            va,ca = a[key];vb,cb = b[key]
            overlap = min(1.0,max(0.0,sum(x*y for x,y in zip(va,vb))))
            score += (2*overlap-1)*min(ca,cb)/len(MAPS)
        return 1+self.strength*score


def compare_profiles(first,second):
    """Fixed Gaussian closeness of shared maps' RMS distance, not a probability.

    Squared distance makes a mismatched map count instead of being diluted by
    other close maps. WIDTH is fixed, so more catalogue data never rescales a pair.
    Missing/N/A maps supply no evidence, never a zero point. Draw bias is unchanged.
    """
    a,b=positions({'vibe_maps':first}),positions({'vibe_maps':second})
    return compare_positions(a,b)


def compare_positions(a,b):
    """Same public metric for already validated vectors; shared by batch reports."""
    shared=[values[0] for values in MAPS if values[0] in a and values[0] in b]
    mean_squared=(sum(sum((x-y)**2 for x,y in zip(a[key],b[key])) for key in shared)/len(shared)) if shared else None
    return dict(similarity=100*math.exp(-mean_squared/(2*WIDTH**2)) if mean_squared is not None else None,
                shared_maps=len(shared),map_ids=shared,coverage=len(shared)/len(MAPS))
