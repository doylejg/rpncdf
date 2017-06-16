#!/usr/bin/env python

"""
Program designed to convert EC3 proprietary standard format to NetCDF

Dependencies:
rpnpy
numpy
netCDF4-python
"""

import rpnpy.librmn.all as rmn

import copy
import os

import datetime, time

import pkg_resources
import argparse

import numpy as np

# Currently using netcdf4 package rather than scipy version
#from scipy.io.netcdf import netcdf_file 
from netCDF4 import Dataset 

import re

class FileNotFound(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def new_netcdf(*var):
    # Call the netcdf_file from netCDF4 implementation
    return Dataset(*var)

def read_odict(fname=None,skip_footer=22):

    if fname==None:
        fname = pkg_resources.resource_stream(__name__,'o.dict')
        
    # From SO: http://stackoverflow.com/a/14693789/5543181 
    ansi_escape = re.compile(r'\x1b[^m]*m')
    
    out = np.genfromtxt(fname,
                        dtype='str',
                        autostrip=True,
                        delimiter='\t',
                        skip_footer=skip_footer, # Removes VAR list footer
                        #comments='\x1b[31m', # Removes obsolete vars
                        invalid_raise=False, # This excludes data with 4 columns
                        # Removes the coloring command after an obsolete tag
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
    
    if type(odict)==str or odict==None:
        data = read_odict(fname=odict)
    elif type(odict)==dict:
        data = odict.copy()
        
    if fname:
        funit = rmn.fstopenall(fname,rmn.FST_RO)
    elif funit==None:
        raise Exception,'fname or funit must be provided'

    return {k:v for k,v in data.items() if rmn.fstinf(funit, nomvar=k)}


def _get_var(funit,var):
    try:
        return rmn.fstlir(funit, nomvar=var)

    except TypeError:
        print 'data for %s not found'%var
        return None


def get_data(fname,fname_prev=None,
             verbose=False,odict=None,
             nf=None,checkvars=True):
    """Extract all data from a rpn file

    Inputs: 
    fname - path to standard file
    fname_prev - path to previous data in time, used to calculate 
                 precipitation rate
    verbose - passes verbose flag to rpnpy [seems to not work]
    odict - path to o.dict source file (included in package)
    nf - path to desired NetCDF output
    checkvars - Forces a check to ensure all variables are in the standard
                file. If set to False and extra variables are provided in
                odict then conversion may crash.

    Returns:
    Dictionary containing data (numpy.array), units (str), long_name (str) 
    for each key provided in o.dict. If nf is provided, a NetCDF file will be
    created.
    
    """
    
    funit = rmn.fstopenall(fname,rmn.FST_RO,verbose=verbose)
   
    if checkvars:
        data = check_vars(odict,funit=funit)
    else:
         if type(odict)==str or odict==None:
             data = read_odict(fname=odict)
         elif type(odict)==dict:
             data = copy.deepcopy(odict)

    if nf == True:
        nf = fname
        
    if nf and type(nf)==str:
        fmts = ['m%Y%m%d%H','%Y%m%d%H']
        for fmt in fmts:
            try:
                ladate = datetime.datetime.strptime( \
                            os.path.basename(fname).split('_')[0],fmt)
                ladate += datetime.timedelta(
                    seconds=int(fname.split('_')[-1])*60*60)
                notime = False
                break
            
            except ValueError:
                ladate = None
                notime = True
                
        nf = _create_netcdf(nf, ladate)

        # deal with lat/lon
        _create_dimension(nf,'lon',dim_size=_get_var(funit,'^^')['d'].shape[1])
        _create_dimension(nf,'lat',dim_size=_get_var(funit,'>>')['d'].shape[0])


    xkeys = ['!!','^^','>>','LA','LO']
    keys = data.keys()

    # Remove non data keys from key list
    for k in xkeys:
        try:
            keys.pop(keys.index(k))
        except ValueError:
            pass
    keys.sort()
    

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
                                  long_name=data[dim]['long_name'],
                                  notime=True)
            
            
        if nf:
            _addto_netcdf(nf,var,data=data[var]['data'],
                          units=data[var]['units'],
                          long_name=data[var]['long_name'],
                          notime=notime)
                
        if var=='PR' and fname_prev:
            _funit = rmn.fstopenall(fname_prev,rmn.FST_RO,verbose=verbose)
            
            data['PR1h'] = {'data':data[var]['data']-_get_var(_funit,var)['d'],
                            'long_name':'Hourly accumulated precipitation '\
                            '(from PR and previous hour)',
                            'units':data['PR']['units']}
        elif var=='RT':
            data['PR1h'] = {'data':data[var]['data']*3600, # Warning!!!! 1h only
                            'long_name':'Hourly accumulated precipitation '\
                            '(from RT)',
                            'units':data['PR']['units']}

        if 'PR1h' in data and nf:
            if not 'PR1h' in nf.variables.keys():
                _addto_netcdf(nf,'PR1h',
                              data=data['PR1h']['data'],
                              units=data['PR1h']['units'],
                              long_name=data['PR1h']['long_name'],
                              notime=notime)

    if nf:
        nf.close()
        
    return data


def _create_netcdf(nfname,dt=None):
    
    # Create netcdf
    nf = new_netcdf(nfname,'w')
    nf.history = 'Created on %s by %s'%(datetime.datetime.now().isoformat(),
                                        os.environ['USER'])

    if dt:
        nf.datetime = '%s UTC'%dt

        nf.createDimension('time',None)
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



def _addto_netcdf(nf,var,data,units,long_name,notime=False):

    dimensions = nf.dimensions.items()

    if notime:
        dims = []
    else:
        dims = ['time',]
        
    for data_len in data.shape:
        dims.extend([dim for dim,dim_len in dimensions \
                     if dim_len.size==data_len])

    # WARNING: This only works for 2D lon/lat, this needs to change
    if len(dims)==3:
        input_data = np.atleast_3d(data.T).T
    else:
        input_data = data
        
    _create_variable(nf,var,tuple(dims))
    _insert_data(nf,var,input_data,units,long_name)
    
def main():
    
    parser = argparse.ArgumentParser(
        description='Convert standard file to NetCDF')

    parser.add_argument('infiles',nargs='+',
                        help='Path to input standard file(s).')
    parser.add_argument('-o','--outfiles',nargs='*',dest='outfiles',
                        help='Path to output netcdf file(s).'\
                             ' (optional, same as input)',
                        default=None)
    parser.add_argument('--odict',
                        help='Path to custom o.dict '\
                             '(22 line footer is ignored)',
                        default=None)
    parser.add_argument('--fprev',dest='fname_prev',nargs='*',
                        help='Path to previous standard file for calculation '\
                        'of rates',default=None)
    parser.add_argument('--rate',action='store_true',
                        default=False,
                        help='Calculate rate if multiple input files are '\
                             'provieded (Note: ignores fprev)')
    parser.add_argument('-v','--verbose',dest='verbose',default=False,
                        help='Verbose output (may not work, problem with RPNpy')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--checkvars',
                        help='Enables check vars in o.dict against file',
                        action='store_true',dest='checkvars',
                        default=True)
    group.add_argument('-d','--nocheckvars',
                        help='Disables checking vars in o.dict against file',
                        action='store_false',dest='checkvars')
    
    args = parser.parse_args()

    if args.outfiles is None:
        nfpaths = [infile+'.nc' for infile in  args.infiles]
    elif len(args.outfiles) != len(args.infiles):
        raise argparse.ArgumentError(
            parser._option_string_actions['--outfiles'],
            'argument length ({0:}) mismatch with infiles ({1:})'.format(
                len(args.outfiles),len(args.infiles)))
    else:
        nfpaths = args.outfiles

    if args.rate:
        fname_prevs = [None] + args.infiles[:-1]
    elif args.fname_prev is None:
        fname_prevs = [None] * len(args.infiles)
    elif len(args.fname_prev) != len(args.infiles)-1 \
         and not (len(args.fname_prev)==1 and len(args.infiles)==1):
        raise argparse.ArgumentError(
            parser._option_string_actions['--fprev'],
            'argument length ({0:}) mismatch with infiles len-1 ({1:})'.format(
                len(args.fname_prev),len(args.infiles)))
    else:
        fname_prevs = [None] + args.fname_prev


    [get_data(infile,
              nf=nfpath,
              fname_prev=fname_prev,
              verbose=args.verbose,
              odict=args.odict,
              checkvars=args.checkvars) \
     for infile, nfpath, fname_prev in \
     zip(args.infiles, nfpaths,fname_prevs) ]


    
if __name__=="__main__":

    main()
