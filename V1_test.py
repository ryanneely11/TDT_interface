##visual_tuning_2.py
##by Ryan Neely
##a program to acquire neural data during the presentation of 
##drifting grating visual stimuli. 
##Designed to run with TDT hardware and ActiveX controls as 
##well as psychopy in order to generate stimuli.

from psychopy import visual
from psychopy import core
from psychopy import info
import TDT_control_ax as TDT_control
import matplotlib
matplotlib.use("WX")
import matplotlib.pyplot as plt
import h5py
import numpy as np
#from multiprocessing.pool import ThreadPool
import pickle
from scipy.signal import butter, lfilter
import os
import time

##grating variables
#directions of movement (list). -1 is the baseline gray screen
##***NOTE: for plotting to be correct, the gray screen value should be last in the array!!!***
DIRECTIONS = np.array([0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, -1])
#the spatial frequency of the grating in cycles/degree
SPATIAL_FREQ = 0.1
##amount of time to display the gray screen in seconds
GRAY_TIME = 2.0
##amount of time to display the drifting grating in seconds
DRIFT_TIME = 2.0
#the number of times to repeat the full set of gratings
NUM_SETS = 20
##define filter functions
def butter_bandpass(lowcut, highcut, fs, order=5):
	nyq = 0.5 * fs
	low = lowcut / nyq
	high = highcut / nyq
	b, a = butter(order, [low, high], btype='band')
	return b, a


def butter_bandpass_filter(data, lowcut, highcut, fs, order=5):
	b, a = butter_bandpass(lowcut, highcut, fs, order=order)
	y = lfilter(b, a, data)
	return y


def run_orientations(save_loc,circ_loc,chans,plot = True):
	##load the spcified circuit file and connect to the processor
	"""
	NOTE: Loading the wrong file isn't immediately obvious and can cause
	a lot of headaches!!
	"""
	RZ2 = TDT_control.RZ2(circ_loc)
	##load the RPvdsEx circuit locally
	RZ2.load_circuit(local = True, start = True)
	##get the processor sampling rate
	fs = RZ2.get_fs()
	#print 'sample rate is: ' + str(fs)
	##the number of samples to take from the TDT (duration of each stim rep)
	num_samples = int(np.ceil(fs*(DRIFT_TIME+2*GRAY_TIME)))
	x_axis = np.linspace(0,1000*(GRAY_TIME+DRIFT_TIME+GRAY_TIME), num_samples)
	##double check that the TDT processors are connected and the circuit is running
	if RZ2.get_status() != 7:
		raise SystemError, "Check RZ2 status!"
	dataFile = h5py.File(save_loc,'w')
	
	##a function to stream data from the TDT hardware. 
	##args are obvious except for pause- this value, if not None,
	##intentionally slows down the data rate by pausing in between
	##reads. This is because you can overload th TDT bus by asking for 
	##to much data at once. Value is seconds.
	def get_data(chans_list, n_samp, dtype="F32", pause = None):
		print "in data loop"
		n_chan = max(chans_list) ##if there are channels not selected in this range they will be zeros in the data
		##allocate memory; channels x samples 
		data = np.zeros((n_chan, n_samp))
		##we are assuming the channels are distributed across
		#multiple processors, and we don't want to grab all channes
		##from once processor at once and overload it, so randomize the order
		np.random.shuffle(chans_list)
		##go through each channel and grab however many samples
		for c in chans_list:
			print "reading channel "+str(c)
			data[c-1,:] = RZ2.read_target(str(c), 0, n_samp, 1, dtype, dtype).squeeze()
			if pause is not None:
				time.sleep(pause)
		return data

	print "Running orientation presentation."
	if plot:
		fig1 = plt.figure(figsize = (20,10))
		ax1 = fig1.add_subplot(221)
		ax2 = fig1.add_subplot(223)
		ax3 = fig1.add_subplot(222)
		ax4 = fig1.add_subplot(224)
		#full data
		p_data, = ax1.plot(x_axis, np.zeros(num_samples),'k')
		#zoomed data
		z_data, = ax2.plot(x_axis, np.zeros(num_samples),'k')
		##spikband data
		s_data, = ax3.plot(x_axis, np.zeros(num_samples),'r')
		#lfpband data
		l_data, = ax4.plot(x_axis, np.zeros(num_samples),'g')
		ax1.axvspan(GRAY_TIME*1000, GRAY_TIME*1000+DRIFT_TIME*1000, 
			alpha = 0.5, color = 'royalblue')
		ax2.axvspan(GRAY_TIME*1000, GRAY_TIME*1000+DRIFT_TIME*1000, 
			alpha = 0.5, color = 'royalblue')
		ax3.axvspan(GRAY_TIME*1000, GRAY_TIME*1000+DRIFT_TIME*1000, 
			alpha = 0.5, color = 'royalblue')
		ax4.axvspan(GRAY_TIME*1000, GRAY_TIME*1000+DRIFT_TIME*1000, 
			alpha = 0.5, color = 'royalblue')		
		ax1.set_title("Full trace", fontsize = 12)
		ax2.set_title("Onset", fontsize = 12)
		ax2.set_xlim(GRAY_TIME*1000-100, GRAY_TIME*1000+400)
		ax2.set_xlabel("time, ms")
		ax2.set_ylabel("mV")
		ax1.set_ylabel("mV")
		ax4.set_xlabel("time, ms")
		ax3.set_title("Spike band", fontsize = 12)
		ax4.set_title("LFP band", fontsize = 12)
		fig1.set_size_inches((12,8))
	##create a window for the stimuli
	myWin = visual.Window([800,480] ,monitor="RPi_5in", units="deg", fullscr = True, screen = 1)
	# ##get the system/monitor info (interested in the refresh rate)
	# print "Testing monitor refresh rate..."
	# sysinfo = info.RunTimeInfo(author = 'Ryan', version = '1.0', win = myWin, 
	# 	refreshTest = 'grating', userProcsDetailed = False, verbose = False)
	# ##get the length in ms of one frame
	# frame_dur = float(sysinfo['windowRefreshTimeMedian_ms'])
	frame_dur = 15.22749 #calculated beforehand

	##create a grating object
	grating = visual.GratingStim(win=myWin, mask = None, size=40,
	                             pos=[0,0], sf=SPATIAL_FREQ, ori = 0, units = 'deg')
	##calculate the number of frames needed to produce the correct display time
	num_frames = int(np.ceil((DRIFT_TIME*1000.0)/frame_dur))
	##set RZ2 recording time parameters
	RZ2.set_tag("samples", num_samples)
	##generate the stimuli
	for setN in range(NUM_SETS):
		print "Beginning set " + str(setN+1) + " of " + str(NUM_SETS)
		##shuffle the orientations
		np.random.shuffle(DIRECTIONS)
		##create a file group for this set
		set_group = dataFile.create_group("set_" + str(setN+1))
		for repN in range(DIRECTIONS.size):
			##make sure you are still connected to the RZ2
			if RZ2.get_status() != 7:
				raise SystemError, "Hardware connection lost"
			##create a dataset for this orientation
			dset = set_group.create_dataset(str(DIRECTIONS[repN]), (max(chans),num_samples), dtype = 'f')
			##initialize thread pool to stream data
			#dpool = ThreadPool(processes = 3)
			##set the contrast to zero:
			grating.contrast = 0.0
			grating.draw()
			myWin.flip()
			##trigger the RZ2 to begin recording
			print "Sending trigger"
			RZ2.send_trig(1)

			##start threads
			#sort_thread = dpool.apply_async(RZ2.stream_data, ("sorted", num_samples, 16, "I32", "int"))
			#spk_thread = dpool.apply_async(RZ2.stream_data, ("spkR", num_samples, 16, "F32", "float"))
			#lfp_thread = dpool.apply_async(RZ2.stream_data, ("lfpR", num_samples, 16, "F32", "float"))
			##pause for the Gray time
			core.wait(GRAY_TIME)
			##make sure this isn't a gray trial
			if DIRECTIONS[repN] != -1:
				##adjust the orientation
				grating.ori = DIRECTIONS[repN]
				##bring the contrast back to 100%
				grating.contrast = 1.0
				##draw the stimuli and update the window
				print "Showing orientation " + str(DIRECTIONS[repN])
				for frameN in range(num_frames):
					grating.phase = (0.026*frameN, 0.0)
					grating.draw()
					myWin.flip()
			else:
				##continue to display gray screen
				print "Showing zero contrast control"
				core.wait(DRIFT_TIME)
			##set the contrast to zero:
			grating.contrast = 0.0
			grating.draw()
			myWin.flip()
			##pause for the specified time
			core.wait(GRAY_TIME)
			##now save the data to the hdf5 file
			#raw trace
			print "getting data"
			trace_data = get_data(chans, num_samples, pause = .005)
			print "Data retrieved, saving data"
			##make sure you are still connected to the RZ2
			if RZ2.get_status() != 7:
				raise SystemError, "Hardware connection lost"
			dset[:,:] = trace_data
			print "Data saved"
			##make sure you are still connected to the RZ2
			if RZ2.get_status() != 7:
				raise SystemError, "Hardware connection lost"
			if plot:
				lfp = butter_bandpass_filter(trace_data[4,:], 0.5, 300, fs, 1)
				spike = butter_bandpass_filter(trace_data[4,:], 300, 5000, fs, 5)
				p_data.set_ydata(trace_data[4,:])
				z_data.set_ydata(trace_data[4,:])
				s_data.set_ydata(spike)
				l_data.set_ydata(lfp)
				ax1.set_ylim(trace_data[4,:].min(), trace_data[4,:].max())
				ax2.set_ylim(trace_data[4,:].min(), trace_data[4,:].max())
				ax3.set_ylim(spike.min(), spike.max())
				ax4.set_ylim(lfp.min(), lfp.max())
				fig1.suptitle(str(DIRECTIONS[repN])+" Degrees", fontsize = 18)
				fig1.canvas.draw()
	print "Orientation test complete."
	myWin.close()
	dataFile.close()
	RZ2.stop()

