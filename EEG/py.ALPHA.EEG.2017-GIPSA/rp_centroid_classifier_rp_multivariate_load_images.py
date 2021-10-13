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
import os

"""
=============================
Classification of EGG signal from two states: eyes open and eyes closed.
Here we use centroid classification based on reccurence plots of many electrodes.
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
#electrode = 14 #get the Oz:14
#electrode = 5 #get the T7:5
#m = 5
#tau = 30 
m = 5 
tau = 30
#rp = RecurrencePlot(threshold='point', dimension = m, time_delay = tau, percentage=20)
#rp = RecurrencePlot(threshold=0.2, dimension = m, time_delay = tau, percentage=20)
rp = RecurrencePlot(threshold='point', dimension = m, time_delay = tau, percentage=20)
n_train_subjects = 21 #max=19
filter_fmin = 4 #default 3
filter_fmax = 13 #default 40
electrodes = [9,10,11,13,14,15]
#electrodes = [6,8,12,9,10,11,13,14,15]
#electrodes = list(range(0,16))
folder = "D:\Work\ML_examples\EEG\py.ALPHA.EEG.2017-GIPSA\multivariate_rp_images"
epochs_all_subjects = [];
label_all_subjects = [];

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


train_epochs_all_subjects = [];
train_label_all_subjects = [];

test_epochs_all_subjects = [];
test_label_all_subjects = [];

print("Train data:")

images_loaded = 0
for filename in os.listdir(folder):
    if filename.endswith(".npy"): 
        
        print(os.path.join(folder, filename))
        base_name = os.path.basename(filename)
        
        parts = base_name.split("_")
        #print(parts)
        label = int(parts[4].split(".")[0])
        subject = int(parts[1])
        print("Subject: ", subject, " Label: ", label)
        
        if (subject < n_train_subjects):
            images_loaded = images_loaded + 1
            rp_image=np.load(os.path.join(folder, filename))
            train_epochs_all_subjects.append(rp_image)
            train_label_all_subjects.append(label)
        
    else:
        continue

print("Train images loaded: ", images_loaded)

train_images1 = []
train_images2 = []

#separate classes
for i in range(0,len(train_label_all_subjects)):
    if train_label_all_subjects[i] == 0: # 0 eyes closed = alpha
        train_images1.append(train_epochs_all_subjects[i][200:280, 200:280])#[200:280, 200:280]
    else:
        train_images2.append(train_epochs_all_subjects[i][200:280, 200:280])#[200:280, 200:280]
        
print("Process Class 1 for Train data:")

images1 = np.array(train_images1) #[:, :, :]

#====================================================================================

print("Process CLass 2 for Train data:")


images2 = np.array(train_images2) #[:, :, :]
#====================================================================================

#reduce images (it seems the performance is the same)
#images1 = images1[:,330:370,330:370]
#images2 = images2[:,330:370,330:370]

# ====================================================================================
# start classification

iterations = 20
average_train_accuracy = 0;
average_classification = 0;

for i in range(iterations):
    
    np.random.shuffle(images1) #Multi-dimensional arrays are only shuffled along the first axis
    np.random.shuffle(images2)
    
    N = len(images1)
    N_validation =  N // 5
    
    # class 0
    train_images1 = images1[:N-N_validation]
    valid_images1 = images1[N-N_validation:]
    
    # class 1
    train_images2 = images2[:N-N_validation]
    valid_images2 = images2[N-N_validation:]
    
    # build centroids
    imave1 = np.average(train_images1,axis=0) #eyes closed, alpha high
    imave2 = np.average(train_images2,axis=0) #eyes opened, alpha low
    
    
    #plt.imshow(imave1, cmap='binary', origin='lower') #eyes closed, alpha high
    #plt.imshow(imave2, cmap='binary', origin='lower') #eyes opened, alpha low
    
    training_accuracy = 0
    train_all_N = len(train_images1) + len(train_images2)
    # training accuracy =======================================================================
    #print("Class 0 eyes closed")
    for x in train_images1:
        d1 = calculateDistance(x,imave1)
        d2 = calculateDistance(x,imave2)
        if (d1 < d2 ):
            training_accuracy = training_accuracy + 1

        
    #print("Class 1 eyes open")            
    for x in train_images2:
        d1 = calculateDistance(x,imave2)
        d2 = calculateDistance(x,imave1)
        if (d1 < d2 ):
            training_accuracy = training_accuracy + 1
    
    print("Training accuracy: ", training_accuracy / train_all_N)
    average_train_accuracy = average_train_accuracy + training_accuracy / train_all_N
    
    # validation test ==========================================================================
    correctly_classified = 0;
    valid_all_N = len(valid_images1) + len(valid_images2)
    
    #print("Class 0 eyes closed")
    for x in valid_images1:
        d1 = calculateDistance(x,imave1)
        d2 = calculateDistance(x,imave2)
        if (d1 < d2 ):
            #print("True")
            correctly_classified = correctly_classified + 1
        else:
            pass
            #print("False")
        
    #print("Class 1 eyes open")            
    for x in valid_images2:
        d1 = calculateDistance(x,imave2)
        d2 = calculateDistance(x,imave1)
        if (d1 < d2 ):
            correctly_classified = correctly_classified + 1
            #print("True")
        else:
            pass
            #print("False")
            
    print("Cross correlation: ", correctly_classified / valid_all_N)
    average_classification = average_classification + correctly_classified / valid_all_N

print("======================================================================================")
print("Train average accuracy: ", average_train_accuracy / iterations)
print("Average classification: ", average_classification / iterations)