#!/usr/bin/env python2.7
# Copyright (C) 2017 Daniel Asarnow
# University of California, San Francisco
#
# Simple map modification utility.
# See help text and README file for more information.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import print_function
import json
import logging
import numpy as np
import sys
from pyem.mrc import read
from pyem.mrc import write
from pyem.util import euler2rot
from pyem.util import rot2euler
from pyem.util import vec2rot
from scipy.ndimage import affine_transform
from scipy.ndimage import map_coordinates
from scipy.ndimage import shift


def main(args):
    log = logging.getLogger(__name__)
    log.setLevel(logging.INFO)
    hdlr = logging.StreamHandler(sys.stdout)
    if args.quiet:
        hdlr.setLevel(logging.ERROR)
    elif args.verbose:
        hdlr.setLevel(logging.INFO)
    else:
        hdlr.setLevel(logging.WARN)
    log.addHandler(hdlr)

    data, hdr = read(args.input, inc_header=True)
    final = None
    box = np.array([hdr[a] for a in ["nx", "ny", "nz"]])

    if args.normalize:
        if args.reference is not None:
            ref, refhdr = read(args.reference, inc_header=True)
            sigma = np.std(ref)
        else:
            sigma = np.std(data)

        mu = np.mean(data)
        final = (data - mu) / sigma
        if args.verbose:
            log.info("Mean: %f, Standard deviation: %f" % (mu, sigma))

    if args.apix is None:
        args.apix = hdr["xlen"] / hdr["nx"]
        log.info("Using computed pixel size of %f Angstroms" % args.apix)

    if args.target and args.matrix:
        log.warn("Target pose transformation will be applied after explicit matrix")
    if args.euler is not None and (args.target is not None or args.matrix is not None):
        log.warn("Euler transformation will be applied after target pose transformation")
    if args.translate is not None and (args.euler is not None or args.target is not None or args.matrix is not None):
        log.warn("Translation will be applied after other transformations")

    if args.origin is not None:
        try:
            args.origin = np.array([np.double(tok) for tok in args.origin.split(",")]) / args.apix
            assert np.all(args.origin < box)
        except:
            log.error("Origin must be comma-separated list of x,y,z coordinates and lie within the box")
            return 1
    else:
        args.origin = box / 2
        log.info("Origin set to box center, %s" % (args.origin * args.apix))

    if ismask(data) and args.spline_order != 0:
        log.warn("Input looks like a mask, --spline-order 0 (nearest neighbor) is recommended")

    if args.matrix is not None:
        try:
            r = np.array(json.loads(args.matrix))
        except:
            log.error("Matrix format is incorrect")
            return 1
        data = resample_volume(data, r=r, t=None, ori=None, order=args.spline_order)
        

    if args.target is not None:
        try:
            args.target = np.array([np.double(tok) for tok in args.target.split(",")]) / args.apix
        except:
            log.error("Standard pose target must be comma-separated list of x,y,z coordinates")
            return 1
        args.target -= args.origin
        r = vec2rot(args.target)
        t = np.linalg.norm(args.target)
        log.info("Euler angles are %s deg and shift is %f px" % (np.rad2deg(rot2euler(r)), t))
        data = resample_volume(data, r=r, t=args.target, ori=args.origin, order=args.spline_order)

    if args.euler is not None:
        try:
            args.euler = np.deg2rad(np.array([np.double(tok) for tok in args.euler.split(",")]))
        except:
            log.error("Eulers must be comma-separated list of phi,theta,psi angles")
            return 1
        r = euler2rot(*args.euler)
        offset = args.origin - 0.5
        offset = offset - r.T.dot(offset)
        data = affine_transform(data, r.T, offset=offset, order=args.spline_order)

    if args.translate is not None:
        try:
            args.translate = np.array([np.double(tok) for tok in args.translate.split(",")]) / args.apix
        except:
            log.error("Translation vector must be comma-separated list of x,y,z coordinates")
            return 1
        args.translate -= args.origin
        data = shift(data, -args.translate, order=args.spline_order)

    if final is None:
        final = data

    write(args.output, final, psz=args.apix)
    return 0


def ismask(vol):
    """
    Even with a soft edge, a mask will have very few unique values (unless it's already been resampled).
    The 1D slice below treats just the central XY section for speed. Real maps have ~20,000 unique values here.
    """
    return np.unique(vol[vol.shape[2]/2::vol.shape[2]]).size < 100


def resample_volume(vol, r=None, t=None, ori=None, order=3):
    if r is None and t is None:
        return vol.copy()

    if ori is None:
        ori = np.array(vol.shape) / 2

    x, y, z = np.meshgrid(*[np.arange(-o,o) for o in ori], indexing="xy")
    xyz = np.vstack([x.reshape(-1), y.reshape(-1), z.reshape(-1), np.ones(x.size)])
    
    th = np.eye(4)
    if t is None and r.shape[1] == 4:
        t = np.squeeze(r[:,3]) - ori
    elif t is not None:
        th[:3,3] = t - ori
    
    rh = np.eye(4)
    if r is not None:
        rh[:3:,:3] = r[:3,:3].T

    xyz = th.dot(rh.dot(xyz))[:3,:] + ori[:, None]
    xyz = np.array([xyz[a].reshape(vol.shape) for a in xrange(len(xyz))])

    newvol = map_coordinates(vol, xyz, order=order)
    return newvol


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Use equals sign when passing arguments with negative numbers.")
    parser.add_argument("input", help="Input volume (MRC file)")
    parser.add_argument("output", help="Output volume (MRC file)")
    parser.add_argument("--apix", "--angpix", "-a", help="Pixel size in Angstroms", type=float)
    parser.add_argument("--normalize", "-n", help="Convert map densities to Z-scores", action="store_true")
    parser.add_argument("--reference", "-r", help="Normalization reference volume (MRC file)")
    parser.add_argument("--origin", help="Origin coordinates in Angstroms (volume center by default)", metavar="x,y,z")
    parser.add_argument("--target", help="Target pose (view axis and origin) coordinates in Angstroms", metavar="x,y,z")
    parser.add_argument("--euler", help="Euler angles in degrees (Relion conventions)", metavar="phi,theta,psi")
    parser.add_argument("--translate", help="Translation coordinates in Angstroms", metavar="x,y,z")
    parser.add_argument("--matrix", help="Transformation matrix (3x3 or 3x4 with translation in Angstroms) in Numpy/json format")
    parser.add_argument("--spline-order", help="Order of spline interpolation (0 for nearest, 1 for trilinear, default is cubic)",
                        type=int, default=3, choices=np.arange(6))
    parser.add_argument("--quiet", "-q", help="Print errors only", action="store_true")
    parser.add_argument("--verbose", "-v", help="Print info messages", action="store_true")
    sys.exit(main(parser.parse_args()))

