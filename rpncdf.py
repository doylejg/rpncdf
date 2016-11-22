#!/usr/bin/env python

"""
Program designed to convert EC3 proprietary standard format to NetCDF
"""

import rpnpy.librmn.all as rmn

import copy
import os

import datetime,time


import numpy as np

from scipy.io import netcdf
from netCDF4 import Dataset

import re

class FileNotFound(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def new_netcdf(*var):
    #return netcdf.netcdf_file(*var)
    return Dataset(*var)

def read_odict(fname='o.dict',skip_footer=22):
    
    # From SO: http://stackoverflow.com/a/14693789/5543181 
    ansi_escape = re.compile(r'\x1b[^m]*m')
    
    out = np.genfromtxt(fname,dtype='str',
                        autostrip=True,
                        delimiter='\t',
                        skip_footer=skip_footer, # Removes VAR list footer
                        #comments='\x1b[31m', # Removes obsolete vars
                        invalid_raise=False, # This excludes data with 4 columns
                        # This removes the coloring command after an obsolete tag
                        #converters = {0: lambda s: s.replace('\x1b[0m','')}, )
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


def _get_var(funit,var):#,vlevel=-1,forecast_hour=-1):
    
    # k = rmn.fstinf(funit,
    #                ip1=vlevel,
    #                ip2=forecast_hour,
    #                nomvar=var )
    # try:
    #     return rmn.fstluk(k)['d']
    try:
        return rmn.fstlir(funit, nomvar=var)#, dtype=np.float32)

    except TypeError:
        print 'data for %s not found'%var
        return None


def get_data(fname,vlevel=-1,forecast_hour=-1,fname_prev=None,
             verbose=False,odict='o.dict',nf=None,checkvars=True):
    """extract all data from a rpn file"""
    
    funit = rmn.fstopenall(fname,rmn.FST_RO,verbose=verbose)
    if type(odict)==str:
        data = read_odict(fname=odict)
    elif type(odict)==dict:
        data = copy.deepcopy(odict)

    if checkvars:
        data = check_vars(odict,funit=funit)
        
    if nf == True:
        nf = fname
        
    if nf and type(nf)==str:

        ladate = datetime.datetime.strptime( \
                        os.path.basename(fname).split('_')[0],'m%Y%m%d%H')
        ladate += datetime.timedelta(seconds=int(fname.split('_')[-1])*60*60)
        
        nf = _create_netcdf(nf, ladate)

        # deal with lat/lon
        _create_dimension(nf,'lat',dim_size=_get_var(funit,'^^')['d'].shape[1])
        _create_dimension(nf,'lon',dim_size=_get_var(funit,'>>')['d'].shape[0])


    xkeys = ['!!','^^','>>']
    keys = data.keys()
    for k in xkeys:
        keys.pop(keys.index(k))
    keys.sort()
    #keys.extend(xkeys)

    ##################### hack
    #keys.pop(keys.index('!!'))


    for var in keys:
           
        rec = _get_var(funit,var)
        
        data[var]['data'] = rec['d']

        #get lat/lon
        if not ('lat' in data and 'lon' in data) and not var in xkeys:

            rec['iunit'] = funit
            gridid = rmn.ezqkdef(rec)
            gridLatLon = rmn.gdll(gridid)

            data['lat'] = {'data':gridLatLon['lat'],
                           'units':'degrees',
                           'long_name':'Latitude'}
            data['lon'] = {'data':gridLatLon['lon'],
                           'units':'degrees',
                           'long_name':'Longitude'}
            if nf:
                for dim in ['lat','lon']:
                    _addto_netcdf(nf,dim,data=data[dim]['data'],
                                  units=data[dim]['units'],
                                  long_name=data[dim]['long_name'])
            
            
        if nf:
            #try:
            _addto_netcdf(nf,var,data=data[var]['data'],
                          units=data[var]['units'],
                          long_name=data[var]['long_name'])
            #except IndexError:
            #    import pdb;pdb.set_trace()
            #    _addto_netcdf(nf,var,data=d[0,:],
            #                  units=data[var]['units'],
            #                  long_name=data[var]['long_name'])

                
        if var=='PR' and fname_prev:
            _funit = rmn.fstopenall(fname_prev,rmn.FST_RO,verbose=verbose)
            
            data['PR1h'] = {'data':data[var]['data'] - _get_var(_funit,var),
                            'long_name':'Hourly accumulated precipitation (from PR and previous hour)',
                            'units':data['PR']['units']}
        elif var=='RT':
            data['PR1h'] = {'data':data[var]['data']*3600, # Warning!!!! 1h only
                            'long_name':'Hourly accumulated precipitation (from RT)',
                            'units':data['PR']['units']}

        if 'PR1h' in data and nf:
            if not 'PR1h' in nf.variables.keys():
                _addto_netcdf(nf,'PR1h',
                              data=data['PR1h']['data'],
                              units=data['PR1h']['units'],
                              long_name=data['PR1h']['long_name'])

    if nf:
       # return nf
        nf.close()
        
    return data


def _create_netcdf(nfname,dt):
    
    # Create netcdf
    nf = new_netcdf(nfname+'.nc','w')
    nf.history = 'Created on %s by %s'%(datetime.datetime.now().isoformat(),
                                        os.environ['USER'])
    
    nf.datetime = '%s UTC'%dt

    nf.createDimension('time',1)
    nf.createVariable('datetime', 'i', ('time',))
    nf.variables['datetime'][:] = time.mktime(dt.timetuple())
    nf.variables['datetime'].units = 's'
    nf.variables['datetime'].long_name = 'Epoch Unix Time Stamp (s)'

    return nf

def _create_dimension(nf,dim_name,dim_size=None,data=None):

    nf.createDimension(dim_name,dim_size or data.shape[0])

def _create_variable(nf,var_name,dims):
    
    if type(dims)==str:
        dims = (dims,)
    elif not type(dims)==tuple:
        dims = tuple(dims)
    else:
        pass

    nf.createVariable(var_name, 'float', dims)


def _insert_data(nf,var_name,data,units='',long_name=''):

    nf.variables[var_name][:] = data
    nf.variables[var_name].units = units
    nf.variables[var_name].long_name = long_name



def _addto_netcdf(nf,var,data,units,long_name):

    dimensions = nf.dimensions.items()

    dims = []
    for data_len in data.shape:
        dims.extend([dim for dim,dim_len in dimensions if dim_len.size==data_len])

    # WARNING: This only works for 2D lon/lat, this needs to change
    _create_variable(nf,var,tuple(dims))

    _insert_data(nf,var,data,units,long_name)
    

if __name__=="__main__":

    d = get_data('test_data/m2015120600_042',nf=True)

