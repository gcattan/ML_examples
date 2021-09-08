# -*- coding: utf-8 -*-
"""
Created on Sun Aug 22 19:54:37 2021

@author: anton andreev
"""

import numpy as np
import matplotlib.pyplot as plt

from alphawaves.dataset import AlphaWaves

import mne
from pyts.image import RecurrencePlot
import gc

#import Image
#import ImageChops
from skimage.metrics import structural_similarity as ssim

"""
=============================
Classification of EGG signal from two states: eyes open and eyes closed.
Here we use centroid classification based on reccurence plots and 1 electrode.
=============================

Anaconda 3 2021_05
Python 3.8.8
Spyder 4.2.5
Pyts 0.11 (a Python Package for Time Series Classification,exists in Anaconda, provides recurrence plots)

"""
# Authors: Anton Andreev
#
# License: BSD (3-clause)


# define the dataset instance
dataset = AlphaWaves() # use useMontagePosition = False with recent mne versions


# get the data from subject of interest
#subject = dataset.subject_list[0]
#raw = dataset._get_single_subject_data(subject)

#Parameters
#10-20 international system
#'Fp1','Fp2','Fc5','Fz','Fc6','T7','Cz','T8','P7','P3','Pz','P4','P8','O1','Oz','O2','stim'
#alpha is at the back of the brain
#start form 0
electrode = 14 #get the Oz:14
#electrode = 5 #get the T7:5
#m = 5
#tau = 30 
m = 5 
tau = 30
#rp = RecurrencePlot(threshold='point', dimension = m, time_delay = tau, percentage=20)
#rp = RecurrencePlot(threshold=0.2, dimension = m, time_delay = tau, percentage=20)
rp = RecurrencePlot(threshold='point', dimension = m, time_delay = tau, percentage=20)
n_train_subjects = 1 #max=19
filter_fmin = 3 #default 3
filter_fmax = 40 #default 40

epochs_all_subjects = [];
labels = [];
electrodes = [];
centroids = np.empty(16, dtype=object) 

test_epochs_all_subjects = [];
test_label_all_subjects = [];

def calcDist(i1, i2):
    return np.sum((i1-i2)**2)

def calcDistManhattan(i1, i2):
    return np.sum(abs((i1-i2)))

def calcDistSSIM(i1, i2):
    return -1 * ssim(i1,i2)

def calculateDistance(i1, i2):
    return calcDist(i1, i2)

channels_N = -1

print("Train data:")

#a = np.zeros((n_train_subjects * 10, 1, 16, 649, 649))

for subject in dataset.subject_list[0:n_train_subjects]: #[0:17]
    
    raw = dataset._get_single_subject_data(subject)
    
    # filter data and resample
    raw.filter(filter_fmin, filter_fmax, verbose=False)
    raw.resample(sfreq=128, verbose=False)

    # detect the events and cut the signal into epochs
    events = mne.find_events(raw=raw, shortest_event=1, verbose=False)
    event_id = {'closed': 1, 'open': 2}
    epochs_subject = mne.Epochs(raw, events, event_id, tmin=2.0, tmax=8.0, baseline=None,
                    verbose=False, preload=True)
    epochs_subject.pick_types(eeg=True)
    
    channels_N = len(raw.ch_names)-1
    
    #process raw epochs for the selected subject 
    for i in range(0, len(epochs_subject)):
        
        #processing a single sample for a subject
        
        sample = epochs_subject[i]._data[0,:,:]    
    
        #add to list
        label = list(epochs_subject[i].event_id.values())[0] - 1 #from 1..2 to 0..1
        
        for c in range(0, channels_N):
            print("elecrode=",c)
        
            #create recurrence plot of a single epoch/sample        
            X = sample[c,:]
            X = np.array([X])
            single_epoch_subject_rp = rp.fit_transform(X)
            #print(single_epoch_subject_rp.shape)
            
            
            epochs_all_subjects.append(single_epoch_subject_rp[0,:,:].copy())
            labels.append(label)
            electrodes.append(c)
            #del single_epoch_subject_rp    
        
        #del sample

        #gc.collect();
    
    #del raw
    #del epochs_subject
    #gc.collect()


#images1 = np.array(epochs_all_subjects)[:, :, :]

print(len(epochs_all_subjects), len(electrodes), len(labels))

print("Creating centroids:")


centroids = np.empty(channels_N, dtype=object) 

#version centroids only for the alpha yese close (state 0)
for e in range(0, channels_N): # we create a centroid for each electrode
    
    epochs_single_sentroid=[]
    
    for l in range(0, len(labels)):
        if labels[l] == 0: #eyes closed alpha
            epochs_single_sentroid.append(epochs_all_subjects[l])
    
    #convert np array
    RP_images = np.array(epochs_single_sentroid)[:, :, :]
    #calculate the average for each centroid
    centroids[e] = np.average(RP_images,axis=0)
            





