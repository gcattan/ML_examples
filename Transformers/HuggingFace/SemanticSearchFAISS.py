# -*- coding: utf-8 -*-
"""
Created on Mon Feb 20 16:36:45 2023

Semantic search with FAISS (Facebook AI Similarity Search)

Dataset: github repository issues
First we pre-process the dataset and then we create embeddings that can be utilized by the FAISS library.

This use case is an example of asymmetric semantic search because we have a short query whose answer 
we’d like to find in a longer document, like a an issue comment.

pip install datasets evaluate transformers[sentencepiece]
pip install faiss-gpu

Alternatively: pip install faiss-cpu
"""

from datasets import load_dataset
import pandas as pd

issues_dataset = load_dataset("lewtun/github-issues", split="train")

#filter out the pull requests, as these tend to be rarely used for answering user queries and will introduce noise in our search engine
issues_dataset = issues_dataset.filter(
    lambda x: (x["is_pull_request"] == False and len(x["comments"]) > 0)
)

#keep the most informative columns
columns = issues_dataset.column_names
columns_to_keep = ["title", "body", "html_url", "comments"]
#symmetric_difference: all items in both datasets except their intersection elements
columns_to_remove = set(columns_to_keep).symmetric_difference(columns)
issues_dataset = issues_dataset.remove_columns(columns_to_remove)

#switch to panda format
issues_dataset.set_format("pandas")
df = issues_dataset[:]

#we want to get one row for each of these comments
comments_df = df.explode("comments", ignore_index=True) #for each comment make an extra row duplicating the data
#the title", "body", "html_url" will be the same for each comment for each issue
pd.set_option('max_colwidth', -1)
print(comments_df.head(4).iloc[:, 0:2])

#we can quickly switch back to a Dataset by loading the DataFrame in memory:
from datasets import Dataset
comments_dataset = Dataset.from_pandas(comments_df)
#the number of rows has increased

#let’s create a new comments_length column that contains the number of words per comment
comments_dataset = comments_dataset.map(
    lambda x: {"comment_length": len(x["comments"].split())}
)

#filter short comments, shorter than 15 words
comments_dataset = comments_dataset.filter(lambda x: x["comment_length"] > 15)

#let’s concatenate the issue title, description, and comments together in a new text column "text".
def concatenate_text(examples):
    return {
        "text": examples["title"]
        + " \n "
        + examples["body"]
        + " \n "
        + examples["comments"]
    }
comments_dataset = comments_dataset.map(concatenate_text)

#finished pre-processing the dataset

#creating text embeddings

from transformers import AutoTokenizer, AutoModel

model_ckpt = "sentence-transformers/multi-qa-mpnet-base-dot-v1"
tokenizer = AutoTokenizer.from_pretrained(model_ckpt)
model = AutoModel.from_pretrained(model_ckpt)

#switch to GPU
import torch
device = torch.device("cuda")
model.to(device)

#create the embeddings 
def cls_pooling(model_output):
    return model_output.last_hidden_state[:, 0] #we collect the last hidden state for the special [CLS] token, the CLS is always in the beginning and that is why the 0 index.

#create a helper function that will tokenize a list of documents, place the tensors on the GPU
def get_embeddings(text_list):
    encoded_input = tokenizer( #tokenize the documents
        text_list, padding=True, truncation=True, return_tensors="pt"
    )
    encoded_input = {k: v.to(device) for k, v in encoded_input.items()} #to gpu
    model_output = model(**encoded_input) #feed to tokenized documents
    return cls_pooling(model_output) #finally apply CLS pooling to the outputs of the model

#embedding = get_embeddings(comments_dataset["text"][0])

#generate an embedding for each document in the form of a 768-dimensional vector
#result needs to be a numpy array in order to be used with FAISS
embeddings_dataset = comments_dataset.map(
    lambda x: {"embeddings": get_embeddings(x["text"]).detach().cpu().numpy()[0]}
)

#FAISS semantic search with embeddings

#we need to create an index over the column that will be used to find which embeddings are similar to an input embedding
embeddings_dataset.add_faiss_index(column="embeddings")

#question and its embedding
question = "How can I load a dataset offline?"
question_embedding = get_embeddings([question]).cpu().detach().numpy() #input embedding for the query

#perform search
scores, samples = embeddings_dataset.get_nearest_examples(
    "embeddings", question_embedding, k=5
)

#convert to panda and sort the results
samples_df = pd.DataFrame.from_dict(samples)
samples_df["scores"] = scores
samples_df.sort_values("scores", ascending=False, inplace=True)

# print sorted comments that best answer the question
for _, row in samples_df.iterrows():
    print(f"COMMENT: {row.comments}")
    print(f"SCORE: {row.scores}")
    print(f"TITLE: {row.title}")
    print(f"URL: {row.html_url}")
    print("=" * 50)
    print()