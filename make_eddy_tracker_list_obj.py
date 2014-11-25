# -*- coding: utf-8 -*-
# %run make_eddy_tracker_list_obj.py

"""
===========================================================================
This file is part of py-eddy-tracker.

    py-eddy-tracker is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    py-eddy-tracker is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with py-eddy-tracker.  If not, see <http://www.gnu.org/licenses/>.

Copyright (c) 2014 by Evan Mason
Email: emason@imedea.uib-csic.es
===========================================================================


make_eddy_tracker_list_obj.py

Version 1.4.2


===========================================================================


"""

import haversine_distmat as hav # needs compiling with f2py
#from make_eddy_track import *
from py_eddy_tracker_classes import *


def haversine_distance_vector(lon1, lat1, lon2, lat2):
    '''
    Haversine formula to calculate distance between two points
    Uses mean earth radius in metres (from scalars.h) = 6371315.0
    '''
    lon1 = np.asfortranarray(lon1.copy())
    lat1 = np.asfortranarray(lat1.copy())
    lon2 = np.asfortranarray(lon2.copy())
    lat2 = np.asfortranarray(lat2.copy())
    dist = np.asfortranarray(np.empty_like(lon1))
    hav.haversine_distvec(lon1, lat1, lon2, lat2, dist)
    return dist


def newPosition(lonin, latin, angle, distance):
    '''
    Given the inputs (base lon, base lat, angle, distance) return
     the lon, lat of the new position...
    '''
    lonin = np.asfortranarray(np.copy(lonin))
    latin = np.asfortranarray(np.copy(latin))
    angle = np.asfortranarray(np.copy(angle))
    distance = np.asfortranarray(np.copy(distance))
    lon = np.asfortranarray(np.empty_like(lonin))
    lat = np.asfortranarray(np.empty_like(lonin))
    hav.waypoint_vec(lonin, latin, angle, distance, lon, lat)
    return lon, lat


def nearest(lon_pt, lat_pt, lon2d, lat2d):
    """
    Return the nearest i, j point to a given lon, lat point
    in a lat/lon grid
    """
    lon2d, lat2d = lon2d.copy(), lat2d.copy()
    lon2d -= lon_pt
    lat2d -= lat_pt
    d = np.hypot(lon2d, lat2d)
    j, i = np.unravel_index(d.argmin(), d.shape)
    return i, j
    

def uniform_resample(x, y, num_fac=4, kind='linear'):
    '''
    Resample contours to have (nearly) equal spacing
    '''
    #plt.figure(706)
    #plt.plot(x, y, '.-g', lw=2)
    ##x = ndimage.zoom(x.copy(), 2)
    ##y = ndimage.zoom(y.copy(), 2)
    #plt.plot(x, y, '.-r', lw=2)
    # Get distances
    d = np.r_[0, np.cumsum(haversine_distance_vector(x[:-1],y[:-1], x[1:],y[1:]))]
    # Get uniform distances
    d_uniform = np.linspace(0, d.max(), num=d.size * num_fac, endpoint=True)
    # Do 1d interpolations
    xfunc = interpolate.interp1d(d, x, kind=kind)
    yfunc = interpolate.interp1d(d, y, kind=kind)
    xnew = xfunc(d_uniform)
    ynew = yfunc(d_uniform)
    #plt.plot(xnew, ynew, '.-r', lw=2)
    #plt.axis('image')
    #plt.show()
    return xnew, ynew
    

def strcompare(str1, str2):
    return str1 in str2 and str2 in str1

 

class track (object):
    '''
    Class that holds eddy tracks and related info
        index  - index to each 'track', or track_number
        lon    - longitude
        lat    - latitude
        ocean_time - roms time in seconds
        Uavg   - average velocity within eddy contour
        radius_s - eddy radius (as Chelton etal 2011)
        radius_e - eddy radius (as Chelton etal 2011)
        amplitude - max(abs(vorticity/f)) within eddy (as Kurian etal 2011)
        temp
        salt
        bounds - array(imin,imax,jmin,jmax) defining location of eddy
                 qparam contour
        alive - True if eddy active, set to False when eddy becomes active
        saved2nc - Becomes True once saved to netcdf file
        dayzero - True at first appearance of eddy
    '''
    def __init__(self, eddy_index, datatype, lon, lat, time, Uavg, teke,
                       radius_s, radius_e, amplitude, bounds, temp=None, salt=None, 
                       save_extras=False, contour_e=None, contour_s=None,
                       Uavg_profile=None, shape_error=None):

        self.eddy_index = eddy_index
        self.datatype   = datatype
        self.lon        = np.atleast_1d(lon)
        self.lat        = np.atleast_1d(lat)
        self.ocean_time = np.atleast_1d(time)
        self.Uavg       = np.atleast_1d(Uavg)
        self.teke       = np.atleast_1d(teke)
        self.radius_s   = np.atleast_1d(radius_s) # speed-based eddy radius
        self.radius_e   = np.atleast_1d(radius_e) # effective eddy radius
        self.amplitude  = np.atleast_1d(amplitude)
        if 'ROMS' in self.datatype:
            self.temp   = np.atleast_1d(temp)
            self.salt   = np.atleast_1d(salt)
        self.bounds     = np.atleast_2d(bounds)
        self.alive      = True
        self.dayzero    = True
        self.saved2nc   = False
        self.save_extras = save_extras
        if self.save_extras:
            self.contour_e = [contour_e]
            self.contour_s = [contour_s]
            self.Uavg_profile = [Uavg_profile]
            self.shape_error = np.atleast_1d(shape_error)
        
    
    
    def append_pos(self, lon, lat, time, Uavg, teke, radius_s, radius_e,
                   amplitude, bounds, temp=None, salt=None, contour_e=None, contour_s=None,
                   Uavg_profile=None, shape_error=None):
        '''
        Append track updates
        '''
        self.lon = np.r_[self.lon, lon]
        self.lat = np.r_[self.lat, lat]
        self.ocean_time = np.r_[self.ocean_time, time]
        self.Uavg = np.r_[self.Uavg, Uavg]
        self.teke = np.r_[self.teke, teke]
        self.radius_s = np.r_[self.radius_s, radius_s]
        self.radius_e = np.r_[self.radius_e, radius_e]
        #print 'self.amplitude_e222', self.amplitude, amplitude
        self.amplitude = np.r_[self.amplitude, amplitude]
        if 'ROMS' in self.datatype:
            self.temp = np.r_[self.temp, temp]
            self.salt = np.r_[self.salt, salt]
        try:
            self.bounds = np.hstack((self.bounds, bounds))
        except Exception:
            self.bounds = np.vstack((self.bounds, bounds))
        if self.save_extras:
            self.contour_e.append(contour_e)
            self.contour_s.append(contour_s)
            self.Uavg_profile.append(Uavg_profile)
            self.shape_error = np.r_[self.shape_error, shape_error]
        return self



    def _is_alive(self, rtime):
        '''
        Query if eddy is still active
          rtime is current 'ocean_time'
        If not active, kill it
        '''
        # The eddy...
        if self.alive is False: # is already dead
            return self.alive
        elif self.dayzero: # has just been initiated
            self.dayzero = False
            return self.alive
        elif self.ocean_time[-1] == rtime: # is still alive
            return self.alive
        else:
            self.alive = False # is now dead
            return self.alive
        
        

class track_list (object):
    '''
    Class that holds list of eddy tracks:
        tracklist - the list of 'track' objects
        qparameter: Q parameter range used for contours
        new_lon, new_lat: new lon/lat centroids
        old_lon, old_lat: old lon/lat centroids
        eddy_index:   index of eddy in track_list
    '''
    def __init__(self, datatype, track_duration_min, track_extra_variables):
        '''
        Initialise the list 'tracklist'
        '''
        self.tracklist = []
        self.datatype = datatype
        self.track_duration_min = track_duration_min
        self.track_extra_variables = track_extra_variables
        self.new_lon    = np.array([])
        self.new_lat    = np.array([])
        self.new_radii_s = np.array([])
        self.new_radii_e = np.array([])
        self.new_amp    = np.array([])
        self.new_Uavg   = np.array([])
        self.new_teke   = np.array([])
        if 'ROMS' in self.datatype:
            self.new_temp = np.array([])
            self.new_salt = np.array([])
        self.new_time   = np.array([])
        self.new_bounds = np.atleast_2d(np.empty(4, dtype=np.int16))
        self.old_lon    = np.array([])
        self.old_lat    = np.array([])
        self.old_radii_s  = np.array([])
        self.old_radii_e  = np.array([])
        self.old_amp    = np.array([])
        self.old_Uavg   = np.array([])
        self.old_teke   = np.array([])
        if 'ROMS' in self.datatype:
            self.old_temp = np.array([])
            self.old_salt = np.array([])
        self.old_time   = np.array([])
        self.old_bounds = np.atleast_2d([])
        if self.track_extra_variables:
            self.new_contour_e = []
            self.new_contour_s = []
            self.new_Uavg_profile = []
            self.new_shape_error = np.atleast_1d([])
            self.old_contour_e = []
            self.old_contour_s = []
            self.old_Uavg_profile = []
            self.old_shape_error = np.atleast_1d([])
        self.new_list   = True # flag indicating new list
        self.index = 0 # counter
        self.ncind = 0 # index to write to nc files, will increase and increase...
        self.ch_index = 0 # index for Chelton style nc files
        
        # Check for a correct configuration
        assert datatype in ('ROMS', 'AVISO'), "Unknown string in 'datatype' parameter"


    def append_list(self, lon, lat, time, Uavg, teke,
            radius_s, radius_e, amplitude, bounds, temp=None, salt=None,
            contour_e=None, contour_s=None, Uavg_profile=None, shape_error=None):
        '''
        Append a new 'track' object to the list
        '''
        #print 'AAAAAAAAA', time
        self.tracklist.append(track(self.index, self.datatype,
                                    lon, lat, time, Uavg, teke,
                                    radius_s, radius_e, amplitude, bounds,
                                    temp, salt, self.track_extra_variables,
                                    contour_e, contour_s, Uavg_profile, shape_error))


    def update_track(self, index, lon, lat, time, Uavg, teke,
             radius_s, radius_e, amplitude, bounds, temp=None, salt=None,
             contour_e=None, contour_s=None, Uavg_profile=None, shape_error=None):
        '''
        Update a track at index
        '''
        self.tracklist[index].append_pos(lon, lat, time, Uavg, teke,
                                         radius_s, radius_e,
                                         amplitude, bounds,
                                         temp=temp, salt=salt,
                                         contour_e=contour_e, contour_s=contour_s,
                                         Uavg_profile=Uavg_profile, shape_error=shape_error)


    def reset_holding_variables(self):
        '''
        Reset temporary holding variables to empty arrays
        '''
        self.new_lon_tmp = np.array([])
        self.new_lat_tmp = np.array([])
        self.new_radii_tmp_s = np.array([])
        self.new_radii_tmp_e = np.array([])
        self.new_amp_tmp = np.array([])
        self.new_Uavg_tmp = np.array([])
        self.new_teke_tmp = np.array([])
        self.new_time_tmp = np.array([])
        self.new_temp_tmp = np.array([])
        self.new_salt_tmp = np.array([])
        self.new_bounds_tmp = np.atleast_2d(np.empty(4, dtype=np.int16))
        if self.track_extra_variables:
            self.new_contour_e_tmp = []
            self.new_contour_s_tmp = []
            self.new_Uavg_profile_tmp = []
            self.new_shape_error_tmp = np.atleast_1d([])
        return


    def set_old_variables(self):
        '''
        Pass all values at time k+1 to k
        '''
        self.old_lon = np.copy(self.new_lon_tmp)
        self.old_lat = np.copy(self.new_lat_tmp)
        self.old_radii_s = np.copy(self.new_radii_tmp_s)
        self.old_radii_e = np.copy(self.new_radii_tmp_e)
        self.old_amp = np.copy(self.new_amp_tmp)
        self.old_Uavg = np.copy(self.new_Uavg_tmp)
        self.old_teke = np.copy(self.new_teke_tmp)
        self.old_temp = np.copy(self.new_temp_tmp)
        self.old_salt = np.copy(self.new_salt_tmp)
        if self.track_extra_variables:
            self.old_contour_e = list(self.new_contour_e_tmp)
            self.old_contour_s = list(self.new_contour_s_tmp)
            self.old_Uavg_profile = list(self.new_Uavg_profile_tmp)
            self.old_shape_error = np.atleast_1d([])


    def get_active_tracks(self, rtime):
        '''
        Return list of indices to active tracks.
        A track is defined as active if the last record
        corresponds to current rtime (ocean_time).
        This call also identifies and removes
        inactive tracks.
        '''
        active_tracks = []
        for i, item in enumerate(self.tracklist):
            if item._is_alive(rtime):
                active_tracks.append(i)
        return active_tracks


    def get_inactive_tracks(self, rtime):
        '''
        Return list of indices to inactive tracks.
        This call also identifies and removes
        inactive tracks
        '''
        inactive_tracks = []
        for i, item in enumerate(self.tracklist):
            if not item._is_alive(rtime):
                inactive_tracks.append(i)
        return inactive_tracks


        

    def create_netcdf(self, directory, savedir, title,
                                    grd=None,
                                    Ymin=None,
                                    Ymax=None,
                                    Mmin=None,
                                    Mmax=None,
                                    model=None,
                                    sigma_lev=None,
                                    rho_ntr=None):
        '''
        Create netcdf file same style as Chelton etal (2011)
        '''
        #print 'yooooooooooooo'
        if not self.track_extra_variables:
            self.savedir = savedir
        else:
           self.savedir = savedir.replace('.nc', '_ARGO_enabled.nc')
        nc = netcdf.Dataset(self.savedir, 'w', format='NETCDF4')
        nc.title = title + ' eddy tracks'
        nc.directory = directory
        nc.days_between_records = np.float64(self.days_btwn_recs)
        nc.track_duration_min = np.float64(self.track_duration_min)
        
        if 'Q' in self.diag_type:
            nc.Q_parameter_contours = self.qparameter
        elif 'sla' in self.diag_type:
            nc.sla_parameter_contours = self.slaparameter
            nc.shape_error = self.shape_err
            nc.pixmin = self.pixel_threshold[0]
            nc.pixmax = self.pixel_threshold[1]
        
        if self.smoothing in locals():
            nc.smoothing = np.str(self.smoothing)
            nc.smoothing_fac = np.float(self.smooth_fac)
        else:
            nc.smoothing = 'None'
        
        nc.i0 = np.int32(self.i0)
        nc.i1 = np.int32(self.i1)
        nc.j0 = np.int32(self.j0)
        nc.j1 = np.int32(self.j1)
        
        if 'ROMS' in self.datatype:
            nc.ROMS_grid = grd.grdfile
            nc.model = model
            nc.Ymin = np.int32(Ymin)
            nc.Ymax = np.int32(Ymax)
            nc.Mmin = np.int32(Mmin)
            nc.Mmax = np.int32(Mmax)
            nc.sigma_lev_index = np.int32(sigma_lev)
            
            if 'ip_roms' in model:
                nc.rho_ntr = rho_ntr
        
        nc.evolve_amp_min = self.evolve_ammin
        nc.evolve_amp_max = self.evolve_ammax
        nc.evolve_area_min = self.evolve_armin
        nc.evolve_area_max = self.evolve_armax
        
        # Create dimensions     
        nc.createDimension('Nobs', None)#len(Eddy.tracklist))
        #nc.createDimension('time', None) #len(maxlen(ocean_time)))
        nc.createDimension('four', 4)
            
            
            
        # Create variables     
        nc.createVariable('track', np.int32, ('Nobs'), fill_value=self.fillval)   
        nc.createVariable('n', np.int32, ('Nobs'), fill_value=self.fillval)  
        # Use of jday should depend on clim vs interann
        if self.interannual: # AVISO or interannual ROMS solution
            nc.createVariable('j1', np.int32, ('Nobs'), fill_value=self.fillval)
        else: # climatological ROMS solution
            nc.createVariable('ocean_time', 'f8', ('Nobs'), fill_value=self.fillval)
        nc.createVariable('lon', 'f8', ('Nobs'), fill_value=self.fillval)
        nc.createVariable('lat', 'f8', ('Nobs'), fill_value=self.fillval)
        nc.createVariable('A', 'f8', ('Nobs'), fill_value=self.fillval)
        nc.createVariable('L', 'f8', ('Nobs'), fill_value=self.fillval)
        nc.createVariable('U', 'f8', ('Nobs'), fill_value=self.fillval)
        nc.createVariable('Teke', 'f8', ('Nobs'), fill_value=self.fillval)
        nc.createVariable('radius_e', 'f8', ('Nobs'), fill_value=self.fillval)
        if 'Q' in self.diag_type:
            nc.createVariable('qparameter', 'f8', ('Nobs'), fill_value=self.fillval)
        if 'ROMS' in self.datatype:
            nc.createVariable('temp', 'f8', ('Nobs'), fill_value=self.fillval)
            nc.createVariable('salt', 'f8', ('Nobs'), fill_value=self.fillval)
            
        #nc.createVariable('NLP', 'f8', ('Nobs'), fill_value=self.fillval)
        nc.createVariable('bounds', np.int16, ('Nobs','four'), fill_value=self.fillval)
        nc.createVariable('eddy_duration', np.int16, ('Nobs'), fill_value=self.fillval)
        
        # Meta data for variables
        nc.variables['track'].units = 'ordinal'
        nc.variables['track'].min_val = np.int32(0)
        nc.variables['track'].long_name = 'track number'
        nc.variables['track'].description = 'eddy identification number'
        
        nc.variables['n'].units = 'ordinal'
        #nc.variables['n'].min_val = 4
        #nc.variables['n'].max_val = 293
        nc.variables['n'].long_name = 'observation number'
        # Add option here to set length of intervals.....
        nc.variables['n'].description = 'observation sequence number (XX day intervals)'
        
        ## Use of jday should depend on clim vs interann
        if self.interannual: # AVISO or interannual ROMS solution
            nc.variables['j1'].units = 'days'
            #nc.variables['j1'].min_val = 2448910
            #nc.variables['j1'].max_val = 2455560
            nc.variables['j1'].long_name = 'Julian date'
            nc.variables['j1'].description = 'date of this observation'
            nc.variables['j1'].reference = self.jday_ref
            nc.variables['j1'].reference_description = 'Julian date at Jan 1, 1992'
        else: # climatological ROMS solution
            nc.variables['ocean_time'].units = 'ROMS ocean_time (seconds)'
        
        nc.variables['eddy_duration'].units = 'days'
        nc.variables['lon'].units = 'deg. longitude'
        nc.variables['lon'].min_val = self.lonmin
        nc.variables['lon'].max_val = self.lonmax
        nc.variables['lat'].units = 'deg. latitude'
        nc.variables['lat'].min_val = self.latmin
        nc.variables['lat'].max_val = self.latmax

        if 'Q' in self.diag_type:
            nc.variables['A'].units = 'None, normalised vorticity (abs(xi)/f)'
        elif 'sla' in self.diag_type:
            nc.variables['A'].units = 'cm'
        nc.variables['A'].min_val = self.ampmin
        nc.variables['A'].max_val = self.ampmax
        nc.variables['A'].long_name = 'amplitude'
        nc.variables['A'].description = 'magnitude of the height difference ' + \
                                        'between the extremum of SSH within ' + \
                                        'the eddy and the SSH around the contour ' + \
                                        'defining the eddy perimeter'
        
        nc.variables['L'].units = 'km'
        nc.variables['L'].min_val = self.radmin / 1000.
        nc.variables['L'].max_val = self.radmax / 1000.
        nc.variables['L'].long_name = 'speed radius scale'
        nc.variables['L'].description = 'radius of a circle whose area is equal ' + \
                                        'to that enclosed by the contour of ' + \
                                        'maximum circum-average speed'
        
        nc.variables['U'].units = 'cm/sec'
        #nc.variables['U'].min = 0.
        #nc.variables['U'].max = 376.6
        nc.variables['U'].long_name = 'maximum circum-averaged speed'
        nc.variables['U'].description = 'average speed of the contour defining ' + \
                                        'the radius scale L'
        nc.variables['Teke'].units = 'm^2/sec^2'
        #nc.variables['Teke'].min = 0.
        #nc.variables['Teke'].max = 376.6
        nc.variables['Teke'].long_name = 'sum EKE within contour Ceff'
        nc.variables['Teke'].description = 'sum of eddy kinetic energy within contour defining ' + \
                                        'the effective radius'
        
        nc.variables['radius_e'].units = 'km'
        nc.variables['radius_e'].min_val = self.radmin / 1000.
        nc.variables['radius_e'].max_val = self.radmax / 1000.
        nc.variables['radius_e'].long_name = 'effective radius scale'
        nc.variables['radius_e'].description = 'effective eddy radius'
        
        
        if 'Q' in self.diag_type:
            nc.variables['qparameter'].units = 's^{-2}'
        #nc.variables['NLP'].units = 'None, swirl vel. / propagation vel.'
        #nc.variables['NLP'].long_name = 'Non-linear parameter'

        if 'ROMS' in self.datatype:
            nc.variables['temp'].units = 'deg. C'
            nc.variables['salt'].units = 'psu'
        nc.variables['bounds'].units = 'indices to eddy location (imin,imax,jmin,jmax);' +  \
            ' use like this: var[jstr:jend,istr:iend][jmin:jmax,imin:imax]'
        
        if self.track_extra_variables:
            
            nc.createDimension('contour_points', None)
            nc.createDimension('Uavg_contour_count', np.int(self.slaparameter.size * 0.333))
            nc.createVariable('contour_e', 'f4', ('contour_points','Nobs'), fill_value=self.fillval)
            nc.createVariable('contour_s', 'f4', ('contour_points','Nobs'), fill_value=self.fillval)
            nc.createVariable('Uavg_profile', 'f4', ('Uavg_contour_count','Nobs'), fill_value=self.fillval)
            nc.createVariable('shape_error', 'f4', ('Nobs'), fill_value=self.fillval)
            
            nc.variables['contour_e'].long_name = 'positions of effective contour points'
            nc.variables['contour_e'].description = 'lons/lats of effective contour points; ' + \
                                                    'lons (lats) in first (last) half of vector'
            nc.variables['contour_s'].long_name = 'positions of speed-based contour points'
            nc.variables['contour_s'].description = 'lons/lats of speed-based contour points; ' + \
                                                    'lons (lats) in first (last) half of vector'
            nc.variables['Uavg_profile'].long_name = 'radial profile of Uavg'
            nc.variables['Uavg_profile'].description = 'all Uavg values from effective contour inwards to ' + \
                                                       'smallest inner contour (pixel == 1)'
            nc.variables['shape_error'].units = '%'
        
        nc.close()
        return self
        


    def _reduce_inactive_tracks(self):
        '''
        Remove dead tracks
        '''
        #start_time = time.time()
        for track in self.tracklist:
            if not track.alive:
                track.lon = []
                track.lat = []
                track.qparameter = []
                track.amplitude = []
                track.Uavg = []
                track.teke = []
                track.radius_s = []
                track.radius_e = []
                track.bounds = []
                track.ocean_time = []
                if self.track_extra_variables:
                    track.contour_e = []
                    track.contour_s = []
                    track.Uavg_profile = []
                    track.shape_error = []
        #print '_reduce_inactive_tracks', str(time.time() - start_time), ' seconds!'
        return
    
    
    #def get_non_lin_param(self, i):
        #'''
        #Return the non-linearity parameter along a track
        #'''
        ##start_time = time.time()
        #distances = haversine_distance_vector(self.tracklist[i].lon[:-1],
                               #self.tracklist[i].lat[:-1],
                               #self.tracklist[i].lon[1:],
                               #self.tracklist[i].lat[1:])
        #distances = np.concatenate((distances[0][np.newaxis],
                                    #distances,
                                    #distances[-1][np.newaxis]))
        #distances = distances[:-1]
        #distances += distances[1:]
        #distances *= 0.5
        #distances /= (self.days_btwn_recs * 86400.)
        #return np.array([self.tracklist[i].Uavg]) / distances
    
    
    def write2chelton_nc(self, rtime):
        '''
        Write inactive tracks to netcdf file.
        'ncind' is important because prevents writing of 
        already written tracks.
        Each inactive track is 'emptied' after saving
        '''
        nc = netcdf.Dataset(self.savedir, 'a')
        inactive_tracks = self.get_inactive_tracks(rtime)
        tracks2save = np.asarray(inactive_tracks)
        
        #print 'tracks2save', tracks2save
        
        if np.any(tracks2save): # Note, this could break if all eddies become inactive at same time
            
            for i in np.nditer(tracks2save):

                # saved2nc is a flag indicating if track[i] has been saved
                if np.logical_and(not self.tracklist[i].saved2nc,
                                  np.all(self.tracklist[i].ocean_time)):
     
                    #tsize = self.tracklist[i].ocean_time.size
                    tsize = len(self.tracklist[i].lon)
                    #print 'ncindncindncind',self.ncind
                    if tsize >= self.track_duration_min / self.days_btwn_recs and tsize > 1.:

                        tend = self.ncind + tsize
                        
                        #if self.sign_type in 'Anticyclonic':
                            #print '\ntsize', tsize
                            #print self.ncind, tend
                            #print 'np.array([self.tracklist[i].lon])',np.asarray([self.tracklist[i].lon])
                            
                            #print "\nnc.variables['lon'][:tend]", nc.variables['lon'][:tend]
                            #print "nc.variables['lon'][self.ncind:tend]", nc.variables['lon'][self.ncind:tend]
                        
                        
                        nc.variables['lon'][self.ncind:tend] = np.asarray(self.tracklist[i].lon)
                        nc.variables['lat'][self.ncind:tend] = np.asarray([self.tracklist[i].lat])
                        nc.variables['A'][self.ncind:tend] = np.array([self.tracklist[i].amplitude])
                        self.tracklist[i].Uavg *= np.array(100.) # to cm/s
                        nc.variables['U'][self.ncind:tend] = self.tracklist[i].Uavg
                        nc.variables['Teke'][self.ncind:tend] = np.array([self.tracklist[i].teke])
                        self.tracklist[i].radius_s *= np.array(1e-3) # to km
                        nc.variables['L'][self.ncind:tend] = self.tracklist[i].radius_s
                        self.tracklist[i].radius_e *= np.array(1e-3) # to km
                        nc.variables['radius_e'][self.ncind:tend] = self.tracklist[i].radius_e
                        if 'ROMS' in self.datatype:
                            nc.variables['temp'][self.ncind:tend] = np.array([self.tracklist[i].temp])
                            nc.variables['salt'][self.ncind:tend] = np.array([self.tracklist[i].salt])
                        nc.variables['bounds'][self.ncind:tend] = np.array([self.tracklist[i].bounds])
                        if self.interannual:
                            # We add 1 because 'j1' is an integer in ncsavefile; julian day midnight has .5
                            # i.e., dt.julian2num(2448909.5) -> 727485.0
                            nc.variables['j1'][self.ncind:tend] = dt.num2julian(np.array([self.tracklist[i].ocean_time])) + 1
                        else:
                            nc.variables['ocean_time'][self.ncind:tend] = np.array([self.tracklist[i].ocean_time])
                        nc.variables['n'][self.ncind:tend] = np.arange(tsize, dtype=np.int32)
                        nc.variables['track'][self.ncind:tend] = np.full(tsize, self.ch_index)
                        nc.variables['track'].max_val = np.int32(self.ch_index)
                        nc.variables['eddy_duration'][self.ncind:tend] = np.array([self.tracklist[i].ocean_time]).size \
                                                                                 * self.days_btwn_recs
                        if self.track_extra_variables:
                            nc.variables['shape_error'][self.ncind:tend] = np.array([self.tracklist[i].shape_error])
                            for j in np.arange(tend - self.ncind):
                                jj = j + self.ncind
                                contour_e_arr = np.asarray(self.tracklist[i].contour_e[j]).ravel()
                                nc.variables['contour_e'][:contour_e_arr.size,jj] = contour_e_arr
                                contour_s_arr = np.asarray(self.tracklist[i].contour_s[j]).ravel()
                                nc.variables['contour_s'][:contour_s_arr.size,jj] = contour_s_arr
                                #print 'BBBBBBBB', np.asarray(self.tracklist[i].Uavg_profile).ravel()
                                #print 'j',j
                                Uavg_profile_arr = np.asarray(self.tracklist[i].Uavg_profile[j]).ravel()
                                nc.variables['Uavg_profile'][:Uavg_profile_arr.size,jj] = Uavg_profile_arr #np.asarray(self.tracklist[i].Uavg_profile[j]).ravel()
                        
                        # Flag indicating track[i] is now saved
                        self.tracklist[i].saved2nc = True
                        self.ncind += tsize
                        self.ch_index += 1
                        nc.sync()
        
        nc.close()

        # Get index to first currently active track
        try:
            lasti = self.get_active_tracks(rtime)[0]
        except Exception:
            lasti = None
        
        # Clip tracklist, removing all dead tracks preceding first currently active track
        self.tracklist = self.tracklist[lasti:]
        self.index = len(self.tracklist) # adjust index accordingly
        # Remove inactive tracks
        self._reduce_inactive_tracks()
        
        # Update old_lon and old_lat...
        self.old_lon     = self.new_lon[lasti:]
        self.old_lat     = self.new_lat[lasti:]
        self.old_radii_s = self.new_radii_s[lasti:]
        self.old_radii_e = self.new_radii_e[lasti:]
        self.old_amp     = self.new_amp[lasti:]
        self.old_Uavg    = self.new_Uavg[lasti:]
        self.old_teke    = self.new_teke[lasti:]
        self.old_bounds  = self.new_bounds[lasti:]
        
        self.new_lon     = np.array([])
        self.new_lat     = np.array([])
        self.new_radii_s = np.array([])
        self.new_radii_e = np.array([])
        self.new_amp     = np.array([])
        self.new_Uavg    = np.array([])
        self.new_teke    = np.array([])
        self.new_time    = np.array([])
        self.new_bounds  = np.atleast_2d(np.empty(4, dtype=np.int16))
        
        if 'ROMS' in self.datatype:
            self.old_temp = self.new_temp[lasti:]
            self.old_salt = self.new_salt[lasti:]
            
            self.new_temp = np.array([])
            self.new_salt = np.array([])
        
        if self.track_extra_variables:
            self.old_contour_e = list(self.new_contour_e[lasti:])
            self.old_contour_s = list(self.new_contour_s[lasti:])
            self.old_Uavg_profile = list(self.new_Uavg_profile[lasti:])
            self.old_shape_error = self.new_shape_error[lasti:]
            
            self.new_contour_e = []
            self.new_contour_s = []
            self.new_Uavg_profile = []
            self.new_shape_error = np.array([])
            
        return self
        
        
    def get_distances(self, centlon, centlat):
        '''
        Return distances for the current centroid (centlon,
        centlat) and arrays (self.old_lon, self.old_lat)
        '''
        clon = self.old_lon.copy()
        clat = self.old_lat.copy()
        clon.fill(centlon)
        clat.fill(centlat)
        return haversine_distance_vector(clon, clat, self.old_lon, self.old_lat)


    def insert_at_index(self, xarr, ind, x):
        '''
        For some reason Python doesn't do matlab's
        x(3)=4 gives [0  0  4] and then
        x(5)=7 gives [0  0  4  0  7]
        ------------------------------------------------------------------
        THIS IS SLOW BECAUSE REMAKES THE ARRAY EVERY TIME
        TRY UPDATING WITH VERY LONG ZERO ARRAYS...
        
        This is the way to do it, all tracks as lists rather than np arrays
        try:
            self.new_lon[ind] = x
        except:
            self.new_lon += [0] * (ind - len(self.new_lon) + 1)
            self.new_lon[ind] = x
        THIS IMPLIES CHANGING TO LISTS ALL THROUGH THE CODE... NOT URGENT FOR NOW
        ------------------------------------------------------------------
        
        '''
        tmp = eval('self.' + xarr)
        
        if isinstance(tmp, np.ndarray):
            tmp  = np.copy(tmp)
            if ind < tmp.size:
                newsize = tmp.size
            else:
                newsize = ind + 1
            #print 'numpy-------'
        
        elif isinstance(tmp, list):
            tmp = list(tmp)
            if ind < len(tmp):
                newsize = len(tmp)
            else:
                newsize = ind + 1
            #print 'list-------'
        
        else:
            Exception
        
        if strcompare('new_lon', xarr):
            self.new_lon = np.zeros((newsize))
            self.new_lon[:tmp.size] = tmp
            self.new_lon[ind] = x
        elif strcompare('new_lat', xarr):
            self.new_lat = np.zeros((newsize))
            self.new_lat[:tmp.size] = tmp
            self.new_lat[ind] = x
        elif strcompare('new_radii_s', xarr):
            self.new_radii_s = np.zeros((newsize))
            self.new_radii_s[:tmp.size] = tmp
            self.new_radii_s[ind] = x
        elif strcompare('new_radii_e', xarr):
            self.new_radii_e = np.zeros((newsize))
            self.new_radii_e[:tmp.size] = tmp
            self.new_radii_e[ind] = x
        elif strcompare('new_amp', xarr):
            self.new_amp = np.zeros((newsize))
            self.new_amp[:tmp.size] = tmp
            self.new_amp[ind] = x
        elif strcompare('new_Uavg', xarr):
            self.new_Uavg = np.zeros((newsize))
            self.new_Uavg[:tmp.size] = tmp
            self.new_Uavg[ind] = x
        elif strcompare('new_teke', xarr):
            self.new_teke = np.zeros((newsize))
            self.new_teke[:tmp.size] = tmp
            self.new_teke[ind] = x
        elif strcompare('new_temp', xarr):
            self.new_temp = np.zeros((newsize))
            self.new_temp[:tmp.size] = tmp
            self.new_temp[ind] = x
        elif strcompare('new_salt', xarr):
            self.new_salt = np.zeros((newsize))
            self.new_salt[:tmp.size] = tmp
            self.new_salt[ind] = x
        elif strcompare('new_shape_error', xarr):
            self.new_shape_error = np.zeros((newsize))
            self.new_shape_error[:tmp.size] = tmp
            self.new_shape_error[ind] = x
        elif strcompare('new_bounds', xarr):
            if ind < tmp.shape[0]:
                newsize = tmp.size
            else:
                newsize = ind + 1
            self.new_bounds = np.zeros((newsize, 4))
            self.new_bounds[:tmp.shape[0]] = tmp
            self.new_bounds[ind] = x
        
        elif strcompare('new_contour_e', xarr):
            try:
                self.new_contour_e[ind] = x
            except:
                self.new_contour_e += [0] * (ind - len(self.new_contour_e) + 1)
                self.new_contour_e[ind] = x
        elif strcompare('new_contour_s', xarr):
            try:
                self.new_contour_s[ind] = x
            except:
                self.new_contour_s += [0] * (ind - len(self.new_contour_s) + 1)
                self.new_contour_s[ind] = x
        elif strcompare('new_Uavg_profile', xarr):
            try:
                self.new_Uavg_profile[ind] = x
            except:
                self.new_Uavg_profile += [0] * (ind - len(self.new_Uavg_profile) + 1)
                self.new_Uavg_profile[ind] = x
        else:
            raise Exception
        return self


    def update_eddy_properties(self, centlon, centlat, eddy_radius_s, eddy_radius_e,
                               amplitude, Uavg, teke, rtime, bounds,
                               contour_e=None, contour_s=None,
                               Uavg_profile=None, shape_error=None,
                               cent_temp=None, cent_salt=None):
        '''
        Append new variable values to track arrays
        '''
        #print 'self.new_lon_tmp', self.new_lon_tmp
        #print 'centlon', centlon
        self.new_lon_tmp = np.r_[self.new_lon_tmp, centlon]
        self.new_lat_tmp = np.r_[self.new_lat_tmp, centlat]
        self.new_radii_tmp_s = np.r_[self.new_radii_tmp_s, eddy_radius_s]
        self.new_radii_tmp_e = np.r_[self.new_radii_tmp_e, eddy_radius_e]
        self.new_amp_tmp = np.r_[self.new_amp_tmp, amplitude]
        self.new_Uavg_tmp = np.r_[self.new_Uavg_tmp, Uavg]
        self.new_teke_tmp = np.r_[self.new_teke_tmp, teke]
        self.new_time_tmp = np.r_[self.new_time_tmp, rtime]
        #print self.new_time_tmp
        #print self.new_lon_tmp
        if 'ROMS' in self.datatype:
            #self.new_temp_tmp = np.r_[self.new_temp_tmp, cent_temp]
            #self.new_salt_tmp = np.r_[self.new_salt_tmp, cent_salt]
            pass
        try:
            self.new_bounds_tmp = np.vstack((self.new_bounds_tmp, bounds))
        except Exception:    
            self.new_bounds_tmp = np.hstack((self.new_bounds_tmp, bounds))
        if self.track_extra_variables:
	    #print 'self.new_shape_error_tmp', self.new_shape_error_tmp
	    #print 'shape_error', shape_error
            self.new_contour_e_tmp.append(contour_e)
            self.new_contour_s_tmp.append(contour_s)
            self.new_Uavg_profile_tmp.append(Uavg_profile)
            self.new_shape_error_tmp = np.r_[self.new_shape_error_tmp, shape_error]
        return self
    
    
        
    
    def get_bounds(self, centlon, centlat, radius, i, j, grd):
        '''
        Get indices to a bounding box around the eddy
        '''
        def get_angle(deg, ang):
            return deg - np.rad2deg(ang)
        
        grdangle = grd.angle()[j,i]
        
        a_lon, a_lat = newPosition(centlon, centlat, get_angle(0, grdangle), radius)
        b_lon, b_lat = newPosition(centlon, centlat, get_angle(90, grdangle), radius)
        c_lon, c_lat = newPosition(centlon, centlat, get_angle(180, grdangle), radius)
        d_lon, d_lat = newPosition(centlon, centlat, get_angle(270, grdangle), radius)
                            
        # Get i,j of bounding box around eddy
        a_i, a_j = nearest(a_lon, a_lat, grd.lon(), grd.lat())
        b_i, b_j = nearest(b_lon, b_lat, grd.lon(), grd.lat())
        c_i, c_j = nearest(c_lon, c_lat, grd.lon(), grd.lat())
        d_i, d_j = nearest(d_lon, d_lat, grd.lon(), grd.lat())
                                        
        self.imin = np.maximum(np.min([a_i, b_i, c_i, d_i]) - 5, 0) # Must not go
        self.jmin = np.maximum(np.min([a_j, b_j, c_j, d_j]) - 5, 0) # below zero
        self.imax = np.max([a_i, b_i, c_i, d_i]) + 5
        self.jmax = np.max([a_j, b_j, c_j, d_j]) + 5
        return self
    


class RossbyWaveSpeed (object):
  
    def __init__(self, domain, limits, rw_path=None):
        '''
        Initialise the RossbyWaveSpeedsobject
        '''
        self.domain = domain
        self.rw_path = rw_path
        if self.domain in ('Global', 'ROMS'):
            assert self.rw_path is not None, \
                'Must supply a path for the Rossby deformation radius data'
            data = np.loadtxt(rw_path)
            self._lon = data[:,1] - 360.
            self._lat = data[:,0]
            self._defrad = data[:,3]
            self.limits = limits
            self._make_subset()
            self.vartype = 'variable'
        else:
            self.vartype = 'constant'
        self.distance = np.empty(1)
        self.start = True
    
        
    def get_rwdistance(self, x, y, days_between_records):
        '''
        '''
        if self.domain in ('Global', 'ROMS'):
	    #print 'x,y', x,y
            self.distance[:] = self._get_rlongwave_spd(x, y)
            self.distance *= 86400.
            #if self.domain in 'ROMS':
                #self.distance *= 1.5
        elif 'BlackSea' in self.domain:
            self.distance[:] = 15000. # e.g., Blokhina & Afanasyev, 2003
        elif 'MedSea' in self.domain:
            self.distance[:] = 20000.
        else:
            Exception # Unknown domain
        if self.start:
            print '------ setting ellipse for %s domain' %self.domain
            print '------ using %s Rossby deformation radius of %s m' \
                                %(self.vartype, np.abs(self.distance[0]))
            self.start = False
        self.distance *= days_between_records
        return np.abs(self.distance)
    
    
    def _make_subset(self):
        '''
        '''
        pad = 1.5 # degrees
        lonmin, lonmax, latmin, latmax = self.limits
        lloi = np.logical_and(self._lon >= lonmin - pad,
                              self._lon <= lonmax + pad)
        lloi *= np.logical_and(self._lat >= latmin - pad,
                               self._lat <= latmax + pad)
        self._lon = self._lon[lloi]
        self._lat = self._lat[lloi]
        self._defrad = self._defrad[lloi]
        self._make_kdtree()
    
    
    def _make_kdtree(self):
        points = np.vstack([self._lon, self._lat]).T
        self._tree = spatial.cKDTree(points)
    
    
    def _get_defrad(self, x, y):
        '''
        Get a point average of the deformation radius
        at x, y
        '''
        weights, i = self._tree.query(np.array([x, y]), k=4, p=2)
        weights /= weights.sum()
        self._weights = weights
        self.i = i
        return np.average(self._defrad[i], weights=weights)
    
    
    def _get_rlongwave_spd(self, x, y):
        '''
        Get the longwave phase speed, see Chelton etal (2008) pg 446:
          c = -beta * defrad**2 (this only for extratropical waves...)
        '''
        r_spd_long = self._get_defrad(x, y)
        r_spd_long *= 1000. # km to m
        r_spd_long **= 2
        lat = np.average(self._lat[self.i], weights=self._weights)
        beta = np.cos(np.deg2rad(lat))
        beta *= 1458e-7 # 1458e-7 ~ (2 * 7.29*10**-5)
        beta /= 6371315.0
        r_spd_long *= -beta
        return r_spd_long
    

    
    
class SearchEllipse (object):
    
    def __init__(self, domain, days_btwn_recs, rw_path, limits):
        '''Class to construct a search ellipse/circle around a specified point.
        
        
        
        '''
        self.domain = domain
        self.days_btwn_recs = days_btwn_recs
        self.rw_path = rw_path
        self.limits = limits
        self.rw_d_fac = 1.75
        self.e_w_major = self.days_btwn_recs * 3e5 / 7.
        self.n_s_minor = self.days_btwn_recs * 15e4 / 7.
        self.rwv = RossbyWaveSpeed(self.domain,
                               self.limits, rw_path=self.rw_path)
        self.rw_d = np.empty(1)
        self.rw_d_mod = np.empty(1)
        
    def _set_east_ellipse(self):
        '''
        '''
        self.east_ellipse = patch.Ellipse((self.x, self.y),
                                           self.e_w_major, self.n_s_minor)
        return self
        
    def _set_west_ellipse(self):
        '''
        '''
        self.west_ellipse = patch.Ellipse((self.x, self.y),
                                           self.rw_d_mod, self.n_s_minor)
        return self
        
    def _set_global_ellipse(self):
        '''
        '''
        self._set_east_ellipse()._set_west_ellipse()
        e_verts = self.east_ellipse.get_verts()
        e_size = e_verts[:,0].size
        e_size *= 0.5
        w_verts = self.west_ellipse.get_verts()
        w_size = w_verts[:,0].size
        w_size *= 0.5
        ew_x = np.hstack((e_verts[:e_size,0], w_verts[w_size:,0]))
        ew_y = np.hstack((e_verts[:e_size,1], w_verts[w_size:,1]))
        self.ellipse_path = path.Path(np.array([ew_x, ew_y]).T)
        return self.ellipse_path
        
    def _set_black_sea_ellipse(self):
        '''
        '''
        self.black_sea_ellipse = patch.Ellipse((self.x, self.y),
                               2. * self.rw_d_mod, 2. * self.rw_d_mod)
        verts = self.black_sea_ellipse.get_verts()
        self.ellipse_path = path.Path(np.array([verts[:,0],
                                                verts[:,1]]).T)
            
            
    def get_search_ellipse(self, x, y):
        '''
        '''
        self.x = x
        self.y = y
        if self.domain in ('Global', 'ROMS'):
            self.rw_d[:] = self.rwv.get_rwdistance(x, y, self.days_btwn_recs)
            self.rw_d_mod[:] = 1.75
            self.rw_d_mod *= self.rw_d
            self.rw_d_mod[:] = np.maximum(self.rw_d_mod, self.n_s_minor)
            self.rw_d_mod *= 2.
            self._set_global_ellipse()
            
        elif 'BlackSea'  in self.domain:
            self.rw_d_mod[:] = 1.75
            self.rw_d[:] = self.rwv.get_rwdistance(x, y, self.days_btwn_recs)
            self.rw_d_mod *= self.rw_d
            self._set_black_sea_ellipse()
        
        else: Exception
            
            
    def view_search_ellipse(self, Eddy):
        '''
        Input A_eddy or C_eddy
        '''
        plt.figure()
        ax = plt.subplot(111)
        ax.set_title('Rossby def. rad %s m' %self.rw_d[0])
        Eddy.M.scatter(self.x, self.y, c='b')
        #Eddy.M.plot(ee[:,0], ee[:,1], 'b')
        #Eddy.M.plot(ww[:,0], ww[:,1], 'g')
        Eddy.M.plot(self.ellipse_path.vertices[:,0],
                    self.ellipse_path.vertices[:,1], 'r')
        Eddy.M.drawcoastlines()
        plt.show()
    
    
    
'''
def pickle_track(track_list, file):
    file = open(file, 'wb')
    pickle.dump(track_list, file)
    file.close()
    return

def unpickle_track(file):
    file = open(file, 'rb')
    data = pickle.load(file)
    file.close()
    return data
'''
##############################################################


if __name__ == '__main__':

    lon_ini = -10.
    lat_ini = 25.
    time_ini = 247893
    index = 0
    
    trackA = track_list(index, lon_ini, lat_ini, time_ini, 0, 0)
    print 'trackA lon:', trackA.tracklist[0].lon
    
    # update track 0
    trackA.update_track(0, -22, 34, 333344, 0, 0)
    trackA.update_track(0, -87, 37, 443344, 0, 0)
    trackA.update_track(0, -57, 57, 543344, 0, 0)
    print 'trackA lon:', trackA.tracklist[0].lon
    
    # start a new track
    trackA.append_list(-33, 45, 57435, 0, 0)
    print '\ntrackA lat:', trackA.tracklist[1].lat
    
    trackA.update_track(1, -32, 32, 4453344, 0, 0)
    print 'trackA lat:', trackA.tracklist[1].lat
    
    
    # Pickle
    output = open('data.pkl', 'wb')
    pickle.dump(trackA, output)
    output.close()
    
    # Unpickle
    pkl_file = open('data.pkl', 'rb')
    data1 = pickle.load(pkl_file)
    pkl_file.close()









