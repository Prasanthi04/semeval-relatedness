#!/usr/bin/python

"""
Data loading module for SemEval Shared Task 1.
"""

__author__ = 'Johannes Bjerva'
__email__  = 'j.bjerva@rug.nl'

import cPickle
import numpy as np
from sys import stdout
from collections import defaultdict
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import WordPunctTokenizer
from nltk.tokenize.treebank import TreebankWordTokenizer
from subprocess import check_output, call
import os
import shlex
import requests

import drs_complexity

# Params
DEBUG = True
USE_BOXER = True
WRITE_COMPLEXITY = True

# Tools for lemmatization/tokenization
wnl = WordNetLemmatizer()
wpt = WordPunctTokenizer()
twt = TreebankWordTokenizer()

# Used to encode the entailment judgements numerically
judgement_ids = defaultdict(lambda:len(judgement_ids))
prediction_ids = defaultdict(lambda:len(prediction_ids))
prover_ids = defaultdict(lambda:len(prover_ids))

wvec_path = './wvec/'

def load_embeddings():
    """
    Load embeddings either from pre-processed binary, or fallback to txt if non-existant
    """
    vector_file = 'GoogleNews-vectors-negative300.txt'#argv[1]

    try:
        if DEBUG: stdout.write('loading embeddings from archives.. ')

        with open('google_news_ids.pickle', 'rb') as in_f:
            word_ids = cPickle.load(in_f)     
        with open('google_news_np.pickle', 'rb') as in_f:
            projections = np.load(in_f)

    except IOError:
        if DEBUG: stdout.write(' error - processing txt-file instead (~15 mins)..')  

        
        projections, word_ids = load_word2vec(vector_file)
        with open('google_news_ids.pickle', 'wb') as out_f:
            cPickle.dump(dict(word_ids), out_f, -1)
        with open('google_news_np.pickle', 'wb') as out_f:
            np.save(out_f, projections)
    
    if DEBUG: stdout.write(' done!\n')

    return word_ids, projections

def load_word2vec(f_name):
    """
    Load word projections generated by word2vec from txt-rep.
    This takes a  while.
    """
    if DEBUG: stdout.write('\ngetting vocab size: ')
    dimensions = 300 #int(f_name.lstrip('word_projections-')[:-4])
    vocab_size = int(check_output(shlex.split('wc -l {0}'.format(wvec_path+f_name))).split()[0])
    if DEBUG: stdout.write(str(vocab_size)+'\n')

    # NP matrix for word projections
    word_projections = np.zeros( (vocab_size, dimensions), dtype=np.float64)
    word_ids = defaultdict(lambda:len(word_ids))

    if DEBUG: print 'filling rep matrix'
    with open(wvec_path+f_name, 'r') as in_f:
        for line in in_f:
            fields = line.split()
            word_id = word_ids[fields[0].lower()]
            word_projections[word_id] = [float(i) for i in fields[1:]]

    return word_projections, word_ids


def load_sick_data():
    """
    Attempt to load sick data from binary,
    otherwise fall back to txt.
    """
    sick_path = '/home/p269101/corp/sick/'
    sick_train = 'train/SICK_train.txt'
    sick_trial = 'trial/SICK_trial.txt'

    try:
        if DEBUG: stdout.write('loading sick from archives.. ')

        with open('sick.pickle', 'rb') as in_f:
            sick_data = cPickle.load(in_f)

    except IOError:
        if DEBUG: stdout.write(' error - loading from txt-files..')
    
        sick_data =  load_sick_data_from_txt(sick_path+sick_train)
        sick_data.extend( load_sick_data_from_txt(sick_path+sick_trial) )
        with open('sick.pickle', 'wb') as out_f:
            cPickle.dump(sick_data, out_f, -1)
    
    if DEBUG: stdout.write(' done!\n')

    return sick_data

def load_sick_data_from_txt(f_name):
    """
    Load data from the sick data set.
    Lemmatize all words using NLTK
    """
    data = []
    with open(f_name, 'r') as in_f:
        header = in_f.readline()
        for line in in_f:
            fields = line.split('\t')
            pair_id = int(fields[0].strip())

            # Tokenizing gives a better Spearman correlation, but worse Pearson...
            #sentence_a = [wnl.lemmatize(word) for word in twt.tokenize(fields[1].strip().lower())]
            #sentence_b = [wnl.lemmatize(word) for word in twt.tokenize(fields[2].strip().lower())]
            raw_sentence_a = [word for word in fields[1].strip().split()]
            raw_sentence_b = [word for word in fields[2].strip().split()]

            sentence_a = [wnl.lemmatize(word.lower()) for word in raw_sentence_a]
            sentence_b = [wnl.lemmatize(word.lower()) for word in raw_sentence_b]
            
            relatedness = float(fields[3].strip())
            judgement = fields[4].strip()

            document_data = (pair_id, sentence_a, sentence_b, relatedness, judgement_ids[judgement])

            #if WRITE_COMPLEXITY:
            #    get_and_write_complexities(str(pair_id), raw_sentence_a, raw_sentence_b)

            if USE_BOXER:
                boxer_features = get_shared_features(str(pair_id), raw_sentence_a, raw_sentence_b)
                document_data = document_data + boxer_features

            
            data.append(document_data)

    return data

def get_shared_features(pair_id, sentence_a, sentence_b):
    root = './working/sick/'+pair_id
    data = ()
    with open(root+'/prediction.txt', 'r') as in_f:
        line = in_f.readline().lower().strip()
        data = data + (prediction_ids[line],)

    with open(root+'/modsizedif.txt', 'r') as in_f:
        lines = in_f.readlines()
        prover  = prover_ids[lines[0].split()[0][:-1]] # First field of line without trailing '.'
        dom_nov = float(lines[1].split()[0][:-1]) 
        rel_nov = float(lines[2].split()[0][:-1])
        wrd_nov = float(lines[3].split()[0][:-1])
        mod_nov = float(lines[4].split()[0][:-1])
        word_overlap = float(lines[5].split()[0][:-1])

        data = data + (prover, dom_nov, rel_nov, wrd_nov, mod_nov, word_overlap)

    try: 
        with open(root+'/complexities.txt', 'r') as in_f:
            line = in_f.readlines()
            data = data + (float(line[0]), float(line[1]))
    except IOError:
        data = data + get_and_write_complexities(pair_id, sentence_a, sentence_b)

    return data

url = 'http://127.0.0.1:7777/raw/pipeline?format=xml'
def get_and_write_complexities(pair_id, sentence_a, sentence_b):
    root = './working/sick/'+pair_id

    r = requests.post(url, data=' '.join(sentence_a))
    complexity_a = drs_complexity.parse_xml(r.text)

    r = requests.post(url, data=' '.join(sentence_b))
    complexity_b = drs_complexity.parse_xml(r.text)
    
    with open(root+'/complexities.txt', 'w') as out_f:
        out_f.write('{0}\n{1}\n'.format(complexity_a, complexity_b))

    print pair_id, complexity_a, complexity_b
    return (complexity_a, complexity_b)


"""
unknown.   % prover output    
-1.   % domain novelty   
-1.   % relation novelty 
-1.   % wordnet novelty  
1.   % model novelty    
0.5.   % word overlap
"""

def load_shared_sick_data(path):
    """
    Load shared sick data, parsed with boxer etc.
    TODO: Extract relevant features
    """
    data = []
    prefix = len(path)
    err, corr = 0,0
    for root, dirs, files in os.walk(path):
        if len(files) > 5:
            try:
                sick_id = int(root[prefix:])
                with open(root+'/t.tok', 'r') as in_f:
                    sentence_a = [wnl.lemmatize(word) for word in in_f.readline().lower().split()]

                with open(root+'/h.tok', 'r') as in_f:
                    sentence_b = [wnl.lemmatize(word) for word in in_f.readline().lower().split()]

                with open(root+'/gold.sim', 'r') as in_f:
                    relatedness = float(in_f.readline().strip())

                with open(root+'/gold.rte', 'r') as in_f:
                    judgement = in_f.readline().strip()


                data.append((sick_id, sentence_a, sentence_b, relatedness, judgement_ids[judgement]))
                corr += 1
            except IOError:
                err += 1

    print "done", corr
    print "fail", err
            
    #root = /home/p269101/Dev/candc2/candc/working/sick/24
    #files=
    #['t', 'h', 'gold.sim', 'gold.rte', 't.tok', 'h.tok', 'th.tok', 't.ccg', 'h.ccg', 
    #'th.ccg', 'prediction.txt', 'modsizedif.txt', 't.drs', 'h.drs', 'th.drs', 'kt.mwn', 
    #'kh.mwn', 'kth.mwn', 'vampire.in', 'paradox.in', 'vampire.out', 'paradox.out', 
    #'tpmb.out', 't.mod', 'h.mod', 'th.mod', 'tth.mod']

    return data
