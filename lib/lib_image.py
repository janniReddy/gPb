import numpy as np
import cv2
import math
import scipy.signal

from oe_filters import oe_filters
from textons import textons

def grayscale(L, a, b):
    """Compute a grayscale image from an RGB image."""
    print("inside gray scale function.............")
    g_im = np.empty(L.shape)
    g_im.dtype = L.dtype
    g_im = (0.29894 * L) + (0.58704 * a) + (0.11402 * b)
    return g_im

def rgb_to_lab(L, a, b):
    """Convert from RGB color space to Lab color space."""
    print("inside rgb to lab")
    # convert RGB to XYZ
    x_l = (0.412453 * L) +  (0.357580 * a) + (0.180423 * b)
    y_a = (0.212671 * L) +  (0.715160 * a) + (0.072169 * b)
    z_b = (0.019334 * L) +  (0.119193 * a) + (0.950227 * b)
    # D65 white point reference
    x_ref = 0.950456
    y_ref = 1.000000
    z_ref = 1.088754
    # threshold value
    threshold = 0.008856
    # convert XYZ to Lab
    for i in range(0, L.shape[0]):
        for j in range(0, L.shape[1]):
            x = x_l[i][j] / x_ref
            y = y_a[i][j] / y_ref
            z = z_b[i][j] / z_ref
            # compute fx, fy, fz
            if x > threshold:
                fx = math.pow(x,(1.0/3.0))
            else:
                fx = (7.787*x + (16.0/116.0))

            if y > threshold:
                fy = math.pow(y,(1.0/3.0))
            else:
                fy = (7.787*y + (16.0/116.0))
            
            if z > threshold:
                fz = math.pow(z,(1.0/3.0))
            else:
                fz = (7.787*z + (16.0/116.0))

            # compute Lab color value
            if y > threshold:
                x_l[i][j] = (116*math.pow(y,(1.0/3.0)) - 16)
            else:
                x_l[i][j] = 903.3*y
            
            y_a[i][j] = 500 * (fx - fy)
            z_b[i][j] = 200 * (fy - fz)
    return [x_l, y_a, z_b]

def lab_normalize(l, a, b):
    """Normalize an Lab image so that values for each channel lie in [0,1]."""
    print("inside lab_normalize")
    # range for a, b channels
    ab_min = -73
    ab_max = 95
    ab_range = ab_max - ab_min
    # normalize Lab image
    for i in range(0, l.shape[0]):
        for j in range(0, l.shape[1]):
            l_val = l[i][j] / 100.0
            a_val = (a[i][j] - ab_min) / ab_range
            b_val = (b[i][j] - ab_min) / ab_range
            if l_val < 0:
                l_val = 0
            elif l_val > 1:
                l_val = 1
            
            if a_val < 0:
                a_val = 0
            elif a_val > 1:
                a_val = 1

            if b_val < 0:
                b_val = 0
            elif b_val > 1:
                b_val = 1
            l[i][j] = l_val
            a[i][j] = a_val
            b[i][j] = b_val
    return [l, a, b]


def quantize_values(src, n_bins):
    if(0 == n_bins):
        print("n_bins must be > 0")
        return
    dest = np.empty(src.shape)
    # dest.dtype = src.dtype
    for i in range(0, src.shape[0]):
        for j in range(0, src.shape[1]):
            d_bin = int(math.floor(src[i][j]*float(n_bins)))
            if d_bin == n_bins:
                d_bin = n_bins - 1
            dest[i][j] = d_bin
    return dest

def texton_filters(n_ori):
    """computes texton filters"""
    start_sigma = 1
    num_scales = 2
    scaling = math.sqrt(2)
    elongation = 2
    support = 3
    filter_bank = np.zeros((len(range(1, n_ori + 1))*2, len(range(1, num_scales + 1)))).tolist()
    for idx0, scale in enumerate(range(1, num_scales + 1)):
        sigma = start_sigma * (scaling**(scale - 1))
        for orient in range(1, n_ori + 1):
            theta = (orient-1)/float(n_ori) * math.pi
            filter_bank[(2*orient)-2][idx0] = oe_filters([sigma*elongation, sigma], support, theta, 2, 0)
            filter_bank[(2*orient)-1][idx0] = oe_filters([sigma*elongation, sigma], support, theta, 2, 1)

    return filter_bank

def compute_textons(g_im, border, filters, k):
    return textons(g_im, border, filters, k)

def gaussian(sigma = 1, deriv = 0, hlbrt = False):
    """
    * Gaussian kernel (1D).
    *
    * Specify the standard deviation and (optionally) the support.
    * The length of the returned vector is 2*support + 1.
    * The support defaults to 3*sigma.
    * The kernel is normalized to have unit L1 norm.
    * If returning a 1st or 2nd derivative, the kernel has zero mean."""
    print("inside gaussian function")
    support = math.ceil(3*sigma)
    # enlarge support so that hilbert transform can be done efficiently
    support_big = support
    if hlbrt:
        support_big = 1
        temp = support
        while temp > 0:
            support_big *= 2
            temp /= 2

    # compute constants
    sigma2_inv = 1/(sigma * sigma)
    neg_two_sigma2_inv = (-0.5) * sigma2_inv
    # compute gaussian (or gaussian derivative)
    size = 2 * support_big + 1
    m = np.zeros((size))
    print(m.shape)
    x = -(support_big)
    if deriv == 0:
        # compute gaussian
        for n in range(0, size):
            m[n] = math.exp(x * x * neg_two_sigma2_inv)
            x += 1
    elif deriv == 1:
        # compute gaussian first derivative
        for n in range(0, size):
            m[n] = math.exp(x * x * neg_two_sigma2_inv) * (-x)
            x += 1
    elif deriv == 2:
        # compute gaussian second derivative
        for n in range(0, size):
            x2 = x * x
            m[n] = math.exp(x2 * neg_two_sigma2_inv) * (x2 * sigma2_inv -1)
            x += 1
    else:
        print(" only derivatives 0,1,2 supported")

    # take hilbert transform (if requested)
    if hlbrt:
        # grab power of two sized submatrix (ignore last element)
        m = scipy.signal.hilbert(m).imag
    
    #zero mean
    if deriv>0:
        m = m - np.mean(m)

    #unit L1-norm
    sumf = np.sum(np.abs(m))
    if sumf>0:
        m = m / sumf
    
    return m

def border_trim_2D(m, r):
    return m[r:-r,r:-r]

def weight_matrix_disc(r):
    """Construct weight matrix for circular disc of the given radius."""
    # initialize weights array
    size = 2 * r + 1
    weights = np.zeros((size, size))
    # set values in disc to 1
    radius = r
    r_sq = radius * radius
    for x in range(-radius, radius + 1):
        x_sq = x * x
        for y in range(-radius, radius + 1):
            # check if index is within disc
            y_sq = y * y
            if ((x_sq + y_sq) <= r_sq):
                weights[abs(x)][abs(y)] = 1
    return weights




def hist_gradient_2D(labels, r, n_ori, smoothing_kernel):
    """* Compute the distance between histograms of label values in oriented
    * half-dics of the specified radius centered at each location in the 2D
    * matrix.  Return one distance matrix per orientation.
    *
    * Alternatively, instead of specifying label values at each point, the user
    * may specify a histogram at each point, in which case the histogram for
    * a half-disc is the sum of the histograms at points in that half-disc.
    *
    * The half-disc orientations are k*pi/n for k in [0,n) where n is the 
    * number of orientation requested.
    *
    * The user may optionally specify a nonempty 1D smoothing kernel to 
    * convolve with histograms prior to computing the distance between them.
    *
    * The user may also optionally specify a custom functor for computing the
    * distance between histograms."""
    # construct weight matrix for circular disc
    weights = weight_matrix_disc(r)

    # check arguments - weights
    if len(weights.shape) != 2:
        print("weight matrix must be 2D")
        return

    # check arguments - labels
    if len(labels.shape) != 2:
        print("label matrix must be 2D")
        return

    w_size_x = weights.shape[0]
    w_size_y = weights.shape[1]

    if (((w_size_x/2) == ((w_size_x+1)/2)) or ((w_size_y/2) == ((w_size_y+1)/2))):
        print ("dimensions of weight matrix must be odd")

    # allocate result gradient
    gradients = np.zeros((n_ori)).tolist()
    
    # check that result is nontrivial
    if n_ori == 0:
        return gradients
    # to hold histograms of each slice
    slice_hist = np.zeros((2 * n_ori)).tolist()
    hist_length = labels.max() + 1
    for i in range(0, 2*n_ori):
        slice_hist[i] = np.zeros((hist_length))
    # build orientation slice lookup map 
    slice_map = orientation_slice_map(w_size_x, w_size_y, n_ori)
    # compute histograms and histogram differences at each location
    # compute_hist_gradient_2D(labels, weights, slice_map, smoothing_kernel, slice_hist, gradients)
    # get label matrix size
    size0_x = labels.shape[0]
    size0_y = labels.shape[1]
    # get window size
    size1_x = weights.shape[0]
    size1_y = weights.shape[1]
    # set start position for gradient matrices
    pos_start_x = size1_x/2
    pos_start_y = size1_y/2
    pos_bound_y = pos_start_y + size0_y
    # initialize position in result
    pos_x = pos_start_x
    pos_y = pos_start_y
    # compute initial range of offset_x
    offset_min_x = ((pos_x + 1) > size0_x) ? (pos_x + 1 - size0_x) : 0
    offset_max_x = (pos_x < size1_x) ? pos_x : (size1_x - 1)
    return gradients




def orientation_slice_map(size_x, size_y, n_ori):
    # Initialize map
    slice_map = np.zeros((size_x, size_y))
    # compute orientation of each element from center
    x = -(size_x) / 2
    for n_x in range(0,size_x):
        y = -(size_y) / 2
        for n_y in range(0, size_y):
            # compute orientation index
            ori = math.atan2(y, x) + math.pi
            idx = ori / math.pi * n_ori
            if idx >= (2 * n_ori):
                idx = 2 * n_ori -1
            slice_map[n_x][n_y] = idx
            y += 1
        x += 1
    return slice_map
