import numpy as np
import matplotlib.pyplot as plt
import datetime
import sys

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D, MaxPooling2D
from tensorflow.keras.layers import Activation, Dropout, Flatten, Dense
from tensorflow.keras import backend as K
from tensorflow.keras import optimizers

from towhee import pipeline

from sklearn.pipeline import make_pipeline
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import balanced_accuracy_score

import mne
#from pyts.image import RecurrencePlot
import gc
import os
from sklearn import svm
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import scale

from pymilvus import (
    connections,
    utility,
    FieldSchema, CollectionSchema, DataType,
    Collection,
)

"""
=============================
Classification of EGG signal from two states: eyes open and eyes closed.
Each sample of the two states is represented as an image (a recurrence plot),
next the images are classified using Deep Learning model. It uses rp images that
were previously generated
=============================

Anaconda 3 2021_05
Python 3.8.8
Spyder 4.2.5
TensorFlow 2.3.0
Keras is installed as part of TensorFlow 2
Pyts 0.11 (a Python Package for Time Series Classification,exists in Anaconda, provides recurrence plots)

"""
# Authors: Anton Andreev
#
# License: BSD (3-clause)

'''
https://towardsdatascience.com/dont-overfit-how-to-prevent-overfitting-in-your-deep-learning-models-63274e552323
https://machinelearningmastery.com/evaluate-performance-deep-learning-models-keras/
'''

import warnings
#warnings.filterwarnings("ignore")

def BuildEmbeddings(folder, n_max_subjects, n_max_samples):

    epochs_all_subjects = []
    label_all_subjects = []
    
    samples_class1 = np.zeros(n_max_subjects) #for each subject
    samples_class2 = np.zeros(n_max_subjects)
    
    print("Loading data and generating embeddings ...")

    embedding_pipeline = pipeline('image-embedding')
    
    images_loaded = 0
    for filename in os.listdir(folder):
        if filename.endswith(".jpeg"): 
            
            #print(os.path.join(folder, filename))
            base_name = os.path.basename(filename)
            
            parts = base_name.split("_")
            #print(parts)
            label = int(parts[4].split(".")[0])
            subject = int(parts[1])
            #print("Subject: ", subject, " Label: ", label)
            
            if (subject < n_max_subjects):

                if (label == 0 and samples_class1[subject] < n_max_samples) or (label == 1 and samples_class2[subject] < n_max_samples):
                    
                    images_loaded = images_loaded + 1
                    file_path = os.path.join(folder, filename)
                    print(file_path)

                    if label == 0:
                        samples_class1[subject] = samples_class1[subject] + 1
                    elif label == 1:
                        samples_class2[subject] = samples_class2[subject] + 1

                    embedding = embedding_pipeline(file_path)
                    
                    #print(embedding[0])

                    epochs_all_subjects.append(embedding[0])

                    label_all_subjects.append(label)
                    
                    
                    print(images_loaded)
            
        else:
            continue
    
    print("Images loaded: ", images_loaded)
    return epochs_all_subjects, label_all_subjects
    
def StoreEmbeddingsIntoMulvis(embeddings, labels):
    connections.connect("default", host="localhost", port="19530")
    
    #shuffle
    indices = np.arange(len(labels))
    np.random.shuffle(indices)
    embeddings = embeddings[indices]
    labels = labels[indices]
    
    X_train, X_test, y_train, y_test = train_test_split(embeddings, labels, test_size=0.2, shuffle = True)
    
    has = utility.has_collection("rp_images_embeddings")
    
    if has:
        
        print("Drop old collection")
        utility.drop_collection("rp_images_embeddings")
        
    print("Creating collection")
    embedding_len = len(X_train[0])
    fields = [
        FieldSchema(name="pk", dtype=DataType.INT64, is_primary=True, auto_id=False),
        FieldSchema(name="embeddings", dtype=DataType.FLOAT_VECTOR, dim=embedding_len),
        FieldSchema(name="label", dtype=DataType.INT64),
    ]

    schema = CollectionSchema(fields, "Schema data stores embeddinigs")

    #print(fmt.format("Create collection `hello_milvus`"))
    rp_images_embeddings = Collection("rp_images_embeddings", schema, consistency_level="Strong")

    print("Start inserting ...")
    
    has = utility.has_collection("rp_images_embeddings")
    
    entities = [ [i for i in range(len(X_train))], X_train, y_train]

    insert_result = rp_images_embeddings.insert(entities)
    
    print("Create index")
    
    index = {
        "index_type": "IVF_FLAT",
        "metric_type": "L2",
        "params": {"nlist": 128},
    }

    rp_images_embeddings.create_index("embeddings", index)
    
    return rp_images_embeddings, X_test, y_test
    
    
def ClassifyUsingMulvis(collection, test_x, test_y, limit, metric_type):
    
    print("Start loading")
    collection.load()

    # -----------------------------------------------------------------------------
    # search based on vector similarity
    print("Start searching based on vector similarity")
    
    #should put some test data 
    
    vectors_to_search = test_x
    
    search_params = {
        "metric_type": metric_type,
        "params": {"nprobe": 10},
    }

    #start_time = time.time()
    result = collection.search(vectors_to_search, "embeddings", search_params, limit=limit, output_fields=["label"])
    #end_time = time.time()
    
    accuracy = 0
    
    for i, hits in enumerate(result):
        
        #print("label test_x", test_y[i])
        
        ones = 0
        
        for hit in hits:
            
            ones = ones + hit.entity.get('label')
            
            #print(f"hit: {hit}, label: {hit.entity.get('label')}")
            
        if (test_y[i] == 1 and ones >= (limit // 2) + 1):
            accuracy = accuracy + 1
        elif (test_y[i] == 0 and ones < (limit // 2) + 1):
            accuracy = accuracy + 1
            
        #print("========================================")
    
    print("Accuracy: ", str(accuracy / len(test_y) ) )
    #print(search_latency_fmt.format(end_time - start_time))

def ProcessFolder(folder, limit , metric_type):
    print(folder)
    print("Limit", limit)
    print("Metric type", metric_type)
    embeddings, labels = BuildEmbeddings(folder, 20, 1000)
    rp_images_embeddings, X_test, y_test = StoreEmbeddingsIntoMulvis(embeddings, labels)
    ClassifyUsingMulvis(rp_images_embeddings, X_test, y_test, limit , metric_type)
    print("==============================================")
    
def ProcessDataSet(folder, dataset):
    
    dirs = [x[0] for x in os.walk(folder)]
    
    for d in dirs:
        if  d.find(dataset) != -1 :
            ProcessFolder(d, 1 ,  "L2")
            ProcessFolder(d, 13 , "L2")
            ProcessFolder(d, 51 , "L2")
            ProcessFolder(d, 101 ,"L2")
    
        
#main

#print("Test data:================================================================================================================")

#data_folder="D:\Work\ML_examples\EEG\moabb.bi2013a\data"
data_folder="H:\data"
#data_folder="C:\Temp\data"
#data_folder="h:\data"
#configure tensor flow to avoid GPU out memory error
#https://stackoverflow.com/questions/36927607/how-can-i-solve-ran-out-of-gpu-memory-in-tensorflow/60558547#60558547


#folder = data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_3_nsub_1_per_20_nepo_600_set_BNCI2014008_as_image" # 0.7
#folder = data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_4_nsub_1_per_20_nepo_600_set_BNCI2014008_as_image"  #
#folder = data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_4_nsub_3_per_20_nepo_400_set_BNCI2014008_as_image"
#folder = data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_8_nsub_1_per_20_nepo_600_set_BNCI2014008_as_image"
#folder = data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_8_nsub_3_per_20_nepo_400_set_BNCI2014008_as_image"

#ProcessFolder(data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_4_nsub_1_per_20_nepo_600_set_BNCI2014008_as_image")
#ProcessFolder(data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_4_nsub_3_per_20_nepo_400_set_BNCI2014008_as_image")
#ProcessFolder(data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_8_nsub_1_per_20_nepo_600_set_BNCI2014008_as_image")
#ProcessFolder(data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_8_nsub_3_per_20_nepo_400_set_BNCI2014008_as_image")

#ProcessFolder(data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_4_nsub_10_per_20_nepo_400_set_BNCI2014008_as_image", 13, "L2") #0.56
#ProcessFolder(data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_4_nsub_10_per_20_nepo_400_set_BNCI2014008_as_image", 3, "L2") #0.52
#ProcessFolder(data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_4_nsub_10_per_20_nepo_400_set_BNCI2014008_as_image", 1, "L2")
#ProcessFolder(data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_4_nsub_10_per_20_nepo_400_set_BNCI2014008_as_image", 51, "L2") #0.56
#ProcessFolder(data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_4_nsub_10_per_20_nepo_400_set_BNCI2014008_as_image", 1, "IP")
#ProcessFolder(data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_4_nsub_10_per_20_nepo_400_set_BNCI2014008_as_image", 3, "IP")
#ProcessFolder(data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_4_nsub_10_per_20_nepo_400_set_BNCI2014008_as_image", 13, "IP")
#ProcessFolder(data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_4_nsub_10_per_20_nepo_400_set_BNCI2014008_as_image", 51, "IP")
#ProcessFolder(data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_4_nsub_10_per_20_nepo_400_set_BNCI2014008_as_image", 101, "L2") #0.57

ProcessFolder(data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_16_nsub_10_per_20_nepo_400_set_BNCI2014009_as_image", 101, "L2") #0.56
#ProcessFolder(data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_16_nsub_10_per_20_nepo_400_set_BNCI2014009_as_image", 13, "L2") #0.56
#ProcessFolder(data_folder + "\\rp_m_5_tau_30_f1_1_f2_24_el_16_nsub_10_per_20_nepo_400_set_BNCI2014009_as_image", 51, "L2") #0.56
#ProcessDataSet(data_folder, "BNCI2014009")

print("Done.")