#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tc: CIE TC1-82 Computations

Copyright (C) 2012-2013 Ivar Farup and Jan Henrik Wold

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
import numpy as np
import scipy.optimize
import scipy.interpolate
from scipy.spatial import Delaunay

#==============================================================================
# Tabulated and derived visual data
#==============================================================================

def my_round(x,n=0):
    """
    Round array x to n decimal points using round half away from zero.
    
    Parameters
    ----------
    x : ndarray
        Array to be rounded
    n : int
        Number of decimal points
    
    Returns
    -------
    y : ndarray
        Rounded array
    """
    s = np.sign(x)
    return s*np.floor(np.absolute(x)*10**n + 0.5)/10**n
    
def significant_figures(x,n=0):
    """
    Round x to n significant figures (not decimal points).
    
    Parameters
    ----------
    x : int, float or ndarray
        Number or array to be rounded.
    
    Returns
    -------
    t : float or ndarray
        Rounded number or array.
    """
    if type(x) == float or type(x) == int:
        if x == 0.:
            return 0
        else:
            b = np.ceil(np.log10(x))
            return 10**b*my_round(x/10**b, n)
    b = x.copy()
    b[x == 0] = 0
    b[x != 0] = np.ceil(np.log10(abs(x[x != 0])))
    return 10**b*my_round(x/10**b, n)

def resource_path(relative):
    """
    Extend relative path to full path (mainly for PyInstaller integration).
    """
    return os.path.join(
        os.environ.get(
            "_MEIPASS2",
            os.path.abspath(".")
        ),
        relative
    )
    
def read_csv_file(filename, pad=-np.inf):
    """
    Read a CSV file and return pylab array.

    Parameters
    ----------
    filename : string
        Name of the CSV file to read
    pad : float
        Value to pad for missing values.
    
    Returns
    -------
    csv_array : ndarray
        The content of the file plus padding.
    """
    f = open(resource_path(filename))
    data = f.readlines()
    for i in range(len(data)):
        data[i] = data[i].split(',')
        for j in range(len(data[i])):
            if data[i][j].strip() == '':
                data[i][j] = pad
            else:
                data[i][j] = float(data[i][j])
    return np.array(data)

def chromaticities_from_XYZ(xyz31, xyz64):
    """
    Compute chromaticities and knots (for interpolation) from XYZ functions.

    Parameters
    ----------
    xyz31 : ndarray
        CIE 1931 colour matching functions
    xyz64 : ndarray
        CIE 1964 colour matching functions

    Returns
    -------
    cc31 : ndarray
        Chromaticities for the 1931 colour matching functions.
    cc64 : ndarray
        Chromaticities for the 1964 colour matching functions.
    cc31knots : ndarray
        Knots for interpolating the chromaticities.
    cc64knots : ndarray
        Knots for interpolating the chromaticities.
    """
    cc31 = xyz31.copy()
    cc31sum = np.sum(cc31[:,1:], axis=1)
    cc64 = xyz64.copy()
    cc64sum = np.sum(cc64[:,1:], axis=1)
    for i in range(1,4):
        cc31[:,i] = cc31[:,i]/cc31sum
        cc64[:,i] = cc64[:,i]/cc64sum

    cc31knots = np.array([cc31[0,0],
                          cc31[np.argmin(cc31[:,1]),0],
                          cc31[np.argmax(cc31[:,2]),0],
                          700,
                          cc31[-1,0]])
                          
    cc64knots = np.array([cc64[0,0],
                          cc64[np.argmin(cc64[:,1]),0],
                          cc64[np.argmax(cc64[:,2]),0],
                          700,
                          cc64[-1,0]])
    return cc31, cc64, cc31knots, cc64knots

def gauss_func(param, docul2):
    """
    Gaussian function to be fitted to docul2.
    
    Parameters
    ----------
    param : ndarray
        Parameters b and x0 of the Gaussian
    docul2 : ndarray
        The tabulated docul2 function
    
    Returns
    -------
    gauss_func : ndarray
        The tabulated Gaussian function with the given parameters
    """
    b = param[0]
    x0 = param[1]
    f = 4*np.exp(-b*(docul2[:,0]-x0)**2)
    return f

def rms_error(param, docul2):
    """
    RMS error between docul2 and gaussian function.
    
    For use in optimisation in function docul_fine.
    
    Parameters
    ----------
    param : ndarray
        Parameters b and x0 of the Gaussian
    docul2 : ndarray
        The tabulated docul2 function
    
    Returns
    -------
    rms_error : float
        The RMS error
    """
    f = gauss_func(param, docul2)
    return sum((f - docul2[:,1])**2)

def docul_fine(ocular_sum_32, docul2):
    """
    Calculate the two parts of docul.
    
    Parameters
    ----------
    ocular_sum_32 : ndarray
        Sum of two ocular functions
    docul2 : ndarray
        
    Returns
    -------
    docul1_fine : ndarray
        Tabulated docul1 with high resolution
    docul2_fine : ndarray
        Tabulated docul2 with high resolution
    """
    param = scipy.optimize.fmin(rms_error, [8e-4, 350], (docul2,), disp=False)
    docul2_add = np.array([[390, 4*np.exp(-param[0]*(390 - param[1])**2)],
                           [395, 4*np.exp(-param[0]*(395 - param[1])**2)]])
    docul2_pad = np.zeros((75,2))
    docul2_pad[:,0] = np.arange(460, 835, 5)
    docul2_pad[:,1] = 0
    docul2 = np.concatenate((docul2_add, docul2, docul2_pad))
    spl = scipy.interpolate.InterpolatedUnivariateSpline(docul2[:,0],
                                                         docul2[:,1])
    docul2_fine = ocular_sum_32.copy()
    docul2_fine[:,1] = spl(ocular_sum_32[:,0])
    docul1_fine = ocular_sum_32.copy()
    docul1_fine[:,1] = ocular_sum_32[:,1] - docul2_fine[:,1]
    return docul1_fine, docul2_fine
    
class VisualData:
    """
    Class containing all visual data input to the computations.
    
    All data are read from files in the 'data' folder.
    """
    absorbance = read_csv_file('data/ssabance_fine.csv')
    ocular_sum_32 = read_csv_file('data/lensss_fine.csv') # 32 years only!!!
    macula = read_csv_file('data/macss_fine.csv')
    lms10_log_quant = read_csv_file('data/ss10q_fine_8dp.csv')
    lms10_lin_energ = read_csv_file('data/linss10e_fine_8dp.csv', 0)
    lms10_lin_energ_n_signfig = read_csv_file('data/linss10e_fine.csv', 0)
    lms2_log_quant = read_csv_file('data/ss2_10q_fine_8dp.csv')
    lms2_lin_energ = read_csv_file('data/linss2_10e_fine_8dp.csv', 0)
    lms2_lin_energ_n_signfig = read_csv_file('data/linss2_10e_fine.csv', 0)
    vlambdaLM_10_lin_energ = read_csv_file('data/linCIE2008v10e_fine_8dp.csv')
    vlambdaLM_2_lin_energ = read_csv_file('data/linCIE2008v2e_fine_8dp.csv')
    vlambdaLM_10_log_quant = read_csv_file('data/logCIE2008v10q_fine_8dp.csv')
    vlambdaLM_2_log_quant = read_csv_file('data/logCIE2008v2q_fine_8dp.csv')
    xyz31 = read_csv_file('data/ciexyz31_1.csv')
    xyz64 = read_csv_file('data/ciexyz64_1.csv')
    docul2 = read_csv_file('data/docul2.csv')

    cc31, cc64, cc31knots, cc64knots = chromaticities_from_XYZ(xyz31, xyz64)
    docul1_fine, docul2_fine = docul_fine(ocular_sum_32, docul2)
    
#==============================================================================
# Compute absorptance data from tabulated cone fundamentals; do we need these?
#==============================================================================

def absorptance_from_lms10q():
    """
    Compute the absorptance from quantal lms 10 for reference.
    """
    absorptance = VisualData.lms10_log_quant.copy()
    absorptance[:,1:] = 10**(absorptance[:,1:])
    for i in range(1,4):
        absorptance[:,i] = absorptance[:,i]/ \
            10**(-d_mac_max(10)*VisualData.macula[:,1]/.35 -
                 VisualData.ocular_sum_32[:,1])
        absorptance[:,i] = absorptance[:,i]/absorptance[:,i].max()
    return absorptance

def absorbance_from_lms10q():
    """
    Compute the absorbance from quantal lms 10 for reference.
    """
    absorbance = absorptance_from_lms10q(VisualData.lms10_log_quant)
    absorbance[:,1] = np.log10(1 - absorbance[:,1] * \
                                   (1 - 10**-d_LM_max(10))) / \
                                   -d_LM_max(10)
    absorbance[:,2] = np.log10(1 - absorbance[:,2] * \
                                   (1 - 10**-d_LM_max(10))) / \
                                   -d_LM_max(10)
    absorbance[:,3] = np.log10(1 - absorbance[:,3] * \
                                   (1 - 10**-d_S_max(10))) / \
                                   -d_S_max(10)
    return absorbance

#==============================================================================
# Functions of age and field size
#==============================================================================

def chromaticity_interpolated(field_size):
    """
    Compute the spectral chromaticity coordinates by interpolation for
    reference.
    
    Parameters
    ----------
    field_size : float
        The field size in degrees.
         
    Returns
    -------
    chromaticity : ndarray
        The xyz chromaticities, with wavelenghts in first column.
    """
    alpha = (field_size - 2)/8.
    knots = (1 - alpha)*VisualData.cc31knots + alpha*VisualData.cc64knots
    knots[0] = 360.
    knots[-1] = 830.
    lambd = np.arange(360., 831.)

    lambda31_func = scipy.interpolate.interp1d(knots, VisualData.cc31knots, kind='linear')
    lambda64_func = scipy.interpolate.interp1d(knots, VisualData.cc64knots, kind='linear')
    lambda31 = lambda31_func(lambd)
    lambda64 = lambda64_func(lambd)

    # x values
    cc31x_func = scipy.interpolate.interp1d(VisualData.cc31[:,0],
                                            VisualData.cc31[:,1],
                                            kind='cubic')
    cc64x_func = scipy.interpolate.interp1d(VisualData.cc64[:,0],
                                            VisualData.cc64[:,1],
                                            kind='cubic')
    cc31x = cc31x_func(lambda31)
    cc64x = cc64x_func(lambda64)
    xvalues = (1-alpha)*cc31x + alpha*cc64x
    # y values
    cc31y_func = scipy.interpolate.interp1d(VisualData.cc31[:,0],
                                            VisualData.cc31[:,2],
                                            kind='cubic')
    cc64y_func = scipy.interpolate.interp1d(VisualData.cc64[:,0],
                                            VisualData.cc64[:,2],
                                            kind='cubic')
    cc31y = cc31y_func(lambda31)
    cc64y = cc64y_func(lambda64)
    yvalues = (1-alpha)*cc31y + alpha*cc64y
    zvalues = 1 - xvalues - yvalues
    return np.concatenate((np.reshape(lambd, (471,1)),
                           np.reshape(xvalues, (471,1)),
                           np.reshape(yvalues, (471,1)),
                           np.reshape(zvalues, (471,1))), 1)

def ocular(age):
    """
    The optical density of the ocular media as a function of age.
    
    Computes a weighted average of docul1 and docul2.
    
    Parameters
    ----------
    age : float
        Age in years.
        
    Returns
    -------
    ocular : ndarray
        The optical density of the ocular media with wavelength in first column.
    """
    ocul = VisualData.docul2_fine.copy()
    if age < 60:
        ocul[:,1] = (1 + 0.02*(age - 32)) * VisualData.docul1_fine[:,1] + \
            VisualData.docul2_fine[:,1]
    else:
        ocul[:,1] = (1.56 + 0.0667*(age - 60)) * VisualData.docul1_fine[:,1] + \
            VisualData.docul2_fine[:,1]
    return ocul

def d_mac_max(field_size):
    """
    Maximum optical density of the macular pigment (function of field size).
    
    Parameters
    ----------
    field_size : float
        Field size in degrees.

    Returns
    -------
    d_mac_max : float
        Maximum optical density of the macular pigment.
    """
    return my_round(0.485*np.exp(-field_size/6.132), 3)

def d_LM_max(field_size):
    """
    Maximum optical density of the visual pigment (function of field size).
    
    Parameters
    ----------
    field_size : float
        Field size in degrees.

    Returns
    -------
    d_LM_max : float
        Maximum optical density of the visual pigment.
    """
    return my_round(0.38 + 0.54*np.exp(-field_size/1.333), 3)

def d_S_max(field_size):
    """
    Maximum optical density of the visual pigment (function of field size).
    
    Parameters
    ----------
    field_size : float
        Field size in degrees.

    Returns
    -------
    d_S_max : float
        Maximum optical density of the visual pigment.            
    """
    return my_round(0.30 + 0.45*np.exp(-field_size/1.333), 3)

def absorpt(field_size):
    """
    Compute quantal absorptance as a function of field size.
    
    Parameters
    ----------   
    field_size : float
        Field size in degrees.
        
    Returns
    -------
    absorpt : ndarray
        The computed lms functions, with wavelengths in first column.
    """
    abt = VisualData.absorbance.copy()
    abt[:,1] = 1 - 10**(-d_LM_max(field_size)*10**(VisualData.absorbance[:,1])) # L
    abt[:,2] = 1 - 10**(-d_LM_max(field_size)*10**(VisualData.absorbance[:,2])) # M
    abt[:,3] = 1 - 10**(-d_S_max(field_size)*10**(VisualData.absorbance[:,3]))  # S
    return abt

def lms_quantal(field_size, age):
    """
    Compute quantal cone fundamentals as a function of field size and age.
    
    Parameters
    ----------   
    field_size : float
        Field size in degrees.
    age : float
        Age in years.

    Returns
    -------
    lms : ndarray
        The computed lms functions, with wavelengths in first column.
    """
    abt = absorpt(field_size)
    lmsq = abt.copy()
    ocul = ocular(age)
    for i in range(1,4):
        lmsq[:,i] = abt[:,i] * \
            10**(-d_mac_max(field_size)*VisualData.macula[:,1]/.35 - ocul[:,1])
        lmsq[:,i] = lmsq[:,i]/(lmsq[:,i].max())
    return lmsq

def lms_energy_base(field_size, age):
    """
    Compute energy cone fundamentals as a function of field size and age.
    
    Parameters
    ----------   
    field_size : float
        Field size in degrees.
    age : float
        Age in years.

    Returns
    -------
    lms : ndarray
        The computed lms functions, with wavelengths in first column.
    lms_max : ndarray
        Max values of the lms functions before renormalisation.
    """
    if age == 32:
        if field_size == 2:
            return VisualData.lms2_lin_energ.copy(), 0  # dummy max value
        elif field_size == 10:
            return VisualData.lms10_lin_energ.copy(), 0 # dummy max value
    lms = lms_quantal(field_size, age)
    lms_max = []
    for i in range(1,4):
        lms[:,i] = lms[:,i]*lms[:,0]
        lms_max.append(lms[:,i].max())
        lms[:,i] = lms[:,i]/lms[:,i].max()    
    return significant_figures(lms, 9), np.array(lms_max)

def lms_energy(field_size, age, signfig=6):
    """
    Compute energy cone fundamentals as a function of field size and age.
    
    Parameters
    ----------   
    field_size : float
        Field size in degrees.
    age : float
        Age in years.
    signfig : int
        Number of significant figures in returned lms.

    Returns
    -------
    lms : ndarray
        The computed lms functions, with wavelengths in first column.
    lms_max : ndarray
        Max values of the lms functions before renormalisation.
    """
    if signfig == 6 and age == 32:
        if field_size == 2:
            return VisualData.lms2_lin_energ_n_signfig.copy(), 0  # dummy max value
        elif field_size == 10:
            return VisualData.lms10_lin_energ_n_signfig.copy(), 0 # dummy max value
    lms, lms_max = lms_energy_base(field_size, age)
    if signfig < 6 and age == 32:
        if field_size == 2:
            lms, lms_max = VisualData.lms2_lin_energ_n_signfig.copy(), 0  # dummy max value
        elif field_size == 10:
            lms, lms_max = VisualData.lms10_lin_energ_n_signfig.copy(), 0 # dummy max value
    return significant_figures(lms, signfig), lms_max

def v_lambda_quantal(field_size, age):
    """
    Compute the V(lambda) function as a function of field size and age.
    
    Parameters
    ----------
    field_size : float
        Field size in degrees.
    age : float
        Age in years.
        
    Returns
    -------
    v_lambda : ndarray
        The computed v_lambda function, with wavelengths in first column.
    """
    lms = lms_quantal(field_size, age)
    v_lambda = np.zeros((np.shape(lms)[0], 2))
    v_lambda[:,0] = lms[:,0]
    v_lambda[:,1] = 1.89*lms[:,1] + lms[:,2]
    v_lambda[:,1] = v_lambda[:,1]/v_lambda[:,1].max()
    return v_lambda

def v_lambda_energy_from_quantal(field_size, age):
    """
    Compute the V(lambda) function as a function of field size and age.
    
    Starting from quantal V(lambda).
    
    Parameters
    ----------
    field_size : float
        Field size in degrees.
    age : float
        Age in years.
        
    Returns
    -------
    v_lambda : ndarray
        The computed v_lambda function, with wavelengths in first column.
    """
    if age == 32:
        if field_size == 2:
            return VisualData.vlambdaLM_2_log_quant.copy()
        elif field_size == 10:
            return VisualData.vlambdaLM_10_log_quant.copy()
    v_lambda = v_lambda_quantal(field_size, age)
    v_lambda[:,1] = v_lambda[:,1]*v_lambda[:,0]
    v_lambda[:,1] = v_lambda[:,1]/v_lambda[:,1].max()
    return v_lambda

def v_lambda_energy_from_lms(field_size, age, v_lambda_signfig=7, mat_dp=8):
    """
    Compute the V(lambda) function as a function of field size and age.
    
    Starting from engergy scale LMS.
    
    Parameters
    ----------
    field_size : float
        Field size in degrees.
    age : float
        Age in years.
    v_lambda_signfig : int
        Number of significant figures in v_lambda.
    mat_dp : int
        Number of decimal places in transformation matrix.
        
    Returns
    -------
    v_lambda : ndarray
        The computed v_lambda function, with wavelengths in first column.
    weights : ndarray
        The two weighting factors in V(lambda) = a21*L(lambda) + \
                                                 a22*M(lambda)
    """
    if age == 32:
        if field_size == 2:
            return VisualData.vlambdaLM_2_lin_energ.copy(), \
            np.array([0.68990272, 0.34832189])
        elif field_size == 10:
            return VisualData.vlambdaLM_10_lin_energ.copy(), \
            np.array([0.69283932, 0.34967567])            
    lms, lms_max = lms_energy_base(field_size, age)
    v_lambda = np.zeros((np.shape(lms)[0], 2))
    v_lambda[:,0] = lms[:,0]
    v_lambda[:,1] = 1.89*lms_max[0]*lms[:,1] + lms_max[1]*lms[:,2]
    m = v_lambda[:,1].max()
    a21 = my_round(1.89*lms_max[0]/m, mat_dp)
    a22 = my_round(lms_max[1]/m, mat_dp)
    v_lambda[:,1] = significant_figures(a21*lms[:,1] + a22*lms[:,2], v_lambda_signfig)
    return v_lambda, np.array([a21, a22])

def projective_lms_to_cc_matrix(trans_mat):
    """
    Compute the matrtix for the projective transformation from lms to cc.
    
    Parameters
    ----------
    trans_mat : ndarray
        Transformation matrix from lms to xyz.
    
    Returns
    -------
    mat : ndarray
        Transformation matrix directly from lms to cc.
    """
    mat = trans_mat.copy()
    mat[2,0] = trans_mat[0,0] + trans_mat[1,0] + trans_mat[2,0]
    mat[2,1] = trans_mat[0,1] + trans_mat[1,1] + trans_mat[2,1]
    mat[2,2] = trans_mat[0,2] + trans_mat[1,2] + trans_mat[2,2]
    return mat

def square_sum(a13, a21, a22, a33, l_spline, m_spline, s_spline, v_spline,
               lambdas, lambda_ref_min, cc_ref, full_results=False,
               xyz_signfig=7, mat_dp=8):
    """
    Function to be optimised for a13.
    
    Parameters
    ----------
    a13 : ndarray
        1x1 array with parameter to optimise.
    a21, a22, a33 : float
        Parameters in matrix for LMS to XYZ conversion.
    l_spline, m_spline, s_spline, v_spline: InterPolatedUnivariateSpline
        LMS and V(lambda)
    lambdas : ndarray
        Tabulated lambda values according to chosen resolution.
    lambda_ref_min : float
        Lambda value for x(lambda_ref_min) = x_ref_min.
    cc_ref : ndarray
        Tabulated reference chromaticity coordinates at 1 nm steps.
    full_results : bool
        Return all or just the computed error.
    xyz_signfig : int
        Number of significant figures in XYZ.
    mat_dp : int
        Number of decimal places in transformation matrix.
    
    Returns
    -------
    err : float
        Computed error.
    trans_mat : ndarray
        Transformation matrix.
    lambda_test_min : float
        argmin(x(lambda)).
    ok : bool
        Hit the correct minimum wavelength.
    """
    # Stripping reference values according to Stockman-Sharpe
    cc_ref_trunk = cc_ref[30:,1:].T.copy()
    x_ref_min = cc_ref_trunk[0,:].min()
    # Computed by Mathematica, don't ask...:
    a11 = (-m_spline(lambda_ref_min)*v_spline(lambdas).sum() +
          a13*(s_spline(lambda_ref_min)*m_spline(lambdas).sum() -
          m_spline(lambda_ref_min)*s_spline(lambdas).sum())*(-1 +
          x_ref_min) + (a21*l_spline(lambda_ref_min) +
          a33*s_spline(lambda_ref_min))*m_spline(lambdas).sum()*x_ref_min +
          m_spline(lambda_ref_min)*(a22*m_spline(lambdas).sum() +
          v_spline(lambdas).sum())*x_ref_min) / ((m_spline(lambda_ref_min)*
          l_spline(lambdas).sum() - l_spline(lambda_ref_min) *
          m_spline(lambdas).sum()) * (-1 + x_ref_min))
    a12 = (l_spline(lambda_ref_min)*v_spline(lambdas).sum() -
          a13*(s_spline(lambda_ref_min)*l_spline(lambdas).sum() -
          l_spline(lambda_ref_min)*s_spline(lambdas).sum())*(-1 +
          x_ref_min) - ((a21*l_spline(lambda_ref_min) +
          a22*m_spline(lambda_ref_min) + a33*s_spline(lambda_ref_min)) *
          l_spline(lambdas).sum() +
          l_spline(lambda_ref_min)*v_spline(lambdas).sum())*x_ref_min) / \
          ((m_spline(lambda_ref_min)*
          l_spline(lambdas).sum() - l_spline(lambda_ref_min) *
          m_spline(lambdas).sum()) * (-1 + x_ref_min))
    a11 = my_round(a11[0], mat_dp)
    a12 = my_round(a12[0], mat_dp)
    a13 = my_round(a13[0], mat_dp)
    trans_mat = np.array([[a11, a12, a13], [a21, a22, 0], [0, 0, a33]])
    lms = np.array([l_spline(np.arange(390, 831)),
                    m_spline(np.arange(390, 831)),
                    s_spline(np.arange(390, 831))])
    xyz = np.dot(trans_mat, lms)
    xyz = significant_figures(xyz, xyz_signfig)
    cc = np.array([xyz[0,:]/(xyz[0,:] + xyz[1,:] + xyz[2,:]),
                   xyz[1,:]/(xyz[0,:] + xyz[1,:] + xyz[2,:]),
                   xyz[2,:]/(xyz[0,:] + xyz[1,:] + xyz[2,:])])
    err = ((cc - cc_ref_trunk)**2).sum()
    lambda_test_min = np.arange(390, 831)[cc[0,:].argmin()]
    ok = (lambda_test_min == lambda_ref_min)
    if full_results:
        return err, trans_mat, lambda_test_min, ok
    else:
        return err

def compute_tabulated(field_size, age, resolution=1, xyz_signfig=7, cc_dp=5,
                      mat_dp=8, lms_signfig=6, bm_dp=6, lm_dp=5):
    """
    Compute tabulated quantities as a function of field size and age.
    
    All functions are tabulated at given wavelength resolution.
    
    Parameters
    ----------
    field_size : float
        Field size in degrees.
    age : float
        Age in years.
    resolution : float
        Resolution of tabulated results in nm.
    xyz_signfig : int
        Number of significant figures in XYZ.
    cc_dp : int
        Number of decimal places in chromaticity coordinates.
    mat_dp : int
        Number of decimal places in transformation matrix.
    lms_signfig : int
        Number of significant figures in LMS standard
    bm_dp : int
        Number of decimal places in Boynton-MacLeod chromaticity coordinates.
    lm_dp : int
        Number of decimal places in the normalised lm coordinates.
    
    Returns
    -------
    xyz : ndarray
        The computed colour matching functions.
    cc : ndarray
        The chromaticity coordinates.
    cc_white : ndarray
        The chromaticity coordinates for equi-energy stimulus.
    mat : ndarray
        The 3x3 matrix for converting from LMS to XYZ.
    lms_standard : ndarray
        The computed LMS functions at the given standard resolution.
    lms_base : ndarray
        The computed LMS functions at full available resolution (9 sign. fig.).        
    bm : ndarray
        The computed Boynton-MacLeod chromaticity coordinates.
    bm_white : ndarray
        The Boynton-MacLeod coordinates for equi-energy stimulus.
    lm : ndarray
        The computed normalised lm coordinates.
    lm_white : ndarray
        The lm coordinates for equi-energy stimulus.
    lambda_test_min : int
        The wavelength of minimum x chromaticity value.
    purple_line_cc : ndarray
        Chromaticity coordinates for the endpoints of the purple line.
    purple_line_bm : ndarray
        Boynton-MacLeod coordinates for the endpoints of the purple line.
    purple_line_lm : ndarray
        lm coordinates for the endpoints of the purple line.
    plots : dict
        Versions of xyz, cc, lms, bm, lm at 0.1 nm for plotting. Includes also CIE1964 and CIE1931 data. 
    """
    plots = dict()
    lms, tmp = lms_energy_base(field_size, age)
    plots['lms'] = lms.copy()
    lms_standard, tmp = lms_energy(field_size, age, lms_signfig)
    v_lambda, weights = v_lambda_energy_from_lms(field_size, age,
                                                 xyz_signfig, mat_dp)
    # For normalisation of Boynton-MacLeod, see below:
    bm_s_max = np.max(lms[:,3] / v_lambda[:,1])

    # Resample
    l_spline = scipy.interpolate.InterpolatedUnivariateSpline(lms[:,0], lms[:,1])
    m_spline = scipy.interpolate.InterpolatedUnivariateSpline(lms[:,0], lms[:,2])
    s_spline = scipy.interpolate.InterpolatedUnivariateSpline(lms[:,0], lms[:,3])
    ls_spline = scipy.interpolate.InterpolatedUnivariateSpline(lms_standard[:,0],
                                                               lms_standard[:,1])
    ms_spline = scipy.interpolate.InterpolatedUnivariateSpline(lms_standard[:,0],
                                                               lms_standard[:,2])
    ss_spline = scipy.interpolate.InterpolatedUnivariateSpline(lms_standard[:,0],
                                                               lms_standard[:,3])
    v_spline = scipy.interpolate.InterpolatedUnivariateSpline(v_lambda[:,0],
                                                              v_lambda[:,1])
    lambdas = np.arange(390, 830 + resolution, resolution)

    lms = np.array([l_spline(lambdas),
                    m_spline(lambdas),
                    s_spline(lambdas)])
    lms_standard = np.array([ls_spline(lambdas),
                             ms_spline(lambdas),
                             ss_spline(lambdas)])

    s_values = s_spline(lambdas)
    v_values = v_spline(lambdas)

    # Compute XYZ and chromaticity diagram
    a21 = weights[0]
    a22 = weights[1]
    a33 = my_round(v_values.sum() / s_values.sum(), mat_dp)

    cc_ref = chromaticity_interpolated(field_size)

    lambda_ref_min = 500
    ok = False
    while not ok:
        a13 = scipy.optimize.fmin(square_sum, 0.39,
                                  (a21, a22, a33, l_spline, m_spline, s_spline,
                                   v_spline, lambdas, lambda_ref_min, cc_ref,
                                   False, xyz_signfig, mat_dp),
                                   xtol=10**(-(mat_dp + 2)), disp=False)
        err, trans_mat, lambda_ref_min, ok = \
            square_sum(a13, a21, a22, a33, l_spline, m_spline,
                       s_spline, v_spline, lambdas,
                       lambda_ref_min, cc_ref, True, xyz_signfig, mat_dp)
    xyz = np.dot(trans_mat, lms)
    xyz = significant_figures(xyz, xyz_signfig)
    cc = np.array([xyz[0,:] / (xyz[0,:] + xyz[1,:] + xyz[2,:]),
                   xyz[1,:] / (xyz[0,:] + xyz[1,:] + xyz[2,:]),
                   xyz[2,:] / (xyz[0,:] + xyz[1,:] + xyz[2,:])])
    cc = my_round(cc, cc_dp)
    cc_white = np.sum(xyz, 1)
    cc_white = cc_white / np.sum(cc_white)
    cc_white = my_round(cc_white, cc_dp)

    # Reshape
    lms = np.concatenate((lambdas.reshape((1,len(lambdas))), lms)).T
    lms_standard = np.concatenate((lambdas.reshape((1,len(lambdas))),
                                   lms_standard)).T
    xyz = np.concatenate((lambdas.reshape((1,len(lambdas))), xyz)).T
    cc = np.concatenate((lambdas.reshape((1,len(lambdas))), cc)).T
    Vl = np.concatenate((lambdas.reshape((1,len(lambdas))),
                         v_values.reshape((1,len(v_values))))).T

    # Versions for plotting and purple line
    plots['xyz'] = np.dot(trans_mat, plots['lms'][:,1:].T)
    plots['xyz'] = significant_figures(plots['xyz'], xyz_signfig)
    plots['cc'] = np.array([plots['xyz'][0,:] / (plots['xyz'][0,:] + plots['xyz'][1,:] + plots['xyz'][2,:]),
                   plots['xyz'][1,:] / (plots['xyz'][0,:] + plots['xyz'][1,:] + plots['xyz'][2,:]),
                   plots['xyz'][2,:] / (plots['xyz'][0,:] + plots['xyz'][1,:] + plots['xyz'][2,:])])
    plots['xyz'] = np.concatenate((np.array([plots['lms'][:,0]]).T, plots['xyz'].T), axis=1)
    plots['cc'] = np.concatenate((np.array([plots['lms'][:,0]]).T, plots['cc'].T), axis=1)
    
    # Boynton-MacLeod
    bm = lms.copy()
    bm[:,1] = trans_mat[1,0] * lms[:,1] / Vl[:,1]
    bm[:,2] = trans_mat[1,1] * lms[:,2] / Vl[:,1]
    bm[:,3] = lms[:,3] / Vl[:,1]
    bm[:,3] = bm[:,3] / bm_s_max
    bm[:,1:] = my_round(bm[:,1:], bm_dp)
    
    # Version for plotting and purple line
    plots['bm'] = plots['lms'].copy()
    plots['bm'][:,1] = trans_mat[1,0] * plots['lms'][:,1] / plots['xyz'][:,2]
    plots['bm'][:,2] = trans_mat[1,1] * plots['lms'][:,2] / plots['xyz'][:,2]
    plots['bm'][:,3] = plots['lms'][:,3] / plots['xyz'][:,2]
    plots['bm'][:,3] = plots['bm'][:,3] / bm_s_max
    
    L_E = trans_mat[1,0] * np.sum(lms[:,1])
    M_E = trans_mat[1,1] * np.sum(lms[:,2])
    S_E = np.sum(lms[:,3]) / bm_s_max
    
    bm_white = np.array([L_E / (L_E + M_E), M_E / (L_E + M_E), S_E / (L_E + M_E)])
    bm_white = my_round(bm_white, bm_dp)
    
    # lm diagram
    if lm_dp > 5:
        lms_N = lms.copy()
    else:   
        lms_N = lms_standard.copy()
    lms_N[:,1:] = lms_N[:,1:] / np.sum(lms_N[:,1:], 0)
    lm = lms_N.copy()
    lm[:,1] = lms_N[:,1] / (lms_N[:,1] + lms_N[:,2] + lms_N[:,3])
    lm[:,2] = lms_N[:,2] / (lms_N[:,1] + lms_N[:,2] + lms_N[:,3])
    lm[:,3] = lms_N[:,3] / (lms_N[:,1] + lms_N[:,2] + lms_N[:,3])
    lm[:,1:] = my_round(lm[:,1:], lm_dp)
    lm_white = np.sum(lms_N[:,1:], 0)
    lm_white = lm_white / np.sum(lm_white)
    lm_white = my_round(lm_white, lm_dp)
    
    # Version for plotting and purple line
    plots['lm'] = plots['lms'].copy()
    lms_N_fine = plots['lms'].copy()
    if lm_dp <= 5:
        lms_N_fine[:,1:] = significant_figures(lms_N_fine[:,1:], lms_signfig)
    lms_N_fine[:,1:] = lms_N_fine[:,1:] / np.sum(lms_N[:,1:], 0)
    plots['lm'][:,1] = lms_N_fine[:,1] / (lms_N_fine[:,1] + lms_N_fine[:,2] + lms_N_fine[:,3])
    plots['lm'][:,2] = lms_N_fine[:,2] / (lms_N_fine[:,1] + lms_N_fine[:,2] + lms_N_fine[:,3])
    plots['lm'][:,3] = lms_N_fine[:,3] / (lms_N_fine[:,1] + lms_N_fine[:,2] + lms_N_fine[:,3])
    
    # Compute purple line for cc
    delaunay = Delaunay(plots['cc'][:,1:3])
    ind = np.argmax(np.abs(delaunay.convex_hull[:,0] - delaunay.convex_hull[:,1]))
    purple_line_cc = np.zeros((2,3))
    purple_line_cc[0,0] = plots['cc'][delaunay.convex_hull[ind,0], 0]
    purple_line_cc[0,1] = plots['cc'][delaunay.convex_hull[ind,0], 1]
    purple_line_cc[0,2] = plots['cc'][delaunay.convex_hull[ind,0], 2]
    purple_line_cc[1,0] = plots['cc'][delaunay.convex_hull[ind,1], 0]
    purple_line_cc[1,1] = plots['cc'][delaunay.convex_hull[ind,1], 1]
    purple_line_cc[1,2] = plots['cc'][delaunay.convex_hull[ind,1], 2]
    plots['purple_line_cc'] = purple_line_cc.copy()
    purple_line_cc[:,1:] = my_round(purple_line_cc[:,1:], cc_dp)

    # Compute purple line for bm
    delaunay = Delaunay(plots['bm'][:,1:4:2])
    ind = np.argmax(np.abs(delaunay.convex_hull[:,0] - delaunay.convex_hull[:,1]))
    purple_line_bm = np.zeros((2,3))
    purple_line_bm[0,0] = plots['bm'][delaunay.convex_hull[ind,0], 0]
    purple_line_bm[0,1] = plots['bm'][delaunay.convex_hull[ind,0], 1]
    purple_line_bm[0,2] = plots['bm'][delaunay.convex_hull[ind,0], 3]
    purple_line_bm[1,0] = plots['bm'][delaunay.convex_hull[ind,1], 0]
    purple_line_bm[1,1] = plots['bm'][delaunay.convex_hull[ind,1], 1]
    purple_line_bm[1,2] = plots['bm'][delaunay.convex_hull[ind,1], 3]
    plots['purple_line_bm'] = purple_line_bm.copy()
    purple_line_bm[:,1:] = my_round(purple_line_bm[:,1:], bm_dp)

    # Hack to report correct wavelength also for the chromaticity diagram
    # (they give the same value anyway)
    # Could (should?) be removed at a later stage
    if ( purple_line_cc[1,0] != purple_line_bm[1,0] ):
        print "Wavelengths differ!"
        purple_line_cc[1,0] = purple_line_bm[1,0]
    
    # Compute purple line for lm
    delaunay = Delaunay(plots['lm'][:,1:3])
    ind = np.argmax(np.abs(delaunay.convex_hull[:,0] - delaunay.convex_hull[:,1]))
    purple_line_lm = np.zeros((2,3))
    purple_line_lm[0,0] = plots['lm'][delaunay.convex_hull[ind,0], 0]
    purple_line_lm[0,1] = plots['lm'][delaunay.convex_hull[ind,0], 1]
    purple_line_lm[0,2] = plots['lm'][delaunay.convex_hull[ind,0], 2]
    purple_line_lm[1,0] = plots['lm'][delaunay.convex_hull[ind,1], 0]
    purple_line_lm[1,1] = plots['lm'][delaunay.convex_hull[ind,1], 1]
    purple_line_lm[1,2] = plots['lm'][delaunay.convex_hull[ind,1], 2]
    plots['purple_line_lm'] = purple_line_lm.copy()
    purple_line_lm[:,1:] = my_round(purple_line_lm[:,1:], lm_dp)
    
    # Add CIE standards to plot data structure
    plots['xyz31'] = VisualData.xyz31.copy()
    plots['xyz64'] = VisualData.xyz64.copy()
    plots['cc31'] = my_round(VisualData.cc31, 5)
    plots['cc64'] = my_round(VisualData.cc64, 5)
    
    # Compute purple line for CIE standard cc
    delaunay = Delaunay(plots['cc31'][:,1:3])
    ind = np.argmax(np.abs(delaunay.convex_hull[:,0] - delaunay.convex_hull[:,1]))
    purple_line_cc31 = np.zeros((2,3))
    purple_line_cc31[0,0] = plots['cc31'][delaunay.convex_hull[ind,0], 0]
    purple_line_cc31[0,1] = plots['cc31'][delaunay.convex_hull[ind,0], 1]
    purple_line_cc31[0,2] = plots['cc31'][delaunay.convex_hull[ind,0], 2]
    purple_line_cc31[1,0] = plots['cc31'][delaunay.convex_hull[ind,1], 0]
    purple_line_cc31[1,1] = plots['cc31'][delaunay.convex_hull[ind,1], 1]
    purple_line_cc31[1,2] = plots['cc31'][delaunay.convex_hull[ind,1], 2]
    plots['purple_line_cc31'] = purple_line_cc31.copy()

    delaunay = Delaunay(plots['cc64'][:,1:3])
    ind = np.argmax(np.abs(delaunay.convex_hull[:,0] - delaunay.convex_hull[:,1]))
    purple_line_cc64 = np.zeros((2,3))
    purple_line_cc64[0,0] = plots['cc64'][delaunay.convex_hull[ind,0], 0]
    purple_line_cc64[0,1] = plots['cc64'][delaunay.convex_hull[ind,0], 1]
    purple_line_cc64[0,2] = plots['cc64'][delaunay.convex_hull[ind,0], 2]
    purple_line_cc64[1,0] = plots['cc64'][delaunay.convex_hull[ind,1], 0]
    purple_line_cc64[1,1] = plots['cc64'][delaunay.convex_hull[ind,1], 1]
    purple_line_cc64[1,2] = plots['cc64'][delaunay.convex_hull[ind,1], 2]
    plots['purple_line_cc64'] = purple_line_cc64.copy()

    return xyz, cc, cc_white, trans_mat, lms_standard, lms, \
        bm, bm_white, lm, lm_white, lambda_ref_min, \
        purple_line_cc, purple_line_bm, purple_line_lm, plots
        
#==============================================================================
# For testing purposes only
#==============================================================================

if __name__ == '__main__':
    xyz, cc, cc_white, trans_mat, lms_standard, lms_base, bm, bm_white, \
    lm, lm_white, lambda_ref_min, purple_line_cc, purple_line_bm, \
    purple_line_lm, plots = compute_tabulated(2, 32, 1)
    print "2 degrees, 32 years, 1nm:"
    print "\nPurple line xy:"
    print purple_line_cc
    print "\nPurple line bm:"
    print purple_line_bm
    print "\nPurple line lm:"
    print purple_line_lm
    xyz, cc, cc_white, trans_mat, lms_standard, lms_base, bm, bm_white, \
    lm, lm_white, lambda_ref_min, purple_line_cc, purple_line_bm, \
    purple_line_lm, plots = compute_tabulated(10, 32, 1)
    print "10 degrees, 32 years, 1nm:"
    print "\nPurple line xy:"
    print purple_line_cc
    print "\nPurple line bm:"
    print purple_line_bm
    print "\nPurple line lm:"
    print purple_line_lm
