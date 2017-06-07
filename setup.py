from setuptools import setup

setup(name='rpncdf',
      version='0.1',
      description='Converts RPN standard files to NetCDF',
      classifiers=[
          'Development Status :: 4 - Beta',
          'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',

          'Programming Language :: Python :: 2.7+',
          'Intended Audience :: Science/Research',
          'Topic :: :: Linguistic',
      ],
      keywords='netcdf rpn gem wrf environmentcanada eccc',
      url='http://github.com/doylejg/rpncdf',
      author='Jonathan G. Doyle',
      author_email='jonathan.g.doyle@gmail.com',
      license='LGPLv3+',
      packages=['rpncdf'],
      install_requires=['numpy','netCDF4','rpnpy'],
      entry_points="""
      [console_scripts]
      rpncdf = rpncdf:main
      """,
      include_package_data=True,
      zip_safe=True)
