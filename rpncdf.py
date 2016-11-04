#!/usr/bin/env python

"""
Program designed to convert EC3 proprietary standard format to NetCDF
"""

import rpnpy.librmn.all as rmn

import numpy as np

from scipy.io import netcdf

import re

class FileNotFound(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def read_odict(fname='o.dict',skip_footer=22):
    
    # From SO: http://stackoverflow.com/a/14693789/5543181 
    ansi_escape = re.compile(r'\x1b[^m]*m')
    
    out = np.genfromtxt(fname,dtype='string',
                        autostrip=True,
                        delimiter='\t',
                        skip_footer=skip_footer, # Removes VAR list footer
                        #comments='\x1b[31m', # Removes obsolete vars
                        invalid_raise=False, # This excludes data with 4 columns
                        # This removes the coloring command after an obsolete tag
                        #converters = {0: lambda s: s.replace('\x1b[0m','')},
                        converters = {0: lambda s: ansi_escape.sub('',s)}, )
    
    return {o[0]:{'long_name':o[1], 'units':o[2]} for o in out}

    
def get_data(fname,vlevel=-1,forecast_hour=-1,fname_prev=None,verbose=False):
    """extract all data from a rpn file"""
    funit = rmn.fstopenall(fname,rmn.FST_RO,verbose=verbose)
    data = var_list.copy()
    for var in var_list:
        k = rmn.fstinf(funit,
                       ip1=vlevel,
                       ip2=forecast_hour,
                       nomvar=var,
                       verbose=verbose,
                       )
        try:
            data[var]['data'] = rmn.fstluk(k)['d']
            if var=='PR' and fname_prev:
                funit = rmn.fstopenall(fname_last,rmn.FST_RO,verbose=verbose)
                k = rmn.fstinf(funit,
                               ip1=vlevel,
                               ip2=forecast_hour,
                               nomvar=var,
                       verbose=verbose,
                               )
                data['PR1h'] = {'data':data[var]['data'] - rmn.fstluk(k)['d'],
                                'desc':data['PR']['desc'],
                                'units':data['PR']['units']}
        except TypeError:
            print('variable %s failed to extract'%var)

    return data

