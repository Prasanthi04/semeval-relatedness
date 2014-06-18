#!/usr/bin/python
'''
This script is intended for adding in the corrected values from sick_corr.run,
as generated by reclassify_neutrals.py.
See combine.py for the 'normal' version.
'''
__author__ = 'Johannes Bjerva'
__email__  = 'j.bjerva@rug.nl'

rel_lines = sorted([line.split() for line in open('./working/foo.txt', 'r')][1:], key=lambda x:int(x[0]))
ids = set(i[0] for i in rel_lines)
corr_lines = dict([line.split()[:2] for line in open('./sick_corr.run', 'r') if line.split()[0] in ids])

rte_lines = dict([line.split()[:2] for line in open('./working/sick.run', 'r') if line.split()[0] in ids])

with open('submission_corr.txt', 'w') as out_f:
    out_f.write('pair_ID\tentailment_judgment\trelatedness_score\n')
    for val in rel_lines:
        i = val[0]
        try:
            out_f.write(str(i)+'\t'+corr_lines[i] + '\t'+val[-1]+'\n')
        except:
            out_f.write(str(i)+'\t'+rte_lines[i] + '\t'+val[-1]+'\n')
