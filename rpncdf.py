#!/usr/bin/env python

"""
Program designed to convert EC3 proprietary standard format to NetCDF
"""

import rpnpy.librmn.all as rmn
import copy

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


def check_vars(odict,fname=None,funit=None):
    """
    Checks standard file for inclusion of variables provided in odict.

    Input:
    odict (str,dict) - the odict as read by read_odict()
    fname (str) - path to standard file
    funit (rmn) - pointer to standard file

    Returns:
    simplified dictionary, similar to odict
    """
    
    if type(odict)==str:
        data = read_odict(fname=odict)
    elif type(odict)==dict:
        data = odict.copy()
        
    if fname:
        funit = rmn.fstopenall(fname,rmn.FST_RO)
    elif funit==None:
        raise Exception,'fname or funit must be provided'

    return {k:v for k,v in data.items() if rmn.fstinf(funit, nomvar=k)}


def _get_var(funit,var,vlevel=-1,forecast_hour=-1):
    
    k = rmn.fstinf(funit,
                   ip1=vlevel,
                   ip2=forecast_hour,
                   nomvar=var )
        
    return rmn.fstluk(k)['d']


def get_data(fname,vlevel=-1,forecast_hour=-1,fname_prev=None,
             verbose=False,odict='o.dict',nf=None):
    """extract all data from a rpn file"""
    
    funit = rmn.fstopenall(fname,rmn.FST_RO,verbose=verbose)
    if type(odict)==str:
        data = read_odict(fname=odict)
    elif type(odict)==dict:
        data = copy.deepcopy(odict)

    if nf and type(nf)==str:
        nf = _create_netcdf(nfname,
                           {'datetime':_get_var(funit,'datetime'),
                            'lon':_get_var(funit,'^^'),
                            'lat':_get_var(funit,'>>') })
        
    for var in data.keys():
           
        d = _get_var(funit,var)
        
        if nf:
            _addto_netcdf(nf,var,data=d,
                          units=data[var]['units'],
                          long_name=data[var]['long_name'])
        else:
            data[var]['data'] = d
        
        if var=='PR' and fname_prev:
            _funit = rmn.fstopenall(fname_prev,rmn.FST_RO,verbose=verbose)
            
            data['PR1h'] = {'data':data[var]['data'] - _get_var(_funit,var),
                            'long_name':'Hourly accumulated precipitation',
                            'units':data['PR']['units']}
        elif var=='RT':
            data['PR1h'] = {'data':data[var]['data']*3600, # Warning!!!! 1h only
                            'long_name':'Hourly accumulated precipitation',
                            'units':data['PR']['units']}

        if 'PR1h' in data and nf:
            _addto_netcdf(nf,var,
                          data=data['PR1h']['data'],
                          units=data['PR1h']['units'],
                          long_name=data['PR1h']['long_name'])
            
            
    return data


def _create_netcdf(nfname,data):
    
    # Create netcdf
    nf = netcdf.netcdf_file(filename+'.nc','w')
    nf.history = 'Created on %s by %s'%(datetime.datetime.now().isoformat(),
                                        os.environ['USER'])
    
    nf.datetime = '%s UTC'%data['datetime']


    nf.createDimension('time',1)
    nf.createVariable('datetime', 'int32', ('time',))
    nf.variables['datetime'][:] = time.mktime(data['datetime'].astype(\
                                            datetime.datetime).timetuple())
    nf.variables['datetime'].units = 's'
    nf.variables['datetime'].long_name = 'Epoch Unix Time Stamp (s)'
    
    nf.createDimension('lat',data['lat'].shape[0])
    nf.createDimension('lon',data['lon'].shape[0])
    
    nf.createVariable('lon', 'float', ('lon',))
    nf.variables['lon'][:] = data['lon']
    nf.variables['lon'].units = 'degrees'

    nf.createVariable('lat', 'float', ('lat',))
    nf.variables['lat'][:] = data['lat']
    nf.variables['lat'].units = 'degrees'

    return nf

def _addto_netcdf(nf,var,data,units,long_name):
    nf.createVariable(var, 'float', ('lon','lat'))
    nf.variables[var][:] = data[var]['data']
    nf.variables[var].units = data[var]['units']
    nf.variables[var].long_name = data[var]['long_name']


if __name__=="__main__":

    
    pass
