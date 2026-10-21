"""Small, coverage-scaled similarity adjustments; no eligibility or rating changes."""
import math
from songranker.storage.vibe_state import MAPS

MAX_BIAS = .15
WIDTH = .65
GRID = tuple((x/2-1, y/2-1) for x in range(5) for y in range(5))
KERNEL = tuple(tuple(math.exp(-((x-a)**2+(y-b)**2)/(2*WIDTH**2))
                     for a,b in GRID) for x,y in GRID)


def positions(song):
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
    return math.exp(-sum((x-y)**2 for x,y in zip(a,b))/(2*WIDTH**2))


class SongVibeBias:
    def __init__(self, songs):
        self.profiles = {s['id']:positions(s) for s in songs}
        self.coverage = (sum(map(len,self.profiles.values())) /
                         (len(MAPS)*len(self.profiles))) if self.profiles else 0
        self.strength = MAX_BIAS*self.coverage

    def multiplier(self, anchor, candidate):
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
        a,b = self.profiles.get(anchor,{}),self.profiles.get(candidate,{})
        score = 0
        for key in a.keys() & b.keys():
            va,ca = a[key];vb,cb = b[key]
            overlap = min(1.0,max(0.0,sum(x*y for x,y in zip(va,vb))))
            score += (2*overlap-1)*min(ca,cb)/len(MAPS)
        return 1+self.strength*score


def compare_profiles(first,second):
    """Public percentage, independent of the small adaptive draw multiplier.

    Each shared map has equal weight. Identical points are 100%; opposite
    corners are 0%. Missing/N/A maps supply no evidence, never a zero point.
    """
    a,b=positions({'vibe_maps':first}),positions({'vibe_maps':second})
    shared=[values[0] for values in MAPS if values[0] in a and values[0] in b]
    closeness=(sum(1-math.dist(a[key],b[key])/(2*math.sqrt(2)) for key in shared)/len(shared)) if shared else None
    return dict(similarity=100*max(0,min(1,closeness)) if closeness is not None else None,
                shared_maps=len(shared),map_ids=shared,coverage=len(shared)/len(MAPS))
