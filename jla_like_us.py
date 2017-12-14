#
#    routines to prepare and compute the likelihood for cosmological (Om0, and Ol0) 
#    and nuisance parameters for analyses of the JLA supernovae dataset 
#    http://supernovae.in2p3.fr/sdss_snls_jla/ReadMe.html
#
#    routines below are partly based on the likelihood routines provided by 
#    Nielsen et al. 2016, Nature Sci. Reports 6, 35596
#    http://adsabs.harvard.edu/abs/2016NatSR...635596N
#    available at:
#    https://zenodo.org/record/34487
#  
#    The Nielsen et al. likelihood is modified to allow for the evolution of the
#    mean color correction (eta_c) and stretch (eta_x)
#
import numpy as np
from scipy.linalg import cho_factor, cho_solve, block_diag
from scipy import interpolate as intp

def dL_init(zCMB, zhel, Om, Oml, bbox, int_tab_file_name):
    """
    This routine initializes interpolating splines using pre-computed table of 
    d_L (without c/H0 factor). The table has dimensions (Nsn,Ng,Ng), 
    where Nsn = the number of SNe in the sample, and Ng x Ng is a grid 
    of Om0, Oml0 for which distances were calculated for each z_SN
    
    dL_int_tab_740x60x60.npy example table with 60x60 grid for 740 SNe is provided
    in the repository, Other tables can be generated using 
    
    Ng is the size of the vectors Om, Oml that define the grid of Om0 and Oml0 values on 
    which the table was tabulated. 
    
    The table is read and is rescaled by (1+zhel)/(1+zCMB) (see Davis et al. 2011) and then used 
    to generate a list of Nsn interpolating splines which will be used to compute
    distances for each SN. 
    
    Parameters
    -----------------------
    zCMB: array of floats
          list of SN redshifts in the CMB frame from JLA table
    zhel: array of floats
          list of SN redshifts in the Sun's frame from JLA table
    Om, Oml: arrays of floats 
          vectors of Om and Oml used to generate the interpolation table that is read
          the size of the vectors squared Ng^2 should correspond to np.size(inttab[0])
    bbox: list of 4 floats
          bounding values for Om0 and Oml0 to be used in generating interpolating splines
    int_tab_file_name: str
          file name of the interpolating table 
          
    Returns    
    --------
    intsp: list
          a list of interpolating bivariate splines for for each z_SN interpolating in Om_m and Om_L
    """
    
    inttab = np.load(int_tab_file_name)
    intsp = []
    for iz, zs in enumerate(zCMB):
        inttab[iz] *= (1.0 + zhel[iz])/(1.0+zCMB[iz]) 
        dummy = intp.RectBivariateSpline(Om, Oml, inttab[iz], bbox=bbox, kx=3, ky=3, s=0.0)
        intsp.append(dummy)
        
    return intsp
    
        
def mu_model(zCMB, Om0, OL0, cH0, intsp):
    """
    distance modulus for SNe with redshits in zCMB predicted for a given Om0, OL0
    
    Parameters
    ----------
    zCMB: array of floats 
          list of SN redshifts in the CMB frame from JLA table
    Om0, OL0: floats
          mean matter and vacuum energy density in units of critical density at z=0
    cH0: float
          c/H0 in Mpc for adopted value of H0
    intsp: array of pointers to interpolating spline functions
         pointer to the array of spline interpolation functions for each z 
         generated by dL_init
         
    Returns
    -------
    mu_cosmo: list
        a list of distance moduli 
        
    """

    Ns = np.size(zCMB); mu_cosmo = np.zeros_like(zCMB)
    
    for iz in range(Ns):
        # compute distance modulus
        mu_cosmo[iz] = 25.0 + 5.0*np.log10(intsp[iz](Om0,OL0)*cH0) 
    
    return mu_cosmo


def priors(xmod, name):
    """
    define priors on the parameters of the SN posterior sampling 
    
    Parameters
    ----------
    xmod: float
          parameter value
    name: str
          parameter name
          
    Returns
    -------
    prior: float
         value of the prior, given the input parameters
         currently, unnormalized constant priors for all parameters
    """
    prior = 0.    
    if name=='M0' and ((xmod>-17.) or (xmod<-21.)):  
        prior = -1.e9
        return prior
    if name=='Om0' and ((xmod>1.2) or (xmod<0.0)):
        prior = -1.e9
        return prior
    if name=='OL0' and ((xmod>1.2) or (xmod<0.0)):
        prior = -1.e9
        return prior
    if name=='sM0' and ((xmod<=0.) or (xmod>1.)): 
        prior = -1.e9  
        return prior
    if name=='alfa' and ((xmod<= 0.) or (xmod>1.)): 
        prior = -1.e9
        return prior
    if name=='beta' and ((xmod<= 0.) or (xmod>5.)): 
        prior = -1.e9
        return prior
    if name=='x10' and ((xmod<=-5.) or (xmod>5.)): 
        prior = -1.e9
        return prior
    if name=='eta_x1' and ((xmod<-5.)  or (xmod>5.)): 
        prior = -1.e9
        return prior
    if name=='sx1' and ((xmod<= 0.)  or (xmod>2.)):
        prior = -1.e9
        return prior
    if name=='c0' and ((xmod<=-1.)  or (xmod>1.)): 
        prior = -1.e9
        return prior
    if name=='eta_c' and ((xmod<-1.)  or (xmod>1.)): 
        prior = -1.e9
        return prior
    if name=='sc' and ((xmod<=0.)  or (xmod>1.)): 
        prior = -1.e9
    return prior
               
def sn_like_walk(xw, dobs, covobs, zCMB, cH0, intsp, 
                 mst, emst, dset, anames, **kwargs):
    """
    compute SN likelihood for a set of walkers given the walker parameters
    passed on in xw
    
    Parameters
    ----------
    xw: vector of floats
        active parameters sampled by the MCMC sampler
    
    the following parameters are to be passed in the args vector: 
    
    dobs: vector of floats
        vector of size 3*Nsn containing m_B, x1, and c values for each SN
    covobs: 2d array of floats
        observational covariance matrix of the JLA dataset of size 3Nsn x 3Nsn
    zCMB: array of floats 
          list of SN redshifts in the CMB frame from JLA table
    cH0: float
          c/H0 in Mpc for adopted value of H0
    intsp: array of pointers to interpolating spline functions
         pointer to the array of spline interpolation functions for each z 
         generated by dL_init
    mst, emst: floats
         log10(stellar mass of SN host galaxy in Msun) and its error 
    dset: float
          code of the data set from which SN originated; not used yet, 
          but may be used later
    anames: vector of str
         names of the sampled parameters; these names are selected among 
         the overall 13 parameters on which the likelihood depends
         names = ['M0', 'sM0', 'delM', 'alfa', 'beta', 'x10', 'eta_x1', 'sx1',
                  'c0', 'eta_c', 'sc', 'Om0', 'OL0']
                  M0   = central value of the intrinsic abs. magnitude of SNIa
                  sM0  = Gaussian rms of M0
                  delM = shift of M0 zeropoints for massive host galaxies (see eq. 5 in Betoule et al. 2014)
                  alfa = x1 stretch
                  beta = color stretch
                  x10  = central value of x1
                  eta_x1 = parameter describing linear z-dependence of x1: x1 = x10 + eta_x1*z
                  sx1  = Gaussian rms of x1
                  c0   = central value of c
                  eta_c = parameter describing linear z-dependence of c: c = c0 + eta_c*z
                  sc   = Gaussian rms of c
                  Om0  = mean matter density in units of rho_crit at z=0
                  OL0  = mean vacuum energy density in units ot rho_crit at z=0
                  
         the names passed in anames are names of the parameters that are actually
         sampled, the other parameters from the above list not in anames are kept fixed
         at the specified values
         
    kwargs: dictionary of keyword arguments that contains values of all parameters,
         both sampled and kept fixed
         
    Returns
    -------
    float
      ln(posterior)

    """
    Ns = np.size(zCMB); Nobs = np.size(dobs)
    dmod, diag, dobsd, Y0 = np.zeros((Nobs)), np.zeros((Nobs)), np.zeros((Nobs)),  np.zeros((Nobs)) 
    M0z = np.zeros((Ns))
    dobsd[:] = dobs[:]
    prefact0 =  -0.5*np.log(2*np.pi) * Nobs
    prior = 0.0
    #print("in like", xw, anames)
    for ip, name in enumerate(anames):
        kwargs[name] = xw[ip]
        prior += priors(xw[ip], name)
         
    if prior <= -1.e8:
        return -1.e9
    else:
        M0, sM0    = kwargs['M0'], kwargs['sM0']
        alfa, beta = kwargs['alfa'], kwargs['beta']
        x10, eta_x1, sx1 = kwargs['x10'], kwargs['eta_x1'], kwargs['sx1']
        c0, eta_c, sc    = kwargs['c0'], kwargs['eta_c'], kwargs['sc']
        delM = kwargs['delM']
        Om0 = kwargs['Om0']; OL0 = kwargs['OL0']
        
        # compute distance modulus for the current cosmology
        mu   = mu_model(zCMB, Om0, OL0, cH0, intsp)
 
        # set up covariance matrix using current parameter values
        vM0 = sM0*sM0; vx1 = sx1*sx1; vc = sc*sc
        block3 = np.array( [[vM0 + vx1*alfa**2 + vc*beta**2, -vx1*alfa, vc*beta], 
                            [-vx1*alfa , vx1, 0.], 
                            [vc*beta , 0., vc]] )
        ATCOVlA = block_diag( *[ block3 for i in range(Ns) ] );
        covlike = covobs + ATCOVlA
        
        # Cholesky decomposition for faster cov matrix inversion
        chol_fac = cho_factor(covlike, overwrite_a = True, lower = True ) 
        dobsd[::3] = dobs[::3] - mu
        x10z = x10 + eta_x1*zCMB; c0z = c0 + eta_c*zCMB
        ims = (mst > 10.0)
        M0z[~ims] = M0; M0z[ims] = M0 + delM # apply delta M correction a la eq. 5 in Betoule et al. 2014
        Y0[::3] = M0z - alfa*x10z + beta*c0z; Y0[1::3] = x10z; Y0[2::3] = c0z
        dm = dobsd - Y0
        prefact =  prefact0 - np.sum( np.log( np.diag( chol_fac[0] ) ) )
        like = prefact - 0.5 * np.dot(dm, cho_solve(chol_fac,dm)) + prior 

    return like

def read_jla_data(sn_list_name = None, cov_mat_dir = None, covhost=False, cohlens=False):
    """
    read in JLA table
    
    Parameters
    ----------
    sn_list_name: str
        file name containing the table
    cov_mat_dir: str
        path to directory containing covariance matrices
    covhost: bool
        set this to True, if delM is actively sampled parameter
        otherwise, set this to False and delM to 0 
    cohlens: bool
        specifies whether to include coh and lens covariance
        these should not be included when scatter in M is modelled in the model
        this parameter was passed only during testing stages
        
    Returns
    -------
    dobs, covobs, zCMB, zhel, mst, emst, dset, biascor
      vectos and covariance matrices containing JLA SNe data constructed from the JLA sample
    """
    zCMB, zhel, mB, x1, c, mst, emst, dset, biascor = np.loadtxt(sn_list_name, usecols=(1, 2, 4, 6, 8, 10, 11, 17, 20),  unpack=True)
 
    Ns = np.size(zCMB)
    Nobs = 3*Ns
    dobs = np.zeros((Nobs))
    covobs = np.zeros((Nobs,Nobs))
    
    dobs[::3] = mB; dobs[1::3] = x1; dobs[2::3] = c

    import pyfits
    # see Betoule et al. (2014), Eq. 11-13 for reference
    # to see the definitions of these covariances
    # also see http://supernovae.in2p3.fr/sdss_snls_jla/ReadMe.html
    covobs = pyfits.getdata(cov_mat_dir+'/C_stat.fits')
    if covhost:
        covmatlist = ['pecvel', 'nonia', 'model', 'dust', 'cal', 'host', 'bias']
    else:
        covmatlist = ['pecvel', 'nonia', 'model', 'dust', 'cal', 'bias']
        
    for mat in covmatlist:
        covobs += pyfits.getdata(cov_mat_dir+'/C_'+mat+'.fits') 

    #if cohlens: 
    #    # Add diagonal term from Eq. 13
    #    sigma = np.loadtxt(cov_mat_dir+'/sigma_mu.txt')
    #    sigma_pecvel = (5. * 150 / 3e5) / (np.log(10.) * sigma[:, 2])
    #    covobs[::3,::3] += sigma[:, 0]**2 + sigma[:, 1]**2 + sigma_pecvel**2

    return dobs, covobs, zCMB, zhel, mst, emst, dset, biascor
    
import sys
    
if __name__ == '__main__':
    import numpy as np
    import usample.usample
    import emcee 
    from time import clock

    if len(sys.argv) > 1:
        #print("will assume that SN data is in the directory %s"%sys.argv[1])
        data_dir = sys.argv[1]
    else:
        print("path to data directory is not provided")
        print("usage: python jla_like_test.py data_dir")
        exit(1)
   
    # prepare parameter values
    # set to best fit values of Nielsen et al. 2016
    Om0 = 0.341; OL0 = 0.569; H0 = 70.0
    
    # total number of all parameters
    Npar = 13
    xmod = np.zeros((1,Npar))
    
    # parameter values (initial or at which they will be fixed)
    alfa = 0.134; beta = 3.059; M0 = -19.052; sM0 = 0.108
    x10 = 0.038; eta_x1 = 0.; sx1 = 0.932; c0 = -0.016; eta_c = 0.0; sc=0.071
    delM = 0.0
    
    # fill in parameter vector
    xmod = np.array([M0, sM0, delM, alfa, beta, x10, eta_x1, sx1, c0, eta_c, sc, Om0, OL0])
    names = ['M0', 'sM0', 'delM', 'alfa', 'beta', 'x10', 'eta_x1', 'sx1', 'c0', 
             'eta_c', 'sc', 'Om0', 'OL0']

    # initial rms to use for each variable (if it's "active") to distribute them in a multivariate Gaussian
    scatter = np.array([0.05, 0.02, 0.02, 0.02, 0.05, 0.05, 0.05, 0.05*sx1, 
                        0.01, 0.02, 0.1*sc, 0.05, 0.05])

    # define which parameters to sample (1) and which to keep fixed (0)
    ipar_active = np.array([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1])

    # construct dictionary of parameters 
    kwargs = dict(list(zip(names, xmod)))

    # extract the active parameter vector
    ia = (ipar_active==1)
    ndim = np.size(ipar_active[ia])
    x0 = np.zeros((ndim)); step = np.zeros((ndim))
    x0[:] = xmod[ia]; step[:] = scatter[ia]

    # names of active parameters
    anames = np.array(names)[ia];
    
    # read JLA SNe list and covariance matrices; returned covobs is a combined cov. matrix
    sn_list_file = data_dir+'jla_lcparams.txt'
    cov_mat_dir = data_dir+'covmat'
    # set covhost to True (i.e. include host covariance) if M offset delM is an active parameter
    if 'delM' in anames:
        covhost = True
    else:
        covhost = False
        
    dobs, covobs, zCMB, zhel, mst, emst, dset, biascor = read_jla_data(sn_list_file, cov_mat_dir, covhost=covhost, cohlens=False)
 
    # auxiliary data to pass onto likelihood function
    cH0 = 2.99792e5/H0 
    Om = np.arange(0., 1.2, 0.02)
    Oml = np.arange(0., 1.2, 0.02)
    bbox = [0.,1.2, 0., 1.2]
    int_tab_file_name = data_dir+'dL_int_tab_740x60x60.npy'

    print("initializing the interpolation tables. This will take a few seconds...")
    
    intsp = dL_init(zCMB, zhel, Om, Oml, bbox, int_tab_file_name)
        
    args = [dobs, covobs, zCMB, cH0, intsp, mst, emst, dset, anames]
 
    print("will sample %d active parameters of the total %d parameters"%(ndim, np.size(xmod)))
    print("active indices:", np.arange(np.size(xmod))[ia])
    print("initial values:", x0)
    print("initial scatter:", step)
    print(anames)
    
    nwalkers = 10

    pp = np.vstack([x0 + np.random.normal(scale=step, size=len(x0))
            for i in range(nwalkers)])
    
    us = usample.UmbrellaSampler( sn_like_walk , lpfargs=args, lpfkwargs=kwargs, mpi=True, debug=True,  burn_acor=20 )

    if (us.is_master() ):
        t0 = clock()
    
    #
    # Now add some umbrellas.
    # First, define some temperatures to run with. 
    #

    temps = np.linspace( 1 , 10 , 5. ) 

    #
    # Then add an umbrella at each temperature. Use numwalkers walkers, and give some initial conditions
    # Can be added individually, or in bulk:
    #

    us.add_umbrellas( temperatures=temps , numwalkers=nwalkers , ic=x0 , sampler=emcee.EnsembleSampler )


    #
    # Then run for 1000 steps in each window.
    # Output stats every [freq] steps
    # Try to replica exchange [repex]-many walkers every [freq] steps
    #

    pos, weights, prob = us.run(500 , freq=10, repex=10)

    #
    # save the output
    #

    if (us.is_master() ):

        print("sampled in ", clock()-t0, " seconds")

        np.save('pos_zevo_all_nielsen_test_us.npy', pos)
        np.save('weights_zevo_all_nielsen_test_us.npy', weights)
        np.save('prob_zevo_all_nielsen_test_us.npy', prob)

    us.close_pools()
