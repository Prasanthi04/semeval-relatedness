#!/usr/bin/python

"""
SemEval 2014, Task 1 -- Sentence Relatedness

This script has several requirements.
Firstly, you need to have the following libraries installed:
* NLTK
* Scikit-Learn
* SciPy / NumPy
* PyLab

Secondly, you need to have a file containing word embeddings
as generated by word2vec, in txt format.
Using this will take a long time the first run, 
but this will be binarized after the first loading, 
cutting loading time to a few seconds.
Also note that the memory requirements for this is quite high (~8gig).
Running on e.g. Zardoz is recommended.

Thirdly, you need to have the SICK data files.

Before using the script, make sure to change the paths (above main)
so that they correspond with the locations of your files.

Running example:
python semeval_task1_test.py 

To also evaluate, add the following to the command (fix paths first!):
&& R --no-save --slave --vanilla --args foo.txt 
/home/p269101/corp/sick/trial/SICK_trial.txt < 
/home/p269101/corp/sick/sick_evaluation.R
"""

__author__ = 'Johannes Bjerva'
__email__  = 'j.bjerva@rug.nl'

import cPickle
import shlex
import random
import numpy as np
from sys import argv, stdout
from subprocess import check_output, call, Popen, PIPE
from collections import defaultdict

import requests

from scipy.spatial.distance import cosine
from sklearn import linear_model
from sklearn.svm import SVR
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor, ExtraTreesRegressor

from nltk.corpus import wordnet as wn
from nltk.corpus.reader.wordnet import WordNetError

import load_semeval_data
import save_semeval_data
import drs_complexity

def getReplacements(t, h):
    """
    Return all posible replacements for sentence t to become more like sentence h.
    """
    replacements = []
    for wordT in t:
         if wordT in paraphrases:
             for replacementWord in paraphrases[wordT]:
                 if replacementWord in h and replacementWord not in t and wordT not in h:
                     replacements.append([wordT, replacementWord])
    return replacements

def getNumberOfInstances(modelfile):
    """
    Return the number of instances in the modelfile.
    """
    firstLine = open(modelfile, 'r').readline()
    return float(len(firstLine.split('d'))-2)
  
def instance_overlap(id, sentence_a, sentence_b):
    """
    Calculate the amount of overlap between the instances in the models of sentence_a (t) and sentence_b (h).
    """
    kthFile = os.path.join(shared_sick, str(id), 'kth.mod')
    if not os.path.isfile(kthFile):
        return 0
    kth = getNumberOfInstances(kthFile)
    kt = getNumberOfInstances(os.path.join(shared_sick, str(id), 'kt.mod'))
    kh = getNumberOfInstances(os.path.join(shared_sick, str(id), 'kh.mod'))
    if kh == 0:
        return 0
    return 1 - (kth - kt) / kh
        

def instance_overlap2(id, sentence_a, sentence_b):
    """
    Calculate the amount of overlap between the instances in the models of sentence_a (t) and sentence_b (h).
    And also try to do the same while replacing words with paraphrases to obtain a higher score.
    """
    score = 0
    kthFile = os.path.join(shared_sick, str(id), 'kth.mod')
    if not os.path.isfile(kthFile):
        score = 0
    else:
        kth = getNumberOfInstances(kthFile)
        kt = getNumberOfInstances(os.path.join(shared_sick, str(id), 'kt.mod'))
        kh = getNumberOfInstances(os.path.join(shared_sick, str(id), 'kh.mod'))
        if kh == 0:
            score = 0
        else: 
            score = 1 - (kth - kt) / kh

    for counter in range(1,8):
        newfolder = os.path.join(shared_sick2,'{0}.{1}'.format(str(id), counter))
        if os.path.isfile(os.path.join(newfolder, 'kth.mod')):
            kth = getNumberOfInstances(os.path.join(newfolder, 'kth.mod'))
            kt = getNumberOfInstances(os.path.join(newfolder, 'kt.mod'))
            kh = getNumberOfInstances(os.path.join(newfolder, 'kh.mod'))
            if kh > 0:
                new_score = 1 - (kth - kt) / kh
                if new_score > score:
                    score = new_score
    return score

def get_number_of_relations(modelfile):
    """
    Return the amount of relations in the modelfile.
    """
    counter = 0
    for line in open(modelfile):
        if line.find('f(2') > 0:
            counter += line.count('(')-1
    return float(counter)
  
def relation_overlap(id, sentence_a, sentence_b):
    """
    Calculate the amount of overlap between the relations in the models of sentence_a (t) and sentence_b (h).
    """
    kthFile = os.path.join(shared_sick, str(id), 'kth.mod')
    if not os.path.isfile(kthFile):
        return 0
    kth = get_number_of_relations(os.path.join(shared_sick, str(id), 'kth.mod'))
    kt = get_number_of_relations(os.path.join(shared_sick, str(id), 'kt.mod'))
    kh = get_number_of_relations(os.path.join(shared_sick, str(id), 'kh.mod'))
    if kh == 0:
        return 0
    return 1 - (kth -kt) / kh
  
def relation_overlap2(id, sentence_a, sentence_b):
    """
    Calculate the amount of overlap between the relations in the models of sentence_a (t) and sentence_b (h).
    And also try to do the same while replacing words with paraphrases to obtain a higher score.
    """
    score = 0
    kthFile = os.path.join(shared_sick, str(id), 'kth.mod')
    if not os.path.isfile(kthFile):
        score = 0
    else:
        kth = get_number_of_relations(os.path.join(shared_sick, str(id), 'kth.mod'))
        kt = get_number_of_relations(os.path.join(shared_sick, str(id), 'kt.mod'))
        kh = get_number_of_relations(os.path.join(shared_sick, str(id), 'kh.mod'))
        if kh == 0:
            score = 0
        else:
            score = 1 - (kth -kt) / kh
    
    for counter in range(1,8):
        newfolder = os.path.join(shared_sick2,'{0}.{1}'.format(str(id), counter))
        if os.path.isfile(os.path.join(newfolder, 'kth.mod')):
            kth = get_number_of_relations(os.path.join(newfolder, 'kth.mod'))
            kt = get_number_of_relations(os.path.join(newfolder, 'kt.mod'))
            kh = get_number_of_relations(os.path.join(newfolder, 'kh.mod'))
            if kh > 0:
                new_score = 1 - (kth - kt) / kh
                if new_score > score:
                    score = new_score
    return score
  
def word_overlap2(sentence_a, sentence_b):
    """
    Calculate the word overlap of two sentences and tries to use paraphrases to get a higher score
    """
    
    a_set = set(word for word in sentence_a)
    b_set = set(word for word in sentence_b)
    score = len(a_set&b_set)/float(len(a_set|b_set))

    for replacement in getReplacements(sentence_a, sentence_b):
        sentence_a[sentence_a.index(replacement[0])] = replacement[1]
        a_set = set(word for word in sentence_a)
        b_set = set(word for word in sentence_b)
        newScore = len(a_set&b_set)/float(len(a_set|b_set))
        if newScore > score:
            score = newScore
        sentence_a[sentence_a.index(replacement[1])] = replacement[0]
    return score
  
def johan_contradiction(id):
    for line in open('working/results.raw'):
        words = line.split()
        if words[0] == str(id):
            if words[len(words)-1] == 'CONTRADICTION':
                 return 1
            else:
                 return 0
          
def johan_entailment(id):
    for line in open('working/results.raw'):
        words = line.split()
        if words[0] == str(id):
            if words[len(words)-1] == 'ENTAILEMENT':
                 return 1
            else:
                 return 0  

def johan_neutral(id):
    for line in open('working/results.raw'):
        words = line.split()
        if words[0] == str(id):
            if words[len(words)-1] == 'NEUTRAL':
                 return 1
            else:
                 return 0

def bigrams(sentence):
    """
    Since the skipgram model includes bigrams, look for them.
    These are represented as word1_word2.
    """
    return [word+'_'+sentence[i+1] 
            if word+'_'+sentence[i+1] in word_ids else None 
                for i, word in enumerate(sentence[:-1])] if USE_BIGRAMS else []

def trigrams(sentence):
    """
    Since the skipgram model includes trigrams, look for them.
    These are represented as word1_word2_word3.
    """
    return [word+'_'+sentence[i+1]+'_'+sentence[i+2] 
            if word+'_'+sentence[i+1]+'_'+sentence[i+2] in word_ids else None 
                for i, word in enumerate(sentence[:-2])] if USE_TRIGRAMS else []
        
def sentence_composition(sentence_a, sentence_b):
    """
    Return the composition of two sentences (element-wise multiplication)
    """
    sent_a = np.sum([projections[word_ids[word]] 
        if word in word_ids else [0] 
            for word in sentence_a+bigrams(sentence_a)], axis=0)
    sent_b = np.sum([projections[word_ids[word]] 
        if word in word_ids else [0] 
            for word in sentence_b+bigrams(sentence_b)], axis=0)
    
    reps = sent_a * sent_b

    return reps

def sentence_distance(sentence_a, sentence_b):
    """
    Return the cosine distance between two sentences
    """
    
    sent_a = np.sum([projections[word_ids[word]] 
        if word in word_ids else [0] 
            for word in sentence_a+bigrams(sentence_a)+trigrams(sentence_a)], axis=0)
    sent_b = np.sum([projections[word_ids[word]] 
        if word in word_ids else [0] 
            for word in sentence_b+bigrams(sentence_b)+trigrams(sentence_b)], axis=0)
   
    return cosine(sent_a, sent_b)

def synset_overlap(sentence_a, sentence_b):
    """
    Calculate the synset overlap of two sentences.
    Currently uses the first 5 noun senses.
    """
    def synsets(word):
        sense_lemmas = []
        for pos in ('n'):#,'a'):
            for i in xrange(5):
                try:
                    sense_lemmas += [lemma.name 
                        for lemma in wn.synset('{0}.{1}.0{2}'.format(word, pos, i)).lemmas]
                except WordNetError: 
                    pass
        return sense_lemmas

    a_set = set(lemma for word in sentence_a for lemma in synsets(word))
    b_set = set(lemma for word in sentence_b for lemma in synsets(word))
    score = len(a_set&b_set)/float(len(a_set|b_set))

    return score

def synset_distance(sentence_a, sentence_b):
    def distance(word, sentence_b):
        try:
            synset_a = wn.synset('{0}.n.01'.format(word))
        except WordNetError:
            return 0.0

        max_similarity = 0.0
        for word2 in sentence_b:
            try:
                similarity = synset_a.path_similarity(wn.synset('{0}.n.01'.format(word2)))
                if similarity > max_similarity:
                    max_similarity = similarity
            except WordNetError:
                continue

        return max_similarity

    distances = [distance(word, sentence_b) for word in sentence_a]

    return sum(distances)/float(len([1 for i in distances if i > 0.0]))


def word_overlap(sentence_a, sentence_b):
    """
    Calculate the word overlap of two sentences.
    """
    a_set = set(word for word in sentence_a)
    b_set = set(word for word in sentence_b)
    score = len(a_set&b_set)/float(len(a_set|b_set))

    return score

def sentence_lengths(sentence_a, sentence_b):
    """
    Calculate the proportionate difference in sentence lengths.
    """
    return abs(len(sentence_a)-len(sentence_b))/float(min(len(sentence_a),len(sentence_b)))


url = 'http://127.0.0.1:7777/raw/pipeline?format=xml'
def sent_complexity(sentence):
    r = requests.post(url, data=' '.join(sentence))
    complexity = drs_complexity.parse_xml(r.text)

    print complexity
    return complexity

def drs_complexity_difference(sentence_a, sentence_b):
    sent_a_complexity = sent_complexity(sentence_a)
    sent_b_complexity = sent_complexity(sentence_b)

    return abs(sent_a_complexity-sent_b_complexity)


def regression(X_train, y_train, X_test, y_test):
    """
    Train the regressor from Scikit-Learn.
    """
    # Set params for regression
    # These work well
    #params = {'n_estimators': 2000, 'max_depth': 2, 'min_samples_split': 0.5, 'subsample': 0.45,
    #          'learning_rate': 0.08, 'random_state': 0, 'loss': 'huber', 'alpha': 0.8} 

    # These work better (GradientBoost)
    #params = {'n_estimators': 1000, 'max_depth': 3, 'min_samples_split': 1, 'subsample': 0.7,
    #          'learning_rate': 0.07, 'random_state': 0, 'loss': 'huber', 'alpha': 0.7,
    #          'min_samples_leaf': 1, 'verbose': 0}#, 'max_features':1} 
    #regr = GradientBoostingRegressor(**params)

    # Testing random forest regressor

    params = {'n_estimators':75000, 'criterion':'mse', 'max_depth':None, 'min_samples_split':1, #'estimators':800, depth:18
              'min_samples_leaf':1, 'max_features':2, 'bootstrap':True, 'oob_score':False,  #'max_features':'log2'
              'n_jobs':32, 'random_state':3, 'verbose':1, 'min_density':None, 'max_leaf_nodes':None}
    regr = RandomForestRegressor(**params)


    #regr = linear_model.LinearRegression()#(alpha = .01)
    # regr = SVR(kernel='poly', C=1e3, degree=2)
    # regr = linear_model.ElasticNet(alpha=alpha, l1_ratio=0.7)

    # Train the model using the training sets
    regr.fit(X_train, y_train)

    # Plot the resutls

    save_semeval_data.plot_results(regr, params, X_test, y_test, feature_names)

    # Show the mean squared error
    print("Residual sum of squares: %.2f" % np.mean((regr.predict(X_test) - y_test) ** 2))
    # Explained variance score: 1 is perfect prediction (???)
    print('Variance score: %.2f' % regr.score(X_test, y_test))
    
    return regr

feature_names = np.array([
    'CDSM', 
    'WORDS', 
    'SYN_OVER', 
    'SYN_DIST', 
    'LENGTH',
    #'GOLD_ENT',
    'ENTAILMENT',
    'PROVER',
    'DOM_NV', 
    'REL_NV', 
    'WRD_NV', 
    'MOD_NV',
    'WORDS2',
    'DRS_COMPLEXITY'
    ], dtype='|S7')

def get_features(line):
    """
    Feature extraction.
    Comment out / add lines to disable / add features.
    Add the name to the feature_names array.
    """
    return [
        sentence_distance(line[1], line[2]), # Cosine distance between sentences
        word_overlap(line[1], line[2]),      # Proportion of word overlap
        synset_overlap(line[1], line[2]),    # Proportion of synset lemma overlap
        synset_distance(line[1], line[2]),   # Synset distance (Does not seem to help much?)
        sentence_lengths(line[1], line[2]),  # Proportion of difference in sentence length
        #line[4],                             # Gold standard entailment judgement (inflated)
        line[5],                             # Prediction from Johan's system
        line[6],                             # Prover output
        line[7],                             # Domain novelty                  
        line[8],                             # Relation novelty
        line[9],                             # Wordnet novelty
        line[10],                            # Model novelty
        line[11],                            # Word Overlap
        abs(line[12]-line[13])               # DRS Complexity
            ]

'''
feature_names = np.array(['INSTANCE', 'instance2','relation', 'RELATION2', 'WORDS', 'CONTRADICTION', 'ENTAILMENT', 'NEUTRAL'], dtype='|S7')
def get_features(line):
    """
    Feature extraction.
    Comment out / add lines to disable / add features.
    Add the name to the feature_names array.
    """
    return [
        instance_overlap(line[0], line[1], line[2]),   # Instances overlap in models
        instance_overlap2(line[0], line[1], line[2]),  # Instances overlap with the help of paraphrases
        relation_overlap(line[0], line[1], line[2]),   # Relation overlap in models
        relation_overlap2(line[0], line[1], line[2]),  # Relation overlap in models with the help of paraphrases
        word_overlap2(line[1], line[2]),               # Proportion of word overlap with the help of paraphrases
        #sentence_distance(line[1], line[2]),           # Cosine distance between sentences
        #word_overlap(line[1], line[2]),                # Proportion of word overlap
        #synset_overlap(line[1], line[2]),              # Proportion of synset lemma overlap
        #sentence_lengths(line[1], line[2]),            # Proportion of difference in sentence length
        #line[4]/2.0,                                   # Gold standard entailment judgement (inflated)
        johan_contradiction(line[0]),                  # Johans prediction of contradiction
        johan_entailment(line[0]),                     # Johans prediction of entailment
        johan_neutral(line[0])                         # Johans prediction of neutral
            ]


# Hard-coded paths
ppdb = 'working/ppdb.1'
wvec_path = 'working/'
sick_train = 'working/SICK_train.txt'
sick_trial = 'working/SICK_trial.txt'
shared_sick = 'working/sick/'
shared_sick2 = 'working/sick2/'
'''

#########################
##### PARAMS ############
#########################
DEBUG = True
USE_BIGRAMS = False  # Slightly worse results when this is switched on
USE_TRIGRAMS = True

RECALC_FEATURES = True # Remember to switch if features are changed

# Hard-coded paths
#wvec_path = '/home/p269101/Dev/trunk/'
shared_sick = './working/sick/'
ppdb = './working/ppdb.1'

if __name__ == '__main__':
    # Load the paraphrases data.
    paraphrases = {}
    for line in open(ppdb):
        source = line.split('|')[1][1:-1]
        target = line.split('|')[4][1:-1]
        if source in paraphrases:
            paraphrases[source].append(target)
        else:
            paraphrases[source] = [target]

    # Load sick data
    sick_data = load_semeval_data.load_sick_data()

    # Split into training/test
    split = int(len(sick_data)*0.9)
    sick_train = sick_data[:split]
    sick_test = sick_data[split:]

    # Calculate stop
    word_freqs = defaultdict(int)
    for line in sick_data:
        for word in line[1]+line[2]:
            word_freqs[word] += 1

    stop_list = set(sorted(word_freqs,key=word_freqs.get,reverse=True)[:3])

    print stop_list

    print 'test size: {0}, training size: {1}'.format(len(sick_test), len(sick_train))

    if RECALC_FEATURES:
        # Load projection data
        word_ids, projections = load_semeval_data.load_embeddings()

        # Extract training features and targets
        train_sources = np.array([get_features(line) for line in sick_train])
        train_targets = np.array([line[3] for line in sick_train])

        # Extract trial features and targets
        trial_sources = np.array([get_features(line) for line in sick_test])
        trial_targets = np.array([line[3] for line in sick_test])

        with open('features_np.pickle', 'wb') as out_f:
            np.save(out_f, train_sources)
            np.save(out_f, train_targets)
            np.save(out_f, trial_sources)
            np.save(out_f, trial_targets)
    else:
        with open('features_np.pickle', 'rb') as in_f:
            train_sources = np.load(in_f)
            train_targets = np.load(in_f)
            trial_sources = np.load(in_f)
            trial_targets = np.load(in_f)

    # Train the regressor
    clf = regression(train_sources, train_targets, trial_sources, trial_targets)

    # Apply regressor to trial data
    outputs = clf.predict(trial_sources)

    # Evaluate regressor
    save_semeval_data.write_for_evaluation(outputs, [line[0] for line in sick_test]) #Outputs and sick_ids

    save_semeval_data.plot_deviation(outputs, trial_targets)

    # Write to MESH
    #save_semeval_data.write_to_mesh(train_sources, train_targets, [line[0] for line in sick_train], True) #sick_ids
    #save_semeval_data.write_to_mesh(trial_sources, trial_targets, [line[0] for line in sick_test], False) #sick_ids

#DSM + Words
'''
[1] "Processing foo.txt"
[1] "No data for the entailment task: evaluation on relatedness only"
[1] "Relatedness: Pearson correlation 0.611219539386618"
[1] "Relatedness: Spearman correlation 0.579121096289511"
[1] "Relatedness: MSE 0.636769966364063"
'''

#DSM + Words + Synsets (1)
'''
[1] "Processing foo.txt"
[1] "No data for the entailment task: evaluation on relatedness only"
[1] "Relatedness: Pearson correlation 0.6240941025167"
[1] "Relatedness: Spearman correlation 0.581191940616606"
[1] "Relatedness: MSE 0.620184604639824"
'''

#DSM w/trigram + Words + Synsets (1)
'''
[1] "Processing foo.txt"
[1] "No data for the entailment task: evaluation on relatedness only"
[1] "Relatedness: Pearson correlation 0.629040484297528"
[1] "Relatedness: Spearman correlation 0.587369803749406"
[1] "Relatedness: MSE 0.611421097501485"
'''

#DSM w/trigram + Words + Synsets (5)
'''
[1] "Processing foo.txt"
[1] "No data for the entailment task: evaluation on relatedness only"
[1] "Relatedness: Pearson correlation 0.634456413747237"
[1] "Relatedness: Spearman correlation 0.59369997611572"
[1] "Relatedness: MSE 0.604260603099203"
'''

#Above + Length
'''
[1] "Processing foo.txt"
[1] "No data for the entailment task: evaluation on relatedness only"
[1] "Relatedness: Pearson correlation 0.644495416146579"
[1] "Relatedness: Spearman correlation 0.615426300643788"
[1] "Relatedness: MSE 0.591781380569611"
'''

#Regressor tuning
'''
[1] "Processing foo.txt"
[1] "No data for the entailment task: evaluation on relatedness only"
[1] "Relatedness: Pearson correlation 0.66953725062349"
[1] "Relatedness: Spearman correlation 0.637914417450239"
[1] "Relatedness: MSE 0.559007711760069"
'''

#With entailment (Gold)
'''
[1] "Processing foo.txt"
[1] "No data for the entailment task: evaluation on relatedness only"
[1] "Relatedness: Pearson correlation 0.796717745220322"
[1] "Relatedness: Spearman correlation 0.815944668105982"
[1] "Relatedness: MSE 0.37025897125941"
'''

#Boxer features
'''
[1] "Processing foo.txt"
[1] "No data for the entailment task: evaluation on relatedness only"
[1] "Relatedness: Pearson correlation 0.755935252390634"
[1] "Relatedness: Spearman correlation 0.730835956061164"
[1] "Relatedness: MSE 0.435116692987163"
'''

#New regressor
'''
[1] "Processing foo.txt"
[1] "No data for the entailment task: evaluation on relatedness only"
[1] "Relatedness: Pearson correlation 0.790047753882667"
[1] "Relatedness: Spearman correlation 0.763151377170929"
[1] "Relatedness: MSE 0.382032158131169"
'''
