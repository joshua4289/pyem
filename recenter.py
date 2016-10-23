#! /usr/bin/python2.7
# Copyright (C) 2016 Daniel Asarnow
# University of California, San Francisco
import glob
import logging
import sys
import numpy as np
from pathos.multiprocessing import Pool
from scipy.ndimage.interpolation import affine_transform
from EMAN2 import EMData, Vec3f


def main(args):
    inp = glob.glob(args.input)

    pool = None
    if args.nproc > 1:
        pool = Pool(args.nproc)

    else:
        results = ()

    return 0


def recenter(inp, tr=None):
    if "mrc" in inp[-4:]:
        im = EMData(inp)
        if im.get_ndim() == 3:
            com = Vec3f(*im.phase_cog()[:3])
            im.set_translation(-com)


def find_cm(im):
    l = np.floor(im.shape[0] / 2)
    x, y = np.meshgrid(np.arange(-l, l, dtype=np.double), np.arange(-l, l, dtype=np.double))
    mu_x = np.average(x, axis=None, weights=im)
    mu_y = np.average(y, axis=None, weights=im)
    return mu_x, mu_y


def recenter2d(im, cm, y=None):
    if len(cm) == 1 and y is None:
        t = np.array([[1, 0, cm], [0, 1, cm]])
    elif len(cm) == 1 and len(y) == 1:
        t = np.array([[1, 0, cm], [0, 1, y]])
    else:
        t = np.array([[1, 0, cm[0]], [0, 1, cm[1]]])
    return affine_transform(im, t)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--loglevel", "-l", help="Logging level")
    parser.add_argument("--mask", "-m", help="Size of circular particle mask")
    parser.add_argument("--nproc", "-n", help="Number of parallel processes")
    parser.add_argument("--prefix", "-p", help="Prefix to be prepended to output file names")
    parser.add_argument("--translations", "-t", help="File to note translation applied to each particle")
    parser.add_argument("input", help="Input .star or .mrc(s) file(s)")
    parser.add_argument("output", help="Output destination")

    args = parser.parse_args()

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.getLevelName(args.loglevel.upper()))

    sys.exit(main(args))
