"""Conservative relative weights for comparable, exposure-normalized frames."""
import numpy as np


def quality_weights(rows):
    weights=np.ones(len(rows),dtype=np.float32)
    groups={}
    for i,row in enumerate(rows):
        if row and row.get('stars',0)>=6 and all(isinstance(row.get(k),(int,float,np.number)) and np.isfinite(row[k]) and row[k]>0 for k in ('fwhm','elongation','noise')):
            groups.setdefault(row['group'],[]).append(i)
    for indices in groups.values():
        if len(indices)<2:continue
        widths=np.array([rows[i]['fwhm'] for i in indices]);noise=np.array([rows[i]['noise'] for i in indices]);elong=np.array([rows[i]['elongation'] for i in indices])
        raw=(np.median(noise)/noise)**2*(np.median(widths)/widths)**2*(np.median(elong)/elong)**2
        weights[indices]=np.clip(raw/np.median(raw),.25,4)
    return weights
